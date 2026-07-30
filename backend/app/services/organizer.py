from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.domain import JobStatus, MatchDecision
from app.models import AuditEvent, MediaMatch, OrganizeJob, SourceItem
from app.providers.base import CloudProvider
from app.schemas import (
    BatchApproveMatchesRequest,
    CreateJobRequest,
    ManualMatchRequest,
    UpdateMatchRequest,
)
from app.schemas import MatchCandidate as MatchCandidateSchema
from app.services.media_parser import ParsedMediaName, parse_media_filename
from app.services.metadata import (
    AiRecognitionService,
    MetadataCandidate,
    MetadataResolutionRequest,
    MetadataResolver,
    TmdbService,
)
from app.services.naming import NamingInput, build_target_relative_path
from app.services.organizer_execute import ExecutionWorkflow
from app.services.organizer_scan import ScanWorkflow
from app.services.organizer_support import (
    OrganizerError,
    candidate_to_dict,
    decide_match,
    find_candidate,
    load_job,
    persist_candidate_payload,
    persist_metadata_candidate,
    read_config_float,
    target_path_for,
    validate_candidate,
)

__all__ = ["OrganizerError", "OrganizerService"]

EDITABLE_JOB_STATUSES = {
    JobStatus.REVIEW_REQUIRED,
    JobStatus.READY,
    JobStatus.FAILED,
}
ACTIVE_JOB_STATUSES = {
    JobStatus.SCANNING,
    JobStatus.IDENTIFYING,
    JobStatus.COPYING,
    JobStatus.SCRAPING,
    JobStatus.FINALIZING,
}


class OrganizerService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: CloudProvider,
        tmdb_service: TmdbService,
        ai_service: AiRecognitionService,
    ) -> None:
        self._scan_workflow = ScanWorkflow(
            session_factory=session_factory,
            provider=provider,
            tmdb_service=tmdb_service,
            ai_service=ai_service,
        )
        self._execution_workflow = ExecutionWorkflow(
            session_factory=session_factory,
            provider=provider,
            tmdb_service=tmdb_service,
        )
        self._metadata_resolver = MetadataResolver(
            tmdb_service=tmdb_service,
            ai_service=ai_service,
        )

    async def create_job(
        self, request: CreateJobRequest, session: AsyncSession
    ) -> OrganizeJob:
        job = OrganizeJob(
            name=request.name,
            source_directory_id=request.source_directory_id,
            source_directory_path=request.source_directory_path,
            target_directory_id=request.target_directory_id,
            target_directory_path=request.target_directory_path,
            config=request.config.model_dump(),
        )
        session.add(job)
        session.add(
            AuditEvent(
                job=job,
                event_type="JOB_CREATED",
                message=f"创建整理任务：{request.name}",
            )
        )
        await session.commit()
        await session.refresh(job)
        return job

    async def run_action(self, action: str, job_id: str) -> None:
        if action == "scan":
            await self._scan_workflow.run(job_id)
            return
        if action == "execute":
            await self._execution_workflow.run(job_id)
            return
        raise OrganizerError(f"Unsupported job action: {action}")

    async def update_match(
        self,
        *,
        job_id: str,
        match_id: str,
        request: UpdateMatchRequest,
        session: AsyncSession,
    ) -> MediaMatch:
        media_match, _ = await self._load_editable_match(
            session=session,
            job_id=job_id,
            match_id=match_id,
        )

        if request.candidate_tmdb_id is not None:
            candidate = find_candidate(media_match.candidates, request.candidate_tmdb_id)
            if candidate is None:
                raise OrganizerError("Candidate not found")
            entity = await persist_candidate_payload(session, candidate)
            candidate_schema = validate_candidate(candidate)
            media_match.media_entity_id = entity.id
            media_match.confidence = candidate_schema.score
            media_match.target_path = _target_path_for_candidate(
                media_match, candidate_schema
            )

        media_match.decision = request.decision
        session.add(
            AuditEvent(
                job_id=job_id,
                event_type="MATCH_UPDATED",
                message=f"更新匹配决策：{media_match.source_item.filename}",
            )
        )
        await session.commit()
        await session.refresh(media_match)
        await self._refresh_job_readiness(session, job_id)
        return media_match

    async def approve_matches(
        self,
        *,
        job_id: str,
        request: BatchApproveMatchesRequest,
        session: AsyncSession,
    ) -> int:
        job = await load_job(session, job_id)
        if job.status not in EDITABLE_JOB_STATUSES:
            raise OrganizerError("当前任务状态不能批量批准")
        match_ids = [item.match_id for item in request.items]
        if len(match_ids) != len(set(match_ids)):
            raise OrganizerError("批量批准包含重复记录")
        matches = list(
            (
                await session.scalars(
                    select(MediaMatch)
                    .join(SourceItem)
                    .options(selectinload(MediaMatch.source_item))
                    .where(
                        SourceItem.job_id == job_id,
                        MediaMatch.id.in_(match_ids),
                    )
                )
            ).all()
        )
        if len(matches) != len(match_ids):
            raise OrganizerError("部分匹配记录不存在")
        matches_by_id = {media_match.id: media_match for media_match in matches}
        approval_candidates: list[tuple[MediaMatch, dict[str, object]]] = []
        for item in request.items:
            media_match = matches_by_id[item.match_id]
            candidate = find_candidate(
                media_match.candidates,
                item.candidate_tmdb_id,
            )
            if candidate is None:
                raise OrganizerError(
                    f"文件 {media_match.source_item.filename} 的候选不存在"
                )
            approval_candidates.append((media_match, candidate))
        for media_match, candidate in approval_candidates:
            entity = await persist_candidate_payload(session, candidate)
            candidate_schema = validate_candidate(candidate)
            media_match.media_entity_id = entity.id
            media_match.confidence = candidate_schema.score
            media_match.target_path = _target_path_for_candidate(
                media_match,
                candidate_schema,
            )
            media_match.decision = MatchDecision.APPROVED
        session.add(
            AuditEvent(
                job_id=job_id,
                event_type="MATCHES_BATCH_APPROVED",
                message=f"批量批准 {len(matches)} 条匹配记录",
            )
        )
        await session.commit()
        await self._refresh_job_readiness(session, job_id)
        return len(matches)

    async def update_group_matches(
        self,
        *,
        job_id: str,
        group_key: str,
        request: UpdateMatchRequest,
        session: AsyncSession,
    ) -> int:
        job = await load_job(session, job_id)
        if job.status not in EDITABLE_JOB_STATUSES:
            raise OrganizerError("当前任务状态不能批量修改")
        matches = list(
            (
                await session.scalars(
                    select(MediaMatch)
                    .join(SourceItem)
                    .options(selectinload(MediaMatch.source_item))
                    .where(
                        SourceItem.job_id == job_id,
                        MediaMatch.group_key == group_key,
                    )
                )
            ).all()
        )
        if not matches:
            raise OrganizerError("Media group not found")

        validated_candidates: list[
            tuple[MediaMatch, dict[str, object] | None]
        ] = []
        for media_match in matches:
            candidate = (
                find_candidate(
                    media_match.candidates,
                    request.candidate_tmdb_id,
                )
                if request.candidate_tmdb_id is not None
                else None
            )
            if request.candidate_tmdb_id is not None and candidate is None:
                raise OrganizerError(
                    f"文件 {media_match.source_item.filename} 的候选不存在"
                )
            validated_candidates.append((media_match, candidate))

        for media_match, candidate in validated_candidates:
            if candidate is not None:
                entity = await persist_candidate_payload(session, candidate)
                candidate_schema = validate_candidate(candidate)
                media_match.media_entity_id = entity.id
                media_match.confidence = candidate_schema.score
                media_match.target_path = _target_path_for_candidate(
                    media_match,
                    candidate_schema,
                )
            media_match.decision = request.decision
        session.add(
            AuditEvent(
                job_id=job_id,
                event_type="MEDIA_GROUP_UPDATED",
                message=f"批量更新媒体分组，共 {len(matches)} 条记录",
            )
        )
        await session.commit()
        await self._refresh_job_readiness(session, job_id)
        return len(matches)

    async def retry_match(
        self,
        *,
        job_id: str,
        match_id: str,
        session: AsyncSession,
    ) -> MediaMatch:
        media_match, job = await self._load_editable_match(
            session=session,
            job_id=job_id,
            match_id=match_id,
        )
        parent_path = str(PurePosixPath(media_match.source_item.source_path).parent)
        parsed = parse_media_filename(
            media_match.source_item.filename,
            parent_path=parent_path,
            source_root=job.source_directory_path,
        )
        resolution = await self._metadata_resolver.resolve(
            MetadataResolutionRequest(
                filename=media_match.source_item.filename,
                parent_path=str(
                    PurePosixPath(media_match.source_item.relative_path).parent
                ),
                parsed=parsed,
            )
        )
        parsed = resolution.parsed
        candidates = list(resolution.candidates)
        decision, confidence = decide_match(
            candidates=candidates,
            auto_threshold=read_config_float(
                job.config, "auto_approve_threshold", 0.9
            ),
            review_threshold=read_config_float(
                job.config, "review_threshold", 0.65
            ),
        )
        if resolution.requires_manual_confirmation and candidates:
            decision = MatchDecision.REVIEW
        top_candidate = candidates[0] if candidates else None
        entity = (
            await persist_metadata_candidate(session, top_candidate)
            if top_candidate is not None
            else None
        )
        media_match.media_entity_id = entity.id if entity is not None else None
        media_match.media_type = parsed.media_type
        media_match.parsed_title = parsed.title
        media_match.parsed_year = parsed.year
        media_match.season_number = parsed.season_number
        media_match.episode_numbers = list(parsed.episode_numbers)
        media_match.edition = parsed.edition
        media_match.confidence = confidence
        media_match.decision = decision
        media_match.candidates = [
            candidate_to_dict(candidate) for candidate in candidates
        ]
        media_match.target_path = (
            target_path_for(
                parsed,
                top_candidate,
                media_match.source_item.extension,
                episode_title=media_match.episode_title,
            )
            if top_candidate is not None
            else ""
        )
        media_match.reason_codes = list(
            dict.fromkeys((*parsed.reason_codes, "SINGLE_ITEM_RETRIED"))
        )
        session.add(
            AuditEvent(
                job_id=job_id,
                event_type="MATCH_RETRIED",
                message=f"重新识别文件：{media_match.source_item.filename}",
                severity="warning" if not candidates else "info",
            )
        )
        await session.commit()
        await self._refresh_job_readiness(session, job_id)
        return media_match

    async def apply_manual_match(
        self,
        *,
        job_id: str,
        match_id: str,
        request: ManualMatchRequest,
        session: AsyncSession,
    ) -> MediaMatch:
        media_match, _ = await self._load_editable_match(
            session=session,
            job_id=job_id,
            match_id=match_id,
        )
        candidate = MetadataCandidate(
            tmdb_id=request.tmdb_id,
            title=request.title,
            original_title=request.original_title or request.title,
            year=request.year,
            media_type=request.media_type,
            score=1,
            poster_url=None,
            backdrop_url=None,
            overview="",
        )
        entity = await persist_metadata_candidate(session, candidate)
        entity.title = request.title
        entity.original_title = request.original_title or request.title
        entity.year = request.year
        media_match.media_entity_id = entity.id
        media_match.media_type = request.media_type
        media_match.parsed_title = request.title
        media_match.parsed_year = request.year
        media_match.confidence = 1
        media_match.decision = MatchDecision.APPROVED
        media_match.candidates = [candidate_to_dict(candidate)]
        media_match.target_path = _target_path_for_candidate(
            media_match,
            validate_candidate(candidate_to_dict(candidate)),
        )
        media_match.reason_codes = list(
            dict.fromkeys((*media_match.reason_codes, "MANUAL_MATCH"))
        )
        session.add(
            AuditEvent(
                job_id=job_id,
                event_type="MATCH_MANUALLY_ASSIGNED",
                message=f"手动匹配文件：{media_match.source_item.filename}",
            )
        )
        await session.commit()
        await self._refresh_job_readiness(session, job_id)
        return media_match

    async def request_cancel(
        self, job: OrganizeJob, session: AsyncSession
    ) -> OrganizeJob:
        if job.status in {
            JobStatus.COMPLETED,
            JobStatus.PARTIAL_FAILED,
            JobStatus.FAILED,
            JobStatus.CANCELED,
        }:
            raise OrganizerError("当前任务已经结束，不能取消")
        job.is_cancel_requested = True
        is_active = job.status in ACTIVE_JOB_STATUSES
        if not is_active:
            job.status = JobStatus.CANCELED
            job.current_stage = "已取消，未执行后续操作"
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="CANCEL_REQUESTED",
                message=(
                    "已请求安全停止任务，当前操作结束后生效"
                    if is_active
                    else "任务已取消，未执行后续操作"
                ),
                severity="warning",
            )
        )
        await session.commit()
        await session.refresh(job)
        return job

    async def _load_editable_match(
        self,
        *,
        session: AsyncSession,
        job_id: str,
        match_id: str,
    ) -> tuple[MediaMatch, OrganizeJob]:
        job = await load_job(session, job_id)
        if job.status not in EDITABLE_JOB_STATUSES:
            raise OrganizerError("当前任务状态不能修改匹配结果")
        statement = (
            select(MediaMatch)
            .join(SourceItem)
            .options(selectinload(MediaMatch.source_item))
            .where(MediaMatch.id == match_id, SourceItem.job_id == job_id)
        )
        media_match = await session.scalar(statement)
        if media_match is None:
            raise OrganizerError("Match not found")
        return media_match, job

    async def _refresh_job_readiness(self, session: AsyncSession, job_id: str) -> None:
        matches = (
            await session.scalars(
                select(MediaMatch).join(SourceItem).where(SourceItem.job_id == job_id)
            )
        ).all()
        job = await load_job(session, job_id)
        review_items = sum(match.decision == MatchDecision.REVIEW for match in matches)
        unresolved_items = sum(match.decision == MatchDecision.UNRESOLVED for match in matches)
        approved_items = sum(
            match.decision in {MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED}
            for match in matches
        )
        job.review_items = review_items + unresolved_items
        job.approved_items = approved_items
        job.failed_items = 0
        job.status = (
            JobStatus.READY
            if review_items + unresolved_items == 0
            else JobStatus.REVIEW_REQUIRED
        )
        job.current_stage = "可以执行" if job.status == JobStatus.READY else "等待审核"
        await session.commit()


def _target_path_for_candidate(
    media_match: MediaMatch, candidate: MatchCandidateSchema
) -> str:
    parsed_from_filename = parse_media_filename(media_match.source_item.filename)
    quality_tags_value = media_match.release_info.get("quality_tags", [])
    quality_tags = (
        tuple(item for item in quality_tags_value if isinstance(item, str))
        if isinstance(quality_tags_value, list)
        else ()
    )
    release_group_value = media_match.release_info.get("release_group", "")
    release_group = (
        release_group_value if isinstance(release_group_value, str) else ""
    )
    parsed = ParsedMediaName(
        media_type=media_match.media_type,
        title=media_match.parsed_title,
        year=media_match.parsed_year,
        season_number=media_match.season_number,
        episode_numbers=tuple(media_match.episode_numbers),
        edition=media_match.edition,
        confidence=media_match.confidence,
        reason_codes=tuple(media_match.reason_codes),
        is_ignored=False,
        episode_date=media_match.episode_date,
        quality_tags=quality_tags,
        release_group=release_group,
        part_number=parsed_from_filename.part_number,
        context_group=media_match.group_key,
    )
    return build_target_relative_path(
        NamingInput(
            title=candidate.title,
            year=candidate.year,
            parsed=parsed,
            extension=media_match.source_item.extension,
            episode_title=media_match.episode_title,
        )
    )
