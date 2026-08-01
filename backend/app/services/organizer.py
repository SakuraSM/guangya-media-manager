from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.domain import JobStatus, MatchDecision, MediaType
from app.models import (
    AuditEvent,
    MediaMatch,
    MediaMatchEpisode,
    OrganizeJob,
    SourceItem,
)
from app.providers.base import CloudProvider
from app.schemas import (
    BatchApproveMatchesRequest,
    CreateJobRequest,
    ManualMatchPreview,
    ManualMatchRequest,
    UpdateMatchRequest,
)
from app.schemas import MatchCandidate as MatchCandidateSchema
from app.services.media_parser import (
    ParsedMediaName,
    parse_bare_episode_numbers,
    parse_media_filename,
)
from app.services.metadata import (
    AiRecognitionService,
    MetadataCandidate,
    MetadataResolutionRequest,
    MetadataResolver,
    MetadataServiceError,
    SeasonMetadata,
    TmdbService,
)
from app.services.naming import NamingInput, build_target_relative_path
from app.services.organizer_ai_review import AiReviewWorkflow
from app.services.organizer_execute import ExecutionWorkflow
from app.services.organizer_scan import ScanWorkflow, _persist_season_metadata
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


@dataclass(frozen=True, slots=True)
class ManualEpisodeMappingContext:
    media_match: MediaMatch
    request: ManualMatchRequest
    source_root: str


class OrganizerService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: CloudProvider,
        tmdb_service: TmdbService,
        ai_service: AiRecognitionService,
    ) -> None:
        self._session_factory = session_factory
        self._tmdb_service = tmdb_service
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
        self._ai_review_workflow = AiReviewWorkflow(
            session_factory=session_factory,
            ai_service=ai_service,
        )

    async def create_job(self, request: CreateJobRequest, session: AsyncSession) -> OrganizeJob:
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
            async with self._session_factory() as session:
                job = await load_job(session, job_id)
                should_auto_execute = job.status == JobStatus.READY and bool(
                    job.config.get(
                        "auto_execute_after_approval",
                        False,
                    )
                )
                if should_auto_execute:
                    session.add(
                        AuditEvent(
                            job_id=job.id,
                            event_type="AUTO_EXECUTE_STARTED",
                            message="审批已完成，自动开始整批整理",
                        )
                    )
                    await session.commit()
            if should_auto_execute:
                await self._execution_workflow.run(job_id)
            return
        if action == "execute":
            await self._execution_workflow.run(job_id)
            return
        if action == "ai_review":
            try:
                await self._ai_review_workflow.run(job_id)
            except Exception:
                async with self._session_factory() as session:
                    job = await load_job(session, job_id)
                    job.config = {
                        key: value
                        for key, value in job.config.items()
                        if key != "_ai_review_queued"
                    }
                    job.current_stage = "AI 审核中止，未完成项保持待审核"
                    session.add(
                        AuditEvent(
                            job_id=job.id,
                            event_type="AI_REVIEW_FAILED",
                            message="AI 审核异常中止，可稍后重试",
                            severity="error",
                        )
                    )
                    await session.commit()
                raise
            async with self._session_factory() as session:
                job = await load_job(session, job_id)
                should_auto_execute = job.status == JobStatus.READY and bool(
                    job.config.get("auto_execute_after_approval", False)
                )
                if should_auto_execute:
                    session.add(
                        AuditEvent(
                            job_id=job.id,
                            event_type="AUTO_EXECUTE_STARTED",
                            message="AI 审核完成，自动开始整批整理",
                        )
                    )
                    await session.commit()
            if should_auto_execute:
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
            media_match.target_path = _target_path_for_candidate(media_match, candidate_schema)

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
                raise OrganizerError(f"文件 {media_match.source_item.filename} 的候选不存在")
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

        validated_candidates: list[tuple[MediaMatch, dict[str, object] | None]] = []
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
                raise OrganizerError(f"文件 {media_match.source_item.filename} 的候选不存在")
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
        if media_match.episode_numbers:
            parsed = replace(
                parsed,
                media_type=media_match.media_type,
                season_number=media_match.season_number,
                episode_numbers=tuple(media_match.episode_numbers),
            )
        resolution = await self._metadata_resolver.resolve_tmdb_only(
            MetadataResolutionRequest(
                filename=media_match.source_item.filename,
                parent_path=str(PurePosixPath(media_match.source_item.relative_path).parent),
                parsed=parsed,
            )
        )
        parsed = resolution.parsed
        candidates = list(resolution.candidates)
        decision, confidence = decide_match(
            candidates=candidates,
            auto_threshold=read_config_float(job.config, "auto_approve_threshold", 0.9),
            review_threshold=read_config_float(job.config, "review_threshold", 0.65),
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
        media_match.candidates = [candidate_to_dict(candidate) for candidate in candidates]
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

    async def retry_group(
        self,
        *,
        job_id: str,
        group_key: str,
        session: AsyncSession,
    ) -> int:
        job = await load_job(session, job_id)
        if job.status not in EDITABLE_JOB_STATUSES:
            raise OrganizerError("当前任务状态不能重新识别分组")
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
                    .order_by(SourceItem.relative_path.asc())
                )
            ).all()
        )
        if not matches:
            raise OrganizerError("Media group not found")
        representative = matches[0]
        representative_parsed = parse_media_filename(
            representative.source_item.filename,
            parent_path=str(
                PurePosixPath(representative.source_item.source_path).parent
            ),
            source_root=job.source_directory_path,
        )
        resolution = await self._metadata_resolver.resolve(
            MetadataResolutionRequest(
                filename=representative.source_item.filename,
                parent_path=str(
                    PurePosixPath(representative.source_item.relative_path).parent
                ),
                parsed=representative_parsed,
                group_files=tuple(
                    media_match.source_item.relative_path
                    for media_match in matches
                ),
            )
        )
        candidates = list(resolution.candidates)
        decision, confidence = decide_match(
            candidates=candidates,
            auto_threshold=read_config_float(
                job.config,
                "auto_approve_threshold",
                0.9,
            ),
            review_threshold=read_config_float(
                job.config,
                "review_threshold",
                0.65,
            ),
        )
        if (
            resolution.requires_manual_confirmation
            or not job.config.get("auto_approve_enabled", True)
        ) and candidates:
            decision = MatchDecision.REVIEW
        top_candidate = candidates[0] if candidates else None
        entity = (
            await persist_metadata_candidate(session, top_candidate)
            if top_candidate is not None
            else None
        )
        for media_match in matches:
            parsed = parse_media_filename(
                media_match.source_item.filename,
                parent_path=str(
                    PurePosixPath(media_match.source_item.source_path).parent
                ),
                source_root=job.source_directory_path,
            )
            if media_match.episode_numbers:
                parsed = replace(
                    parsed,
                    media_type=media_match.media_type,
                    season_number=media_match.season_number,
                    episode_numbers=tuple(media_match.episode_numbers),
                )
            parsed = _merge_manual_group_context(parsed, resolution.parsed)
            media_match.media_entity_id = entity.id if entity is not None else None
            media_match.media_type = parsed.media_type
            media_match.parsed_title = parsed.title
            media_match.parsed_year = parsed.year
            media_match.confidence = confidence
            media_match.decision = decision
            media_match.candidates = [
                candidate_to_dict(candidate) for candidate in candidates
            ]
            media_match.reason_codes = list(
                dict.fromkeys(
                    (*parsed.reason_codes, "MEDIA_GROUP_RETRIED")
                )
            )
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
        session.add(
            AuditEvent(
                job_id=job_id,
                event_type="MEDIA_GROUP_RETRIED",
                message=f"重新识别影视分组，共 {len(matches)} 条记录",
                severity="warning" if not candidates else "info",
            )
        )
        await session.commit()
        await self._refresh_job_readiness(session, job_id)
        return len(matches)

    async def apply_manual_match(
        self,
        *,
        job_id: str,
        match_id: str,
        request: ManualMatchRequest,
        session: AsyncSession,
    ) -> MediaMatch:
        media_match, job = await self._load_editable_match(
            session=session,
            job_id=job_id,
            match_id=match_id,
        )
        candidate = await self._resolve_manual_candidate(request)
        season_number, episode_numbers = _manual_episode_mapping(
            ManualEpisodeMappingContext(
                media_match=media_match,
                request=request,
                source_root=job.source_directory_path,
            )
        )
        entity = await persist_metadata_candidate(session, candidate)
        media_match.media_entity_id = entity.id
        media_match.media_type = request.media_type
        media_match.parsed_title = candidate.title
        media_match.parsed_year = candidate.year
        media_match.season_number = season_number
        media_match.episode_numbers = list(episode_numbers)
        media_match.confidence = 1
        media_match.decision = MatchDecision.APPROVED
        media_match.candidates = [candidate_to_dict(candidate)]
        await session.execute(
            delete(MediaMatchEpisode).where(
                MediaMatchEpisode.media_match_id == media_match.id
            )
        )
        media_match.episode_title = ""
        if request.media_type == MediaType.TV:
            if season_number is None or not episode_numbers:
                raise OrganizerError("电视剧手动匹配必须填写季号和集号")
            try:
                season_metadata = await self._tmdb_service.get_tv_season(
                    request.tmdb_id,
                    season_number,
                )
            except MetadataServiceError:
                season_metadata = None
            _, episodes = await _persist_season_metadata(
                session,
                entity.id,
                season_number,
                episode_numbers,
                season_metadata,
            )
            media_match.episode_title = " / ".join(
                episode.name for episode in episodes if episode.name
            )
            await session.flush()
            session.add_all(
                MediaMatchEpisode(
                    media_match_id=media_match.id,
                    media_episode_id=episode.id,
                    ordinal=ordinal,
                )
                for ordinal, episode in enumerate(episodes)
            )
        media_match.target_path = _target_path_for_candidate(
            media_match,
            validate_candidate(candidate_to_dict(candidate)),
        )
        media_match.reason_codes = list(dict.fromkeys((*media_match.reason_codes, "MANUAL_MATCH")))
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

    async def apply_manual_group_match(
        self,
        *,
        job_id: str,
        match_id: str,
        request: ManualMatchRequest,
        session: AsyncSession,
    ) -> tuple[str, int]:
        anchor_match, job = await self._load_editable_match(
            session=session,
            job_id=job_id,
            match_id=match_id,
        )
        if request.media_type != MediaType.TV:
            raise OrganizerError("整组手动匹配仅适用于电视剧")
        if not anchor_match.group_key:
            raise OrganizerError("当前记录缺少影视分组，请重新扫描后再试")
        matches = list(
            (
                await session.scalars(
                    select(MediaMatch)
                    .join(SourceItem)
                    .options(selectinload(MediaMatch.source_item))
                    .where(
                        SourceItem.job_id == job_id,
                        MediaMatch.group_key == anchor_match.group_key,
                    )
                    .order_by(SourceItem.relative_path.asc())
                )
            ).all()
        )
        if not matches:
            raise OrganizerError("Media group not found")

        candidate = await self._resolve_manual_candidate(request)
        entity = await persist_metadata_candidate(session, candidate)
        group_key = "|".join(
            (
                MediaType.TV.value,
                candidate.title.casefold(),
                str(candidate.year or ""),
            )
        )
        season_cache: dict[int, SeasonMetadata | None] = {}
        mapped_items = 0
        for media_match in matches:
            season_number, episode_numbers = _group_episode_mapping(
                media_match=media_match,
                anchor_match_id=match_id,
                request=request,
                source_root=job.source_directory_path,
            )
            media_match.media_entity_id = entity.id
            media_match.media_type = MediaType.TV
            media_match.parsed_title = candidate.title
            media_match.parsed_year = candidate.year
            media_match.group_key = group_key
            media_match.source_item.group_key = group_key
            media_match.confidence = 1
            media_match.candidates = [candidate_to_dict(candidate)]
            media_match.season_number = season_number
            media_match.episode_numbers = list(episode_numbers)
            media_match.episode_title = ""
            await session.execute(
                delete(MediaMatchEpisode).where(
                    MediaMatchEpisode.media_match_id == media_match.id
                )
            )
            if season_number is None or not episode_numbers:
                media_match.decision = MatchDecision.REVIEW
                media_match.target_path = ""
                media_match.reason_codes = list(
                    dict.fromkeys(
                        (
                            *media_match.reason_codes,
                            "MANUAL_GROUP_MATCH",
                            "EPISODE_MAPPING_REQUIRED",
                        )
                    )
                )
                continue

            if season_number not in season_cache:
                try:
                    season_cache[season_number] = (
                        await self._tmdb_service.get_tv_season(
                            candidate.tmdb_id,
                            season_number,
                        )
                    )
                except MetadataServiceError:
                    season_cache[season_number] = None
            _, episodes = await _persist_season_metadata(
                session,
                entity.id,
                season_number,
                episode_numbers,
                season_cache[season_number],
            )
            media_match.episode_title = " / ".join(
                episode.name for episode in episodes if episode.name
            )
            media_match.decision = MatchDecision.APPROVED
            media_match.target_path = _target_path_for_candidate(
                media_match,
                validate_candidate(candidate_to_dict(candidate)),
            )
            media_match.reason_codes = list(
                dict.fromkeys(
                    (
                        *(
                            code
                            for code in media_match.reason_codes
                            if code != "EPISODE_MAPPING_REQUIRED"
                        ),
                        "MANUAL_GROUP_MATCH",
                    )
                )
            )
            await session.flush()
            session.add_all(
                MediaMatchEpisode(
                    media_match_id=media_match.id,
                    media_episode_id=episode.id,
                    ordinal=ordinal,
                )
                for ordinal, episode in enumerate(episodes)
            )
            mapped_items += 1

        unresolved_items = len(matches) - mapped_items
        session.add(
            AuditEvent(
                job_id=job_id,
                event_type="MEDIA_GROUP_MANUALLY_ASSIGNED",
                message=(
                    f"手动纠正整部剧集，共更新 {len(matches)} 条记录，"
                    f"{unresolved_items} 条需要补充季集编号"
                ),
                severity="warning" if unresolved_items else "info",
            )
        )
        await session.commit()
        await self._refresh_job_readiness(session, job_id)
        return group_key, len(matches)

    async def preview_manual_match(
        self,
        *,
        job_id: str,
        match_id: str,
        request: ManualMatchRequest,
        session: AsyncSession,
    ) -> ManualMatchPreview:
        media_match, job = await self._load_editable_match(
            session=session,
            job_id=job_id,
            match_id=match_id,
        )
        candidate = await self._resolve_manual_candidate(request)
        season_number, episode_numbers = _manual_episode_mapping(
            ManualEpisodeMappingContext(
                media_match=media_match,
                request=request,
                source_root=job.source_directory_path,
            )
        )
        parsed = parse_media_filename(
            media_match.source_item.filename,
            parent_path=str(PurePosixPath(media_match.source_item.source_path).parent),
            source_root=job.source_directory_path,
        )
        parsed = replace(
            parsed,
            media_type=request.media_type,
            title=candidate.title,
            year=candidate.year,
            season_number=season_number,
            episode_numbers=episode_numbers,
        )
        missing_episode_numbers: list[int] = []
        episode_title = ""
        if request.media_type == MediaType.TV:
            if season_number is None or not episode_numbers:
                raise OrganizerError("电视剧手动匹配必须填写季号和集号")
            try:
                season_metadata = await self._tmdb_service.get_tv_season(
                    request.tmdb_id,
                    season_number,
                )
            except MetadataServiceError:
                season_metadata = None
            metadata_by_number = (
                {
                    episode.episode_number: episode
                    for episode in season_metadata.episodes
                }
                if season_metadata is not None
                else {}
            )
            missing_episode_numbers = [
                number for number in episode_numbers if number not in metadata_by_number
            ]
            episode_title = " / ".join(
                metadata_by_number[number].name
                for number in episode_numbers
                if number in metadata_by_number and metadata_by_number[number].name
            )
        return ManualMatchPreview(
            tmdb_id=candidate.tmdb_id,
            title=candidate.title,
            year=candidate.year,
            media_type=candidate.media_type,
            season_number=season_number,
            episode_numbers=list(episode_numbers),
            missing_episode_numbers=missing_episode_numbers,
            target_path=target_path_for(
                parsed,
                candidate,
                media_match.source_item.extension,
                episode_title=episode_title,
            ),
        )

    async def _resolve_manual_candidate(
        self,
        request: ManualMatchRequest,
    ) -> MetadataCandidate:
        try:
            canonical_candidate = await self._tmdb_service.get_candidate(
                tmdb_id=request.tmdb_id,
                media_type=request.media_type,
            )
        except MetadataServiceError as error:
            if not request.title:
                raise OrganizerError("无法读取 TMDB 条目，请稍后重试") from error
            canonical_candidate = None
        if canonical_candidate is not None:
            return canonical_candidate
        if not request.title:
            raise OrganizerError("TMDB 条目不存在，且未提供兼容标题")
        return MetadataCandidate(
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

    async def request_cancel(self, job: OrganizeJob, session: AsyncSession) -> OrganizeJob:
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
            JobStatus.READY if review_items + unresolved_items == 0 else JobStatus.REVIEW_REQUIRED
        )
        job.current_stage = "可以执行" if job.status == JobStatus.READY else "等待审核"
        await session.commit()


def _target_path_for_candidate(media_match: MediaMatch, candidate: MatchCandidateSchema) -> str:
    parsed_from_filename = parse_media_filename(media_match.source_item.filename)
    quality_tags_value = media_match.release_info.get("quality_tags", [])
    quality_tags = (
        tuple(item for item in quality_tags_value if isinstance(item, str))
        if isinstance(quality_tags_value, list)
        else ()
    )
    release_group_value = media_match.release_info.get("release_group", "")
    release_group = release_group_value if isinstance(release_group_value, str) else ""
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


def _manual_episode_mapping(
    context: ManualEpisodeMappingContext,
) -> tuple[int | None, tuple[int, ...]]:
    media_match = context.media_match
    request = context.request
    if request.media_type != MediaType.TV:
        return None, ()
    if request.season_number is not None and request.episode_numbers:
        episode_numbers = tuple(dict.fromkeys(request.episode_numbers))
        if any(number <= 0 for number in episode_numbers):
            raise OrganizerError("集号必须是正整数")
        return request.season_number, episode_numbers
    source_path = media_match.source_item.source_path or media_match.source_item.filename
    parsed = parse_media_filename(
        media_match.source_item.filename,
        parent_path=str(PurePosixPath(source_path).parent),
        source_root=context.source_root,
    )
    inferred_episode_numbers = (
        parsed.episode_numbers
        or parse_bare_episode_numbers(media_match.source_item.filename)
    )
    season_number = (
        request.season_number
        if request.season_number is not None
        else media_match.season_number or parsed.season_number
    )
    episode_numbers = tuple(
        dict.fromkeys(
            request.episode_numbers
            or media_match.episode_numbers
            or inferred_episode_numbers
        )
    )
    if season_number is None and episode_numbers:
        season_number = 1
    if any(number <= 0 for number in episode_numbers):
        raise OrganizerError("集号必须是正整数")
    return season_number, episode_numbers


def _group_episode_mapping(
    *,
    media_match: MediaMatch,
    anchor_match_id: str,
    request: ManualMatchRequest,
    source_root: str,
) -> tuple[int | None, tuple[int, ...]]:
    if media_match.id == anchor_match_id:
        return _manual_episode_mapping(
            ManualEpisodeMappingContext(
                media_match=media_match,
                request=request,
                source_root=source_root,
            )
        )
    if media_match.season_number is not None and media_match.episode_numbers:
        return media_match.season_number, tuple(media_match.episode_numbers)
    parsed = parse_media_filename(
        media_match.source_item.filename,
        parent_path=str(PurePosixPath(media_match.source_item.source_path).parent),
        source_root=source_root,
    )
    episode_numbers = parsed.episode_numbers or parse_bare_episode_numbers(
        media_match.source_item.filename
    )
    season_number = parsed.season_number or (1 if episode_numbers else None)
    return season_number, episode_numbers


def _merge_manual_group_context(
    parsed: ParsedMediaName,
    group_recognition: ParsedMediaName,
) -> ParsedMediaName:
    return replace(
        parsed,
        media_type=group_recognition.media_type,
        title=group_recognition.title,
        year=group_recognition.year or parsed.year,
        confidence=max(parsed.confidence, group_recognition.confidence),
        reason_codes=tuple(
            dict.fromkeys(
                (
                    *parsed.reason_codes,
                    *group_recognition.reason_codes,
                    "GROUP_CONTEXT_REUSED",
                )
            )
        ),
    )
