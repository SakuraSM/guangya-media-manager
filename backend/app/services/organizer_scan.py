from pathlib import PurePosixPath

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain import JobStatus, MatchDecision, MediaType
from app.models import AuditEvent, MediaMatch, OrganizeJob, SourceItem
from app.providers.base import CloudNode, CloudProvider
from app.services.media_parser import (
    ParsedMediaName,
    is_subtitle,
    is_supported_media,
    parse_media_filename,
)
from app.services.metadata import (
    AiRecognitionService,
    MetadataServiceError,
    TmdbService,
)
from app.services.organizer_support import (
    OrganizerError,
    candidate_to_dict,
    decide_match,
    fail_job,
    load_job,
    persist_metadata_candidate,
    read_config_float,
    target_path_for,
    update_job_state,
)

SCAN_PROGRESS = 0.12
IDENTIFY_PROGRESS = 0.36
READY_PROGRESS = 0.45
MAX_SCAN_DEPTH = 24


class ScanWorkflow:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: CloudProvider,
        tmdb_service: TmdbService,
        ai_service: AiRecognitionService,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._tmdb_service = tmdb_service
        self._ai_service = ai_service

    async def run(self, job_id: str) -> None:
        async with self._session_factory() as session:
            job = await load_job(session, job_id)
            if job.status not in {
                JobStatus.DRAFT,
                JobStatus.FAILED,
                JobStatus.REVIEW_REQUIRED,
            }:
                raise OrganizerError(f"Job {job_id} cannot be scanned from {job.status}")
            await session.execute(delete(SourceItem).where(SourceItem.job_id == job_id))
            await update_job_state(
                session,
                job,
                status=JobStatus.SCANNING,
                progress=SCAN_PROGRESS,
                stage="扫描源目录",
                event_type="SCAN_STARTED",
                message="开始递归扫描源目录",
            )
            try:
                cloud_nodes = await self._scan_directory_tree(
                    root_id=job.source_directory_id,
                    root_path=job.source_directory_path,
                )
                media_nodes = [
                    node
                    for node in cloud_nodes
                    if not node.is_directory and is_supported_media(node.name)
                ]
                subtitle_nodes = [
                    node
                    for node in cloud_nodes
                    if not node.is_directory and is_subtitle(node.name)
                ]
                await self._begin_identification(session, job, len(media_nodes))
                await self._identify_nodes(
                    session, job, media_nodes, subtitle_nodes
                )
            except (OrganizerError, MetadataServiceError, RuntimeError) as error:
                await fail_job(session, job, "扫描或识别失败", error)

    async def _scan_directory_tree(
        self, *, root_id: str, root_path: str
    ) -> list[CloudNode]:
        discovered: list[CloudNode] = []
        pending: list[tuple[str, str, int]] = [(root_id, root_path, 0)]
        while pending:
            parent_id, parent_path, depth = pending.pop()
            if depth > MAX_SCAN_DEPTH:
                raise OrganizerError("Directory nesting exceeds safe scan depth")
            nodes = await self._provider.list_directory(parent_id, parent_path)
            discovered.extend(nodes)
            pending.extend(
                (node.id, node.path, depth + 1) for node in nodes if node.is_directory
            )
        return discovered

    async def _begin_identification(
        self, session: AsyncSession, job: OrganizeJob, media_count: int
    ) -> None:
        job.total_items = media_count
        job.status = JobStatus.IDENTIFYING
        job.progress = IDENTIFY_PROGRESS
        job.current_stage = "识别影视信息"
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="IDENTIFY_STARTED",
                message=f"扫描完成，共发现 {media_count} 个视频文件",
            )
        )
        await session.commit()

    async def _identify_nodes(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        media_nodes: list[CloudNode],
        subtitle_nodes: list[CloudNode],
    ) -> None:
        auto_threshold = read_config_float(job.config, "auto_approve_threshold", 0.9)
        review_threshold = read_config_float(job.config, "review_threshold", 0.65)
        decisions: list[MatchDecision] = []
        for cloud_node in media_nodes:
            decision = await self._identify_node(
                session=session,
                job=job,
                cloud_node=cloud_node,
                auto_threshold=auto_threshold,
                review_threshold=review_threshold,
            )
            decisions.append(decision)
        await self._associate_subtitles(
            session, job, subtitle_nodes
        )
        await self._complete_identification(session, job, decisions)

    async def _associate_subtitles(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        subtitle_nodes: list[CloudNode],
    ) -> None:
        media_items = list(
            (
                await session.scalars(
                    select(SourceItem)
                    .join(MediaMatch)
                    .where(SourceItem.job_id == job.id)
                )
            ).all()
        )
        media_by_signature = {
            _media_signature(parse_media_filename(item.filename)): item
            for item in media_items
        }
        associated_count = 0
        for subtitle_node in subtitle_nodes:
            signature = _media_signature(
                parse_media_filename(subtitle_node.name)
            )
            media_item = media_by_signature.get(signature)
            session.add(
                SourceItem(
                    job_id=job.id,
                    cloud_file_id=subtitle_node.id,
                    parent_file_id=subtitle_node.parent_id,
                    source_path=subtitle_node.path,
                    filename=subtitle_node.name,
                    extension=PurePosixPath(subtitle_node.name).suffix,
                    size_bytes=subtitle_node.size_bytes,
                    fingerprint=subtitle_node.fingerprint,
                    associated_media_item_id=(
                        media_item.id if media_item is not None else None
                    ),
                    is_ignored=media_item is None,
                )
            )
            if media_item is not None:
                associated_count += 1
        if subtitle_nodes:
            session.add(
                AuditEvent(
                    job_id=job.id,
                    event_type="SUBTITLES_ASSOCIATED",
                    message=(
                        f"字幕关联完成：{associated_count}/"
                        f"{len(subtitle_nodes)}"
                    ),
                )
            )

    async def _identify_node(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        cloud_node: CloudNode,
        auto_threshold: float,
        review_threshold: float,
    ) -> MatchDecision:
        parsed = parse_media_filename(cloud_node.name)
        source_item = SourceItem(
            job_id=job.id,
            cloud_file_id=cloud_node.id,
            parent_file_id=cloud_node.parent_id,
            source_path=cloud_node.path,
            filename=cloud_node.name,
            extension=PurePosixPath(cloud_node.name).suffix,
            size_bytes=cloud_node.size_bytes,
            fingerprint=cloud_node.fingerprint,
            is_ignored=parsed.is_ignored,
        )
        session.add(source_item)
        await session.flush()
        if parsed.is_ignored:
            session.add(_ignored_match(source_item))
            return MatchDecision.IGNORED

        parsed = await self._ai_service.recognize(
            filename=cloud_node.name,
            parent_path=cloud_node.path,
            parsed=parsed,
        )
        candidates = await self._tmdb_service.search(parsed)
        decision, confidence = decide_match(
            candidates=candidates,
            auto_threshold=auto_threshold,
            review_threshold=review_threshold,
        )
        top_candidate = candidates[0] if candidates else None
        entity = (
            await persist_metadata_candidate(session, top_candidate) if top_candidate else None
        )
        target_path = (
            target_path_for(parsed, top_candidate, source_item.extension)
            if top_candidate
            else ""
        )
        session.add(
            MediaMatch(
                source_item_id=source_item.id,
                media_entity_id=entity.id if entity else None,
                media_type=parsed.media_type,
                parsed_title=parsed.title,
                parsed_year=parsed.year,
                season_number=parsed.season_number,
                episode_numbers=list(parsed.episode_numbers),
                edition=parsed.edition,
                confidence=confidence,
                decision=decision,
                candidates=[candidate_to_dict(candidate) for candidate in candidates],
                target_path=target_path,
                reason_codes=list(parsed.reason_codes),
            )
        )
        return decision

    async def _complete_identification(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        decisions: list[MatchDecision],
    ) -> None:
        job.approved_items = decisions.count(MatchDecision.AUTO_APPROVED)
        job.review_items = decisions.count(MatchDecision.REVIEW)
        job.failed_items = decisions.count(MatchDecision.UNRESOLVED)
        job.status = (
            JobStatus.REVIEW_REQUIRED
            if job.review_items or job.failed_items
            else JobStatus.READY
        )
        job.progress = READY_PROGRESS
        job.current_stage = "等待审核" if job.status == JobStatus.REVIEW_REQUIRED else "可以执行"
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="IDENTIFY_COMPLETED",
                message=(
                    f"识别完成：{job.approved_items} 自动通过，"
                    f"{job.review_items} 待审核"
                ),
            )
        )
        await session.commit()


def _ignored_match(source_item: SourceItem) -> MediaMatch:
    return MediaMatch(
        source_item_id=source_item.id,
        media_type=MediaType.UNKNOWN,
        parsed_title="",
        confidence=0,
        decision=MatchDecision.IGNORED,
        reason_codes=["IGNORED_SAMPLE"],
    )


def _media_signature(parsed: ParsedMediaName) -> tuple[object, ...]:
    return (
        parsed.media_type,
        parsed.title.casefold(),
        parsed.year,
        parsed.season_number,
        parsed.episode_numbers,
    )
