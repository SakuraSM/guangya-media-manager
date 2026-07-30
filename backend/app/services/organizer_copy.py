import asyncio
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import OperationStatus, OperationType
from app.models import FileOperation, OrganizeJob, SourceItem
from app.providers.base import CloudNode, CloudProvider
from app.services.organizer_cloud import wait_for_provider_task
from app.services.organizer_support import make_idempotency_key

RESULT_RESOLVE_DELAYS_SECONDS = (0.25, 0.5, 1.0)


@dataclass(frozen=True, slots=True)
class CopyPlanItem:
    source_item: SourceItem
    target_directory: CloudNode
    final_filename: str


@dataclass(frozen=True, slots=True)
class CopyItemResult:
    source_item_id: str
    succeeded: bool
    copied_bytes: int = 0
    error_message: str | None = None


@dataclass(slots=True)
class _PreparedCopy:
    plan: CopyPlanItem
    operation: FileOperation


class CopyExecutor:
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider

    async def execute_plan(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        items: list[CopyPlanItem],
        should_stop: Callable[[], Awaitable[bool]] | None = None,
    ) -> list[CopyItemResult]:
        """Execute the frozen plan in directory batches instead of per-file copies."""
        results: list[CopyItemResult] = []
        grouped_items: defaultdict[str, list[CopyPlanItem]] = defaultdict(list)
        for item in items:
            grouped_items[item.target_directory.id].append(item)

        for group in grouped_items.values():
            group_results = await self._execute_directory_batch(
                session=session,
                job=job,
                items=group,
            )
            results.extend(group_results)
            if should_stop is not None and await should_stop():
                break
        return results

    async def _execute_directory_batch(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        items: list[CopyPlanItem],
    ) -> list[CopyItemResult]:
        target_directory = items[0].target_directory
        existing_nodes = await self._provider.list_directory(
            target_directory.id,
            target_directory.path,
        )
        filename_counts = Counter(item.final_filename for item in items)
        prepared: list[_PreparedCopy] = []
        results: list[CopyItemResult] = []

        for plan_item in items:
            operation = await self._load_or_create_operation(
                session,
                job,
                plan_item,
            )
            if operation.status == OperationStatus.COMPLETED:
                results.append(
                    CopyItemResult(
                        source_item_id=plan_item.source_item.id,
                        succeeded=True,
                    )
                )
                continue
            if filename_counts[plan_item.final_filename] > 1:
                results.append(
                    self._fail_operation(
                        operation,
                        plan_item,
                        "审核计划中存在重复目标文件名，请调整匹配或版本标签",
                    )
                )
                continue

            recovered_node = await self._recover_previous_copy(
                operation,
                plan_item,
                existing_nodes,
            )
            if recovered_node is not None:
                results.append(
                    await self._finish_copy(
                        session,
                        operation,
                        plan_item,
                        recovered_node,
                        copied_bytes=plan_item.source_item.size_bytes,
                    )
                )
                continue

            final_node = _find_by_name(existing_nodes, plan_item.final_filename)
            if final_node is not None:
                if _same_fingerprint(plan_item.source_item, final_node):
                    operation.status = OperationStatus.SKIPPED
                    operation.error_message = None
                    results.append(
                        CopyItemResult(
                            source_item_id=plan_item.source_item.id,
                            succeeded=True,
                        )
                    )
                else:
                    results.append(
                        self._fail_operation(
                            operation,
                            plan_item,
                            "目标文件已存在且无法确认内容一致",
                        )
                    )
                continue

            operation.status = OperationStatus.RUNNING
            operation.error_message = None
            prepared.append(_PreparedCopy(plan=plan_item, operation=operation))

        await session.commit()
        if not prepared:
            return results

        before_ids = {node.id for node in existing_nodes}
        try:
            task = await self._provider.copy_items(
                [item.plan.source_item.cloud_file_id for item in prepared],
                target_directory.id,
            )
            for prepared_item in prepared:
                prepared_item.operation.provider_task_id = task.task_id
            await session.commit()
            await wait_for_provider_task(self._provider, task.task_id)
            copied_nodes = await self._resolve_copied_nodes(
                task.task_id,
                target_directory,
                before_ids,
            )
        except (RuntimeError, TimeoutError) as error:
            reason = _safe_batch_error(error)
            for prepared_item in prepared:
                results.append(
                    self._fail_operation(
                        prepared_item.operation,
                        prepared_item.plan,
                        reason,
                    )
                )
            await session.commit()
            return results

        resolved, unresolved = _match_copied_nodes(prepared, copied_nodes)
        for prepared_item, copied_node in resolved:
            try:
                results.append(
                    await self._finish_copy(
                        session,
                        prepared_item.operation,
                        prepared_item.plan,
                        copied_node,
                        copied_bytes=prepared_item.plan.source_item.size_bytes,
                    )
                )
            except RuntimeError as error:
                results.append(
                    self._fail_operation(
                        prepared_item.operation,
                        prepared_item.plan,
                        f"复制完成但重命名失败：{type(error).__name__}",
                    )
                )
        for prepared_item in unresolved:
            results.append(
                self._fail_operation(
                    prepared_item.operation,
                    prepared_item.plan,
                    "复制任务已完成，但无法在目标目录认领对应文件",
                )
            )
        await session.commit()
        return results

    async def _load_or_create_operation(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        item: CopyPlanItem,
    ) -> FileOperation:
        target_path = f"{item.target_directory.path.rstrip('/')}/{item.final_filename}"
        idempotency_key = make_idempotency_key(
            "copy",
            job.id,
            item.source_item.id,
            target_path,
        )
        operation = await session.scalar(
            select(FileOperation).where(FileOperation.idempotency_key == idempotency_key)
        )
        if operation is None:
            operation = FileOperation(
                job_id=job.id,
                source_item_id=item.source_item.id,
                operation_type=OperationType.COPY,
                source_path=item.source_item.source_path,
                target_path=target_path,
                idempotency_key=idempotency_key,
            )
            session.add(operation)
        return operation

    async def _recover_previous_copy(
        self,
        operation: FileOperation,
        item: CopyPlanItem,
        existing_nodes: list[CloudNode],
    ) -> CloudNode | None:
        if not operation.provider_task_id:
            return None
        adoptable_names = {
            item.source_item.filename,
            item.final_filename,
        }
        source_named_nodes = [
            node
            for node in existing_nodes
            if node.name in adoptable_names and _same_source_file(item.source_item, node)
        ]
        if len(source_named_nodes) != 1:
            return None
        try:
            if not await self._provider.task_is_complete(operation.provider_task_id):
                return None
        except RuntimeError:
            # The unofficial result/status endpoints can forget completed tasks.
            # A unique same-name, same-size/fingerprint file is still safe to adopt
            # because this operation has a recorded provider task id.
            pass
        return source_named_nodes[0]

    async def _resolve_copied_nodes(
        self,
        task_id: str,
        target_directory: CloudNode,
        before_ids: set[str],
    ) -> list[CloudNode]:
        resolved: list[CloudNode] = []
        for delay in RESULT_RESOLVE_DELAYS_SECONDS:
            try:
                resolved = await self._provider.resolve_task_nodes(
                    task_id,
                    target_directory.path,
                )
            except RuntimeError:
                resolved = []
            if resolved:
                return resolved
            await asyncio.sleep(delay)

        directory_nodes = await self._provider.list_directory(
            target_directory.id,
            target_directory.path,
        )
        return [node for node in directory_nodes if node.id not in before_ids]

    async def _finish_copy(
        self,
        session: AsyncSession,
        operation: FileOperation,
        item: CopyPlanItem,
        copied_node: CloudNode,
        *,
        copied_bytes: int,
    ) -> CopyItemResult:
        target_path = f"{item.target_directory.path.rstrip('/')}/{item.final_filename}"
        if copied_node.name != item.final_filename:
            await self._provider.rename_item(copied_node.id, item.final_filename)
            session.add(
                FileOperation(
                    job_id=operation.job_id,
                    source_item_id=item.source_item.id,
                    operation_type=OperationType.RENAME,
                    source_path=copied_node.path,
                    target_path=target_path,
                    status=OperationStatus.COMPLETED,
                    idempotency_key=make_idempotency_key(
                        "rename",
                        operation.job_id,
                        item.source_item.id,
                        item.final_filename,
                    ),
                )
            )
        operation.status = OperationStatus.COMPLETED
        operation.error_message = None
        await session.flush()
        return CopyItemResult(
            source_item_id=item.source_item.id,
            succeeded=True,
            copied_bytes=copied_bytes,
        )

    def _fail_operation(
        self,
        operation: FileOperation,
        item: CopyPlanItem,
        reason: str,
    ) -> CopyItemResult:
        operation.status = OperationStatus.FAILED
        operation.error_message = reason
        return CopyItemResult(
            source_item_id=item.source_item.id,
            succeeded=False,
            error_message=reason,
        )


def _find_by_name(nodes: list[CloudNode], filename: str) -> CloudNode | None:
    return next((node for node in nodes if node.name == filename), None)


def _same_fingerprint(source: SourceItem, target: CloudNode) -> bool:
    return bool(
        source.fingerprint and target.fingerprint and source.fingerprint == target.fingerprint
    )


def _same_source_file(source: SourceItem, target: CloudNode) -> bool:
    if _same_fingerprint(source, target):
        return True
    return bool(source.size_bytes and source.size_bytes == target.size_bytes)


def _match_copied_nodes(
    prepared: list[_PreparedCopy],
    copied_nodes: list[CloudNode],
) -> tuple[list[tuple[_PreparedCopy, CloudNode]], list[_PreparedCopy]]:
    remaining_nodes = list(copied_nodes)
    resolved: list[tuple[_PreparedCopy, CloudNode]] = []
    unresolved: list[_PreparedCopy] = []

    for item in prepared:
        candidates = [
            node for node in remaining_nodes if node.name == item.plan.source_item.filename
        ]
        if len(candidates) != 1:
            candidates = [
                node for node in remaining_nodes if _same_fingerprint(item.plan.source_item, node)
            ]
        if len(candidates) != 1:
            candidates = [
                node
                for node in remaining_nodes
                if item.plan.source_item.size_bytes
                and node.size_bytes == item.plan.source_item.size_bytes
            ]
        if len(candidates) != 1:
            unresolved.append(item)
            continue
        copied_node = candidates[0]
        remaining_nodes.remove(copied_node)
        resolved.append((item, copied_node))
    return resolved, unresolved


def _safe_batch_error(error: Exception) -> str:
    return f"云端批量复制失败：{type(error).__name__}"
