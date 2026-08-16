from dataclasses import dataclass
from pathlib import PurePosixPath

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import (
    OperationStatus,
    OperationType,
    ProgressStage,
    ProgressState,
    SourceAction,
    SourceClassification,
)
from app.models import AuditEvent, FileOperation, MediaMatch, OrganizeJob, SourceItem
from app.providers.base import CloudProvider
from app.services.organizer_cloud import wait_for_provider_task
from app.services.organizer_support import make_idempotency_key
from app.services.progress_events import (
    record_file_operation_progress,
    record_job_progress,
)

MAX_TRASH_BATCH_SIZE = 50
PROTECTED_FILTER_REASONS = frozenset({"TARGET_TREE", "STAGING_TREE"})


@dataclass(frozen=True, slots=True)
class SourceCleanupResult:
    completed: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass(frozen=True, slots=True)
class _PreparedCleanupOperation:
    operation: FileOperation
    file_id: str


class SourceCleanupExecutor:
    """Move selected source files to the provider recycle bin exactly once."""

    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        matches: list[MediaMatch],
        include_ignored: bool,
    ) -> SourceCleanupResult:
        candidates = await _cleanup_candidates(
            session,
            job,
            matches,
            include_ignored=include_ignored,
        )
        if not candidates:
            return SourceCleanupResult()

        safe_candidates = [
            item for item in candidates if _is_safe_cleanup_item(item, job)
        ]
        safety_skipped = len(candidates) - len(safe_candidates)
        operations, existing_skipped = await _prepare_operations(
            session,
            job,
            safe_candidates,
        )
        result = SourceCleanupResult(skipped=safety_skipped + existing_skipped)
        if not operations:
            return result

        record_job_progress(
            session,
            job,
            stage=ProgressStage.CLEANUP,
            state=ProgressState.RUNNING,
            total=len(operations),
            skipped=result.skipped,
            operation_type=OperationType.TRASH,
            current_filename=_operation_filename(operations[0].operation),
            message=f"将 {len(operations)} 个源文件移入回收站",
        )
        await session.commit()

        completed = 0
        failed = 0
        for batch_start in range(0, len(operations), MAX_TRASH_BATCH_SIZE):
            batch = operations[batch_start : batch_start + MAX_TRASH_BATCH_SIZE]
            batch_completed, batch_failed = await self._execute_batch(
                session,
                job,
                batch,
            )
            completed += batch_completed
            failed += batch_failed
            processed = completed + failed
            is_complete = processed >= len(operations)
            record_job_progress(
                session,
                job,
                stage=ProgressStage.CLEANUP,
                state=(
                    ProgressState.FAILED
                    if is_complete and failed
                    else ProgressState.COMPLETED
                    if is_complete
                    else ProgressState.RUNNING
                ),
                completed=processed,
                total=len(operations),
                succeeded=completed,
                failed=failed,
                skipped=result.skipped,
                operation_type=OperationType.TRASH,
                current_filename=_operation_filename(batch[-1].operation),
                message=f"源文件清理 {processed}/{len(operations)}",
            )
            await session.commit()

        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="SOURCE_CLEANUP_COMPLETED",
                message=(
                    f"源文件清理完成：{completed} 个已移入回收站，"
                    f"{failed} 个失败，{result.skipped} 个安全跳过"
                ),
                severity="warning" if failed else "info",
                details={
                    "completed": completed,
                    "failed": failed,
                    "skipped": result.skipped,
                    "recoverable": True,
                },
            )
        )
        await session.commit()
        return SourceCleanupResult(
            completed=completed,
            failed=failed,
            skipped=result.skipped,
        )

    async def _execute_batch(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        operations: list[_PreparedCleanupOperation],
    ) -> tuple[int, int]:
        file_ids = [prepared.file_id for prepared in operations]
        for prepared in operations:
            operation = prepared.operation
            operation.status = OperationStatus.RUNNING
            record_file_operation_progress(
                session,
                job,
                operation,
                details={
                    "recoverable": True,
                    "message": "正在移入光鸭回收站",
                },
            )
        await session.commit()

        try:
            task = await self._provider.trash_items(file_ids)
        except RuntimeError as error:
            _fail_operations(
                session,
                job,
                [prepared.operation for prepared in operations],
                error,
            )
            await session.commit()
            return 0, len(operations)

        for prepared in operations:
            operation = prepared.operation
            operation.provider_task_id = task.task_id
        await session.commit()

        try:
            await wait_for_provider_task(self._provider, task.task_id)
        except RuntimeError as error:
            _fail_operations(
                session,
                job,
                [prepared.operation for prepared in operations],
                error,
            )
            await session.commit()
            return 0, len(operations)

        for prepared in operations:
            operation = prepared.operation
            operation.status = OperationStatus.COMPLETED
            operation.error_message = None
            record_file_operation_progress(
                session,
                job,
                operation,
                details={
                    "recoverable": True,
                    "message": "已移入光鸭回收站",
                },
            )
        await session.commit()
        return len(operations), 0


async def _cleanup_candidates(
    session: AsyncSession,
    job: OrganizeJob,
    matches: list[MediaMatch],
    *,
    include_ignored: bool,
) -> list[SourceItem]:
    predicates = []
    if job.config.get("trash_organized_source_files", False):
        source_item_ids = {media_match.source_item_id for media_match in matches}
        if source_item_ids:
            predicates.append(
                or_(
                    SourceItem.id.in_(source_item_ids),
                    SourceItem.associated_media_item_id.in_(source_item_ids),
                )
            )
    if include_ignored and job.config.get("trash_ignored_source_files", False):
        predicates.append(
            (SourceItem.classification == SourceClassification.IGNORED)
            & (SourceItem.user_action != SourceAction.INCLUDE)
            & (SourceItem.is_directory.is_(False))
        )
    if not predicates:
        return []
    items = list(
        (
            await session.scalars(
                select(SourceItem).where(
                    SourceItem.job_id == job.id,
                    or_(*predicates),
                )
            )
        ).all()
    )
    deduplicated = {
        item.cloud_file_id: item for item in items if item.cloud_file_id
    }
    return sorted(deduplicated.values(), key=lambda item: item.relative_path.casefold())


async def _prepare_operations(
    session: AsyncSession,
    job: OrganizeJob,
    items: list[SourceItem],
) -> tuple[list[_PreparedCleanupOperation], int]:
    keyed_items = [
        (make_idempotency_key("trash-source", item.cloud_file_id), item)
        for item in items
    ]
    existing_keys = set(
        (
            await session.scalars(
                select(FileOperation.idempotency_key).where(
                    FileOperation.idempotency_key.in_(
                        [idempotency_key for idempotency_key, _ in keyed_items]
                    )
                )
            )
        ).all()
    )
    pending: list[tuple[FileOperation, SourceItem]] = []
    skipped = len(existing_keys)
    for idempotency_key, item in keyed_items:
        if idempotency_key in existing_keys:
            continue
        operation = FileOperation(
            job_id=job.id,
            source_item_id=item.id,
            operation_type=OperationType.TRASH,
            status=OperationStatus.PENDING,
            source_path=item.source_path,
            target_path="光鸭回收站",
            idempotency_key=idempotency_key,
        )
        session.add(operation)
        pending.append((operation, item))
    await session.flush()

    operations: list[_PreparedCleanupOperation] = []
    for operation, item in pending:
        record_file_operation_progress(
            session,
            job,
            operation,
            details={"recoverable": True},
        )
        operations.append(
            _PreparedCleanupOperation(
                operation=operation,
                file_id=item.cloud_file_id,
            )
        )
    return operations, skipped


def _is_safe_cleanup_item(item: SourceItem, job: OrganizeJob) -> bool:
    if item.is_directory or item.filter_reason in PROTECTED_FILTER_REASONS:
        return False
    if not _is_within(item.source_path, job.source_directory_path):
        return False
    if _is_within(item.source_path, job.target_directory_path):
        return False
    return "_整理中" not in PurePosixPath(item.source_path).parts


def _operation_filename(operation: FileOperation) -> str:
    return PurePosixPath(operation.source_path).name


def _is_within(path: str, root: str) -> bool:
    if not path or not root:
        return False
    try:
        PurePosixPath(path).relative_to(PurePosixPath(root))
    except ValueError:
        return False
    return True


def _fail_operations(
    session: AsyncSession,
    job: OrganizeJob,
    operations: list[FileOperation],
    error: Exception,
) -> None:
    reason = f"云盘回收站请求失败（{type(error).__name__}）"
    for operation in operations:
        operation.status = OperationStatus.FAILED
        operation.error_message = reason
        record_file_operation_progress(
            session,
            job,
            operation,
            details={"recoverable": True},
        )
