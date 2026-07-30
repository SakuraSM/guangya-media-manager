from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.domain import (
    JobStatus,
    MatchDecision,
    OperationStatus,
    OperationType,
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
from app.services.organizer_copy import CopyExecutor
from app.services.organizer_support import (
    OrganizerError,
    fail_job,
    load_job,
    make_idempotency_key,
)

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
            if job.status != JobStatus.READY:
                raise OrganizerError(f"Job {job_id} is not ready")
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
                for item_index, media_match in enumerate(matches, start=1):
                    await self._copy_match(
                        session=session,
                        job=job,
                        media_match=media_match,
                        target_directory=media_directories[media_match.id].leaf,
                        item_index=item_index,
                        total_items=len(matches),
                    )
                    if await _is_cancel_requested(session, job.id):
                        await self._cancel_job(session, job)
                        return
                if await _is_cancel_requested(session, job.id):
                    await self._cancel_job(session, job)
                    return
                warning_count = await self._scrape_metadata(
                    session, job, matches, media_directories
                )
                if await _is_cancel_requested(session, job.id):
                    await self._cancel_job(session, job)
                    return
                await self._finalize_job(
                    session, job, staging_directory, warning_count
                )
            except (OrganizerError, RuntimeError) as error:
                await fail_job(session, job, "执行整理失败", error, partial=True)

    async def _begin_copy(
        self, session: AsyncSession, job: OrganizeJob, item_count: int
    ) -> None:
        job.status = JobStatus.COPYING
        job.progress = COPY_PROGRESS_START
        job.current_stage = "复制媒体文件"
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="COPY_STARTED",
                message=f"开始复制 {item_count} 个媒体文件",
            )
        )
        await session.commit()

    async def _copy_match(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        media_match: MediaMatch,
        target_directory: CloudNode,
        item_index: int,
        total_items: int,
    ) -> None:
        source_item = media_match.source_item
        final_filename = PurePosixPath(media_match.target_path).name
        media_copied = await self._copy_executor.copy_and_rename(
            session=session,
            job=job,
            source_item=source_item,
            target_directory=target_directory,
            final_filename=final_filename,
        )
        copied_bytes = source_item.size_bytes if media_copied else 0
        subtitles = list(
            (
                await session.scalars(
                    select(SourceItem).where(
                        SourceItem.associated_media_item_id == source_item.id
                    )
                )
            ).all()
        )
        for subtitle in subtitles:
            subtitle_copied = await self._copy_executor.copy_and_rename(
                session=session,
                job=job,
                source_item=subtitle,
                target_directory=target_directory,
                final_filename=(
                    build_subtitle_filename(
                        media_match.target_path, subtitle.filename
                    )
                    if job.config.get("rename_subtitles", True)
                    else subtitle.filename
                ),
            )
            if subtitle_copied:
                copied_bytes += subtitle.size_bytes
        job.copied_bytes += copied_bytes
        job.progress = COPY_PROGRESS_START + (item_index / total_items) * 0.32
        job.current_stage = f"复制媒体文件 {item_index}/{total_items}"
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
        await session.commit()
        warning_count = await self._asset_scraper.scrape(
            session, job, matches, directories
        )
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
                    idempotency_key=make_idempotency_key(
                        "move", job.id, move.target_path
                    ),
                )
            )
        has_warnings = bool(commit_result.conflicts or warning_count)
        job.status = (
            JobStatus.PARTIAL_FAILED if has_warnings else JobStatus.COMPLETED
        )
        job.progress = 1
        job.current_stage = (
            "整理完成，存在待处理项" if has_warnings else "整理完成"
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
                MediaMatch.decision.in_(
                    [MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED]
                ),
            )
        )
        return list((await session.scalars(statement)).all())


async def _is_cancel_requested(
    session: AsyncSession, job_id: str
) -> bool:
    is_cancel_requested = await session.scalar(
        select(OrganizeJob.is_cancel_requested).where(OrganizeJob.id == job_id)
    )
    return bool(is_cancel_requested)
