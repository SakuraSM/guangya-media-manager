from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.domain import (
    JobStatus,
    MatchDecision,
    OperationStatus,
    OperationType,
    ProgressStage,
    ProgressState,
)
from app.models import AuditEvent, FileOperation, MediaMatch, OrganizeJob, SourceItem
from app.providers.base import CloudNode, CloudProvider
from app.services.metadata import TmdbService
from app.services.naming import build_subtitle_filename
from app.services.organizer_assets import AssetScraper
from app.services.organizer_cloud import (
    CloudLayout,
    MediaDirectories,
)
from app.services.organizer_copy import CopyExecutor, CopyItemResult, CopyPlanItem
from app.services.organizer_support import (
    OrganizerError,
    fail_job,
    load_job,
    make_idempotency_key,
)
from app.services.progress_events import record_job_progress

COPY_PROGRESS_START = 0.5
SCRAPE_PROGRESS = 0.88
FINALIZE_PROGRESS = 0.96


class ExecutionWorkflow:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: CloudProvider,
        tmdb_service: TmdbService,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._layout = CloudLayout(provider)
        self._asset_scraper = AssetScraper(provider, tmdb_service)
        self._copy_executor = CopyExecutor(provider)

    async def run(self, job_id: str) -> None:
        async with self._session_factory() as session:
            job = await load_job(session, job_id)
            if job.status not in {JobStatus.READY, JobStatus.PARTIAL_FAILED}:
                raise OrganizerError(f"Job {job_id} is not ready")
            if job.status == JobStatus.PARTIAL_FAILED:
                incomplete_copy_id = await session.scalar(
                    select(FileOperation.id).where(
                        FileOperation.job_id == job.id,
                        FileOperation.operation_type == OperationType.COPY,
                        FileOperation.status.in_([OperationStatus.FAILED, OperationStatus.RUNNING]),
                    )
                )
                if incomplete_copy_id is None:
                    raise OrganizerError("当前部分失败任务没有可重试的复制文件")
            matches = await self._load_executable_matches(session, job_id)
            if not matches:
                raise OrganizerError("No approved media matches")
            await self._begin_copy(session, job, len(matches))
            try:
                if await _is_cancel_requested(session, job.id):
                    await self._cancel_job(session, job)
                    return
                staging_directory = await self._layout.prepare_staging(job)
                media_directories = await self._layout.prepare_media_directories(
                    staging_directory, matches
                )
                copy_plan = await self._build_copy_plan(
                    session,
                    job,
                    matches,
                    media_directories,
                )
                job.current_stage = f"整批复制 {len(copy_plan)} 个文件"
                await session.commit()

                async def should_stop_copying() -> bool:
                    return await _is_cancel_requested(session, job.id)

                copy_results = await self._copy_executor.execute_plan(
                    session=session,
                    job=job,
                    items=copy_plan,
                    should_stop=should_stop_copying,
                )
                await self._record_copy_results(session, job, copy_results)
                if await _is_cancel_requested(session, job.id):
                    await self._cancel_job(session, job)
                    return
                failed_results = [result for result in copy_results if not result.succeeded]
                if failed_results:
                    await self._pause_after_copy_failures(
                        session,
                        job,
                        failed_results,
                    )
                    return
                warning_count = await self._scrape_metadata(
                    session, job, matches, media_directories
                )
                if await _is_cancel_requested(session, job.id):
                    await self._cancel_job(session, job)
                    return
                await self._finalize_job(session, job, staging_directory, warning_count)
            except (OrganizerError, RuntimeError) as error:
                await fail_job(session, job, "执行整理失败", error, partial=True)

    async def _begin_copy(self, session: AsyncSession, job: OrganizeJob, item_count: int) -> None:
        job.status = JobStatus.COPYING
        job.progress = COPY_PROGRESS_START
        job.current_stage = "准备整批执行"
        job.error_message = None
        job.failed_items = 0
        job.config = {
            key: value for key, value in job.config.items() if key != "_auto_execute_queued"
        }
        record_job_progress(
            session,
            job,
            stage=ProgressStage.COPY,
            state=ProgressState.RUNNING,
            total=item_count,
            message=job.current_stage,
        )
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="COPY_STARTED",
                message=f"冻结审核计划，开始整批执行 {item_count} 个媒体文件",
            )
        )
        await session.commit()

    async def _build_copy_plan(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        matches: list[MediaMatch],
        directories: dict[str, MediaDirectories],
    ) -> list[CopyPlanItem]:
        source_ids = [media_match.source_item.id for media_match in matches]
        subtitles = list(
            (
                await session.scalars(
                    select(SourceItem).where(SourceItem.associated_media_item_id.in_(source_ids))
                )
            ).all()
        )
        subtitles_by_media_id: dict[str, list[SourceItem]] = {}
        for subtitle in subtitles:
            if subtitle.associated_media_item_id is None:
                continue
            subtitles_by_media_id.setdefault(
                subtitle.associated_media_item_id,
                [],
            ).append(subtitle)

        plan: list[CopyPlanItem] = []
        for media_match in matches:
            source_item = media_match.source_item
            target_directory = directories[media_match.id].leaf
            plan.append(
                CopyPlanItem(
                    source_item=source_item,
                    target_directory=target_directory,
                    final_filename=PurePosixPath(media_match.target_path).name,
                )
            )
            for subtitle in subtitles_by_media_id.get(source_item.id, []):
                plan.append(
                    CopyPlanItem(
                        source_item=subtitle,
                        target_directory=target_directory,
                        final_filename=(
                            build_subtitle_filename(
                                media_match.target_path,
                                subtitle.filename,
                            )
                            if job.config.get("rename_subtitles", True)
                            else subtitle.filename
                        ),
                    )
                )
        return plan

    async def _record_copy_results(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        results: list[CopyItemResult],
    ) -> None:
        failed_results = [result for result in results if not result.succeeded]
        job.copied_bytes += sum(result.copied_bytes for result in results)
        job.failed_items = len(failed_results)
        job.progress = 0.82
        job.current_stage = (
            f"整批复制完成，{len(failed_results)} 个文件失败"
            if failed_results
            else f"整批复制完成，共 {len(results)} 个文件"
        )
        record_job_progress(
            session,
            job,
            stage=ProgressStage.COPY,
            state=(ProgressState.FAILED if failed_results else ProgressState.COMPLETED),
            completed=len(results),
            total=len(results),
            succeeded=len(results) - len(failed_results),
            failed=len(failed_results),
            message=job.current_stage,
        )
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="COPY_BATCH_COMPLETED",
                message=job.current_stage,
                severity="warning" if failed_results else "info",
                details={
                    "total": len(results),
                    "succeeded": len(results) - len(failed_results),
                    "failed": len(failed_results),
                },
            )
        )
        await session.commit()

    async def _pause_after_copy_failures(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        failed_results: list[CopyItemResult],
    ) -> None:
        job.status = JobStatus.PARTIAL_FAILED
        job.progress = 0.84
        job.current_stage = f"整批执行完成，{len(failed_results)} 个文件待重试"
        job.error_message = (
            f"{len(failed_results)} 个文件执行失败；已成功内容保留在暂存目录，未发布到正式目录"
        )
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="COPY_BATCH_PARTIAL_FAILED",
                message=job.current_stage,
                severity="warning",
                details={"failed": len(failed_results)},
            )
        )
        await session.commit()

    async def _scrape_metadata(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        matches: list[MediaMatch],
        directories: dict[str, MediaDirectories],
    ) -> int:
        job.status = JobStatus.SCRAPING
        job.progress = SCRAPE_PROGRESS
        job.current_stage = "生成 NFO 与媒体图片"
        record_job_progress(
            session,
            job,
            stage=ProgressStage.SCRAPE,
            state=ProgressState.RUNNING,
            total=len(matches),
            message=job.current_stage,
        )
        await session.commit()
        warning_count = await self._asset_scraper.scrape(session, job, matches, directories)
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="SCRAPE_COMPLETED",
                message="元数据文件生成完成",
            )
        )
        await session.commit()
        return warning_count

    async def _finalize_job(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        staging_directory: CloudNode,
        warning_count: int,
    ) -> None:
        job.status = JobStatus.FINALIZING
        job.progress = FINALIZE_PROGRESS
        job.current_stage = "完成目标目录"
        record_job_progress(
            session,
            job,
            stage=ProgressStage.FINALIZE,
            state=ProgressState.RUNNING,
            message=job.current_stage,
        )
        await session.commit()
        commit_result = await self._layout.commit_staging(
            staging_directory,
            job.target_directory_id,
            job.target_directory_path,
        )
        for move in commit_result.moves:
            session.add(
                FileOperation(
                    job_id=job.id,
                    operation_type=OperationType.MOVE,
                    source_path=move.source_path,
                    target_path=move.target_path,
                    status=OperationStatus.COMPLETED,
                    provider_task_id=move.task_id,
                    idempotency_key=make_idempotency_key("move", job.id, move.target_path),
                )
            )
        has_warnings = bool(commit_result.conflicts or warning_count)
        job.failed_items = 0
        job.error_message = None
        job.status = JobStatus.PARTIAL_FAILED if has_warnings else JobStatus.COMPLETED
        job.progress = 1
        job.current_stage = "整理完成，存在待处理项" if has_warnings else "整理完成"
        record_job_progress(
            session,
            job,
            stage=ProgressStage.FINALIZE,
            state=(ProgressState.FAILED if has_warnings else ProgressState.COMPLETED),
            completed=job.approved_items,
            total=job.approved_items,
            succeeded=job.approved_items,
            failed=warning_count + len(commit_result.conflicts),
            message=job.current_stage,
        )
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="JOB_COMPLETED",
                message=(
                    "整理任务已完成，部分冲突保留在暂存目录"
                    if commit_result.conflicts
                    else "整理任务已完成，源目录未修改"
                ),
                severity="warning" if has_warnings else "info",
                details={
                    "conflicts": commit_result.conflicts,
                    "duplicates": commit_result.duplicates,
                    "asset_warnings": warning_count,
                },
            )
        )
        await session.commit()

    async def _cancel_job(self, session: AsyncSession, job: OrganizeJob) -> None:
        job.status = JobStatus.CANCELED
        job.current_stage = "已停止，暂存文件已保留"
        record_job_progress(
            session,
            job,
            stage=ProgressStage.COPY,
            state=ProgressState.CANCELED,
            message=job.current_stage,
        )
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="JOB_CANCELED",
                message="任务已停止，暂存内容未删除",
                severity="warning",
            )
        )
        await session.commit()

    async def _load_executable_matches(
        self, session: AsyncSession, job_id: str
    ) -> list[MediaMatch]:
        statement = (
            select(MediaMatch)
            .join(SourceItem)
            .options(
                selectinload(MediaMatch.source_item),
                selectinload(MediaMatch.media_entity),
            )
            .where(
                SourceItem.job_id == job_id,
                MediaMatch.decision.in_([MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED]),
                MediaMatch.version_recommendation != "PENDING",
            )
        )
        return list((await session.scalars(statement)).all())


async def _is_cancel_requested(session: AsyncSession, job_id: str) -> bool:
    is_cancel_requested = await session.scalar(
        select(OrganizeJob.is_cancel_requested).where(OrganizeJob.id == job_id)
    )
    return bool(is_cancel_requested)
