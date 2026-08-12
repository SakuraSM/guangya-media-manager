import asyncio
from dataclasses import replace
from pathlib import PurePosixPath

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain import (
    JobStatus,
    MatchDecision,
    MatchOrigin,
    MediaType,
    OutputLayout,
    ProgressStage,
    ProgressState,
    QualityProfile,
    SourceClassification,
)
from app.models import (
    AuditEvent,
    MediaEpisode,
    MediaMatch,
    MediaMatchEpisode,
    MediaSeason,
    OrganizeJob,
    SourceItem,
)
from app.providers.base import CloudNode, CloudProvider
from app.services.incremental_scan import IncrementalDirectoryScanner
from app.services.match_decision import (
    DecisionReason,
    DecisionSeverity,
    MatchDecisionResult,
    decide_identity_match,
)
from app.services.media_classification import apply_output_layout, classify_media
from app.services.media_parser import (
    ParsedMediaName,
    parse_media_filename,
)
from app.services.metadata import (
    AiRecognitionService,
    MetadataCandidate,
    MetadataResolution,
    MetadataResolutionRequest,
    MetadataResolver,
    MetadataServiceError,
    SeasonMetadata,
    TmdbService,
)
from app.services.metadata_identity import (
    MAX_NFO_BYTES,
    MetadataHint,
    MetadataHintError,
    choose_nfo_path,
    extract_path_hint,
    parse_nfo,
)
from app.services.metadata_providers import LocalMetadataProvider, TmdbMetadataProvider
from app.services.organizer_scan_progress import (
    RULE_PARSE_COMPLETE_PROGRESS,
    IncrementalMatchStore,
    PendingMediaRecord,
)
from app.services.organizer_support import (
    OrganizerError,
    candidate_to_dict,
    decide_match,
    fail_job,
    load_job,
    persist_local_metadata_entity,
    persist_metadata_candidate,
    read_config_float,
    target_path_for,
    target_path_for_entity,
    update_job_state,
)
from app.services.progress_events import record_job_progress, record_match_progress
from app.services.quality import build_quality_decision, version_group_key
from app.services.source_classifier import (
    ClassificationPolicy,
    ClassificationResult,
    classify_source_node,
)

SCAN_PROGRESS = 0.12
IDENTIFY_PROGRESS = 0.36
READY_PROGRESS = 0.45
MAX_SCAN_DEPTH = 24
TMDB_SEASON_CONCURRENCY = 4
METADATA_COMPLETE_PROGRESS = 0.44
METADATA_COMMIT_BATCH_SIZE = 5


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
        self._metadata_resolver = MetadataResolver(
            tmdb_service=tmdb_service,
            ai_service=ai_service,
        )

    async def run(self, job_id: str) -> None:
        async with self._session_factory() as session:
            job = await load_job(session, job_id)
            if job.status not in {
                JobStatus.DRAFT,
                JobStatus.FAILED,
                JobStatus.REVIEW_REQUIRED,
                JobStatus.READY,
                JobStatus.CANCELED,
            }:
                raise OrganizerError(f"Job {job_id} cannot be scanned from {job.status}")
            if job.is_cancel_requested:
                return
            await session.execute(delete(SourceItem).where(SourceItem.job_id == job_id))
            job.error_message = None
            job.total_items = 0
            job.approved_items = 0
            job.review_items = 0
            job.failed_items = 0
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
                scan_result = await IncrementalDirectoryScanner(self._provider).scan(session, job)
                cloud_nodes = scan_result.nodes
                job.scanned_directories = scan_result.scanned_directories
                job.skipped_directories = scan_result.skipped_directories
                job.changed_items = scan_result.changed_items
                await session.commit()
                if job.rule_id and not cloud_nodes:
                    job.status = JobStatus.COMPLETED
                    job.progress = 1
                    job.current_stage = "增量扫描完成，没有变化"
                    session.add(
                        AuditEvent(
                            job_id=job.id,
                            event_type="INCREMENTAL_SCAN_UNCHANGED",
                            message=f"检查 {job.scanned_directories} 个目录，未发现新增或变化文件",
                        )
                    )
                    await session.commit()
                    return
                if await _is_cancel_requested(session, job.id):
                    await _cancel_scan(session, job)
                    return
                classified_nodes = [
                    (
                        node,
                        classify_source_node(
                            node,
                            _classification_policy(job),
                        ),
                    )
                    for node in cloud_nodes
                    if not node.is_directory
                ]
                media_nodes = [
                    node
                    for node, result in classified_nodes
                    if result.classification == SourceClassification.MEDIA
                    or result.relative_path in _included_paths(job)
                    or (
                        result.classification == SourceClassification.EXTRA
                        and job.config.get("extras_policy") == "INCLUDE"
                    )
                ]
                subtitle_nodes = [
                    node
                    for node, result in classified_nodes
                    if result.classification == SourceClassification.SUBTITLE
                ]
                await self._persist_filtered_nodes(
                    session,
                    job,
                    classified_nodes,
                )
                await self._begin_identification(session, job, len(media_nodes))
                nfo_nodes = [
                    node
                    for node, result in classified_nodes
                    if result.classification == SourceClassification.EXISTING_ASSET
                    and PurePosixPath(node.name).suffix.casefold() == ".nfo"
                ]
                await self._identify_nodes(
                    session,
                    job,
                    media_nodes,
                    subtitle_nodes,
                    nfo_nodes,
                )
            except (OrganizerError, MetadataServiceError, RuntimeError) as error:
                await fail_job(session, job, "扫描或识别失败", error)

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
        nfo_nodes: list[CloudNode],
    ) -> None:
        auto_threshold = read_config_float(job.config, "auto_approve_threshold", 0.9)
        review_threshold = read_config_float(job.config, "review_threshold", 0.65)
        decisions: list[MatchDecision] = []
        recognition_cache: dict[str, ParsedMediaName] = {}
        candidate_cache: dict[str, list[MetadataCandidate]] = {}
        season_cache: dict[tuple[int, int], SeasonMetadata | None] = {}
        hint_cache: dict[str, MetadataHint] = {}
        hint_decision_cache: dict[str, MatchDecisionResult] = {}
        pending_records = await IncrementalMatchStore(
            session,
            job,
        ).persist_rule_results(media_nodes)
        if await _is_cancel_requested(session, job.id):
            await _cancel_scan(session, job)
            return
        job.progress = RULE_PARSE_COMPLETE_PROGRESS
        job.current_stage = f"查询 TMDB/AI 元数据（已解析 {len(pending_records)} 条）"
        await session.commit()
        await self._prefetch_group_metadata(
            job,
            pending_records,
            recognition_cache,
            candidate_cache,
            hint_cache,
            hint_decision_cache,
            nfo_nodes,
        )
        if await _is_cancel_requested(session, job.id):
            await _cancel_scan(session, job)
            return
        group_seasons = _group_season_numbers(pending_records)
        for item_number, pending_record in enumerate(
            pending_records,
            start=1,
        ):
            if await _is_cancel_requested(session, job.id):
                await _cancel_scan(session, job)
                return
            decision = await self._identify_node(
                session=session,
                job=job,
                pending_record=pending_record,
                auto_threshold=auto_threshold,
                review_threshold=review_threshold,
                recognition_cache=recognition_cache,
                candidate_cache=candidate_cache,
                season_cache=season_cache,
                group_seasons=group_seasons,
                hint_cache=hint_cache,
                hint_decision_cache=hint_decision_cache,
            )
            decisions.append(decision)
            if _should_commit_metadata_batch(
                item_number,
                len(pending_records),
            ):
                _update_metadata_progress(
                    job,
                    decisions,
                    item_number,
                    len(pending_records),
                )
                for completed_record in pending_records[
                    max(0, item_number - METADATA_COMMIT_BATCH_SIZE):item_number
                ]:
                    record_match_progress(
                        session,
                        job,
                        completed_record.media_match,
                        stage=(
                            ProgressStage.AUTO_APPROVE
                            if completed_record.media_match.decision
                            == MatchDecision.AUTO_APPROVED
                            else ProgressStage.IDENTIFY
                        ),
                        state=(
                            ProgressState.COMPLETED
                            if completed_record.media_match.decision
                            != MatchDecision.UNRESOLVED
                            else ProgressState.WAITING_REVIEW
                        ),
                        message=(
                            "TMDB 自动审批通过"
                            if completed_record.media_match.decision
                            == MatchDecision.AUTO_APPROVED
                            else "元数据识别完成"
                        ),
                    )
                await session.commit()
        await self._associate_subtitles(session, job, subtitle_nodes)
        await _apply_version_recommendations(session, job)
        decisions = list(
            (
                await session.scalars(
                    select(MediaMatch.decision)
                    .join(SourceItem)
                    .where(SourceItem.job_id == job.id)
                )
            ).all()
        )
        await self._complete_identification(session, job, decisions)

    async def _prefetch_group_metadata(
        self,
        job: OrganizeJob,
        pending_records: list[PendingMediaRecord],
        recognition_cache: dict[str, ParsedMediaName],
        candidate_cache: dict[str, list[MetadataCandidate]],
        hint_cache: dict[str, MetadataHint],
        hint_decision_cache: dict[str, MatchDecisionResult],
        nfo_nodes: list[CloudNode],
    ) -> None:
        records_by_group: dict[str, list[PendingMediaRecord]] = {}
        for pending_record in pending_records:
            records_by_group.setdefault(pending_record.group_key, []).append(pending_record)

        group_keys = tuple(records_by_group)
        nfo_by_path = {node.path: node for node in nfo_nodes}
        resolutions = await asyncio.gather(
            *(
                self._resolve_group_metadata(
                    job=job,
                    records=records_by_group[group_key],
                    nfo_by_path=nfo_by_path,
                )
                for group_key in group_keys
            )
        )
        for group_key, (resolution, hint, hint_decision) in zip(
            group_keys,
            resolutions,
            strict=True,
        ):
            recognition_cache[group_key] = resolution.parsed
            candidate_cache[group_key] = list(resolution.candidates)
            if hint is not None:
                hint_cache[group_key] = hint
            if hint_decision is not None:
                hint_decision_cache[group_key] = hint_decision

    async def _resolve_group_metadata(
        self,
        *,
        job: OrganizeJob,
        records: list[PendingMediaRecord],
        nfo_by_path: dict[str, CloudNode],
    ) -> tuple[MetadataResolution, MetadataHint | None, MatchDecisionResult | None]:
        representative = records[0]
        path_hint = extract_path_hint(
            representative.cloud_node.path,
            filename=representative.cloud_node.name,
        )
        nfo_hint: MetadataHint | None = None
        nfo_path = choose_nfo_path(representative.cloud_node.path, set(nfo_by_path))
        if nfo_path is not None:
            try:
                content = await self._provider.read_bytes(
                    nfo_by_path[nfo_path].id,
                    max_bytes=MAX_NFO_BYTES,
                )
                nfo_hint = parse_nfo(content, source_path=nfo_path)
                parent_show_path = str(
                    PurePosixPath(representative.cloud_node.path).parent.parent
                    / "tvshow.nfo"
                )
                if (
                    nfo_hint.episode_number is not None
                    and parent_show_path in nfo_by_path
                    and parent_show_path != nfo_path
                ):
                    show_content = await self._provider.read_bytes(
                        nfo_by_path[parent_show_path].id,
                        max_bytes=MAX_NFO_BYTES,
                    )
                    show_hint = parse_nfo(show_content, source_path=parent_show_path)
                    nfo_hint = replace(
                        show_hint,
                        season_number=nfo_hint.season_number,
                        episode_number=nfo_hint.episode_number,
                    )
            except (MetadataHintError, RuntimeError) as error:
                reason_code = getattr(error, "reason_code", "NFO_READ_FAILED")
                nfo_hint = MetadataHint(
                    origin=MatchOrigin.NFO,
                    source_path=nfo_path,
                    error_code=reason_code,
                )
        has_conflict = bool(
            path_hint
            and path_hint.identity
            and nfo_hint
            and nfo_hint.identity
            and path_hint.identity != nfo_hint.identity
        )
        hint = path_hint or nfo_hint
        if hint is not None and (hint.identity is not None or hint.title or has_conflict):
            candidate = None
            if hint.identity is not None and not has_conflict:
                try:
                    candidate = await TmdbMetadataProvider(
                        self._tmdb_service
                    ).resolve_identity(hint.identity, representative.parsed.media_type)
                except (MetadataServiceError, ValueError):
                    candidate = None
            decision = decide_identity_match(
                origin=hint.origin,
                identity_resolved=candidate is not None,
                expected_type=representative.parsed.media_type,
                actual_type=(
                    nfo_hint.media_type
                    if nfo_hint is not None
                    and nfo_hint.identity is not None
                    and nfo_hint.media_type != MediaType.UNKNOWN
                    else candidate.media_type
                    if candidate
                    else None
                ),
                has_local_title=bool(nfo_hint and nfo_hint.title and not nfo_hint.identity),
                has_conflict=has_conflict,
                auto_approve_enabled=bool(job.config.get("auto_approve_enabled", True)),
            )
            warnings: list[DecisionReason] = []
            if nfo_hint is not None and nfo_hint.error_code:
                warnings.append(
                    DecisionReason(
                        nfo_hint.error_code,
                        "关联 NFO 读取或解析失败，已保留其他识别结果。",
                        DecisionSeverity.WARNING,
                        True,
                        MatchOrigin.NFO,
                    )
                )
            if candidate is not None and nfo_hint is not None:
                if (
                    nfo_hint.title
                    and nfo_hint.title.casefold() not in {
                        candidate.title.casefold(),
                        candidate.original_title.casefold(),
                    }
                ):
                    warnings.append(
                        DecisionReason(
                            "NFO_TITLE_DIFFERS",
                            "NFO 标题与外部 ID 对应标题不同；明确 ID 仍作为身份依据。",
                            DecisionSeverity.WARNING,
                            True,
                            MatchOrigin.NFO,
                        )
                    )
                if nfo_hint.year and candidate.year and nfo_hint.year != candidate.year:
                    warnings.append(
                        DecisionReason(
                            "NFO_YEAR_DIFFERS",
                            "NFO 年份与外部 ID 对应年份不同；明确 ID 仍作为身份依据。",
                            DecisionSeverity.WARNING,
                            True,
                            MatchOrigin.NFO,
                        )
                    )
            if warnings:
                decision = replace(decision, reasons=(*decision.reasons, *warnings))
            parsed = representative.parsed
            if candidate is not None:
                parsed = _merge_candidate_identity(parsed, candidate, hint.origin)
            return (
                MetadataResolution(
                    parsed=parsed,
                    candidates=(candidate,) if candidate else (),
                    requires_manual_confirmation=decision.decision != MatchDecision.AUTO_APPROVED,
                ),
                hint,
                decision,
            )
        resolution = await self._metadata_resolver.resolve(
            MetadataResolutionRequest(
                filename=representative.cloud_node.name,
                parent_path=_relative_path(
                    str(PurePosixPath(representative.cloud_node.path).parent),
                    job.source_directory_path,
                ),
                parsed=representative.parsed,
                group_files=tuple(record.source_item.relative_path for record in records),
            )
        )
        return resolution, nfo_hint, None

    async def _associate_subtitles(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        subtitle_nodes: list[CloudNode],
    ) -> None:
        media_items = list(
            (
                await session.scalars(
                    select(SourceItem).join(MediaMatch).where(SourceItem.job_id == job.id)
                )
            ).all()
        )
        media_by_signature = {
            _media_signature(
                parse_media_filename(
                    item.filename,
                    parent_path=str(PurePosixPath(item.source_path).parent),
                    source_root=job.source_directory_path,
                )
            ): item
            for item in media_items
        }
        associated_count = 0
        for subtitle_node in subtitle_nodes:
            signature = _media_signature(
                parse_media_filename(
                    subtitle_node.name,
                    parent_path=str(PurePosixPath(subtitle_node.path).parent),
                    source_root=job.source_directory_path,
                )
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
                    relative_path=_relative_path(subtitle_node.path, job.source_directory_path),
                    classification=SourceClassification.SUBTITLE,
                    filter_reason="SUPPORTED_SUBTITLE",
                    associated_media_item_id=(media_item.id if media_item is not None else None),
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
                    message=(f"字幕关联完成：{associated_count}/{len(subtitle_nodes)}"),
                )
            )

    async def _identify_node(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        pending_record: PendingMediaRecord,
        auto_threshold: float,
        review_threshold: float,
        recognition_cache: dict[str, ParsedMediaName],
        candidate_cache: dict[str, list[MetadataCandidate]],
        season_cache: dict[tuple[int, int], SeasonMetadata | None],
        group_seasons: dict[str, frozenset[int]],
        hint_cache: dict[str, MetadataHint],
        hint_decision_cache: dict[str, MatchDecisionResult],
    ) -> MatchDecision:
        cloud_node = pending_record.cloud_node
        source_item = pending_record.source_item
        media_match = pending_record.media_match
        parsed = pending_record.parsed
        group_key = pending_record.group_key
        parent_path = str(PurePosixPath(cloud_node.path).parent)
        if parsed.is_ignored:
            return MatchDecision.IGNORED

        cached_recognition = recognition_cache.get(group_key)
        if cached_recognition is None:
            resolution = await self._metadata_resolver.resolve(
                MetadataResolutionRequest(
                    filename=cloud_node.name,
                    parent_path=_relative_path(
                        parent_path,
                        job.source_directory_path,
                    ),
                    parsed=parsed,
                )
            )
            parsed = resolution.parsed
            recognition_cache[group_key] = parsed
            candidates = list(resolution.candidates)
            candidate_cache[group_key] = candidates
        else:
            parsed = _merge_group_context(parsed, cached_recognition)
        cached_candidates = candidate_cache.get(group_key)
        if cached_candidates is None:
            resolution = await self._metadata_resolver.resolve(
                MetadataResolutionRequest(
                    filename=cloud_node.name,
                    parent_path=_relative_path(
                        parent_path,
                        job.source_directory_path,
                    ),
                    parsed=parsed,
                )
            )
            parsed = resolution.parsed
            candidates = list(resolution.candidates)
            recognition_cache[group_key] = parsed
            candidate_cache[group_key] = candidates
        else:
            candidates = list(cached_candidates)
        decision, confidence = decide_match(
            candidates=candidates,
            auto_threshold=auto_threshold,
            review_threshold=review_threshold,
        )
        decision = _apply_auto_approval_policy(
            decision,
            auto_approve_enabled=bool(job.config.get("auto_approve_enabled", True)),
            has_candidates=bool(candidates),
            reason_codes=parsed.reason_codes,
        )
        top_candidate = candidates[0] if candidates else None
        entity = await persist_metadata_candidate(session, top_candidate) if top_candidate else None
        hint = hint_cache.get(group_key)
        hint_decision = hint_decision_cache.get(group_key)
        if hint_decision is not None:
            decision = hint_decision.decision
            confidence = 1 if top_candidate is not None else 0
        if entity is None and hint is not None and hint.title and hint.identity is None:
            local_metadata = LocalMetadataProvider().resolve_hint(hint, parsed.media_type)
            if local_metadata is not None:
                entity = await persist_local_metadata_entity(
                    session,
                    title=local_metadata.title,
                    year=local_metadata.year,
                    media_type=local_metadata.media_type,
                    original_title=local_metadata.original_title,
                    overview=local_metadata.overview,
                    metadata_snapshot={
                        "season": local_metadata.season_number,
                        "episode": local_metadata.episode_number,
                    },
                )
        episode_title = ""
        episode_records: list[MediaEpisode] = []
        if (
            entity is not None
            and top_candidate is not None
            and parsed.media_type == MediaType.TV
            and parsed.season_number is not None
        ):
            season_metadata = await self._load_season_metadata(
                top_candidate.tmdb_id,
                parsed.season_number,
                group_seasons.get(group_key, frozenset({parsed.season_number})),
                season_cache,
            )
            _, episode_records = await _persist_season_metadata(
                session,
                entity.id,
                parsed.season_number,
                parsed.episode_numbers,
                season_metadata,
            )
            episode_title = _episode_title(episode_records)
        target_path = (
            target_path_for(
                parsed,
                top_candidate,
                source_item.extension,
                episode_title=episode_title,
            )
            if top_candidate
            else target_path_for_entity(parsed, entity, source_item.extension)
            if entity is not None
            else ""
        )
        media_match.media_entity_id = entity.id if entity else None
        media_match.media_type = parsed.media_type
        media_match.parsed_title = parsed.title
        media_match.parsed_year = parsed.year
        media_match.season_number = parsed.season_number
        media_match.episode_numbers = list(parsed.episode_numbers)
        media_match.edition = parsed.edition
        media_match.confidence = confidence
        media_match.decision = decision
        media_match.candidates = [candidate_to_dict(candidate) for candidate in candidates]
        media_match.target_path = target_path
        media_match.reason_codes = list(parsed.reason_codes)
        media_match.group_key = group_key
        media_match.episode_title = episode_title
        media_match.episode_date = parsed.episode_date
        media_match.release_info = {
            "quality_tags": list(parsed.quality_tags),
            "release_group": parsed.release_group,
            "part_number": parsed.part_number,
        }
        classification = classify_media(
            media_type=parsed.media_type,
            title=(entity.title if entity is not None else parsed.title),
            metadata=(entity.metadata_snapshot if entity is not None else None),
        )
        media_match.library_category = classification.category
        media_match.region_bucket = classification.region
        media_match.classification_reasons = list(classification.reasons)
        media_match.target_path = apply_output_layout(
            media_match.target_path,
            category=classification.category,
            region=classification.region,
            classified=job.config.get("output_layout") == OutputLayout.CLASSIFIED.value,
            include_region=bool(job.config.get("include_region_directory", True)),
        )
        try:
            quality_preference = QualityProfile(
                str(job.config.get("quality_profile", QualityProfile.QUALITY.value))
            )
        except ValueError:
            quality_preference = QualityProfile.QUALITY
        quality = build_quality_decision(
            filename=source_item.filename,
            release_info=media_match.release_info,
            size_bytes=source_item.size_bytes,
            preference=quality_preference,
        )
        media_match.quality_profile = {**quality.profile, "score_reason": quality.reason}
        media_match.version_score = quality.score
        media_match.metadata_provider = (
            "TMDB" if top_candidate is not None else "LOCAL" if entity is not None else None
        )
        media_match.provider_id = str(top_candidate.tmdb_id) if top_candidate else None
        media_match.version_group_key = version_group_key(
            identity=(
                f"{media_match.metadata_provider}:{media_match.provider_id}"
                if media_match.provider_id
                else media_match.group_key
            ),
            media_type=parsed.media_type,
            season=parsed.season_number,
            episodes=list(parsed.episode_numbers),
            edition=parsed.edition,
            part_number=parsed.part_number,
        )
        media_match.version_recommendation = "SINGLE"
        media_match.match_origin = (
            hint.origin.value
            if hint is not None
            else MatchOrigin.AI.value
            if "AI_RECOGNIZED" in parsed.reason_codes
            else MatchOrigin.TMDB.value
            if candidates
            else MatchOrigin.RULE.value
        )
        media_match.metadata_hint = hint.as_dict() if hint is not None else {}
        media_match.decision_reasons = (
            [reason.as_dict() for reason in hint_decision.reasons]
            if hint_decision is not None
            else _standard_decision_reasons(parsed, decision, confidence, hint)
        )
        media_match.reason_codes = list(
            dict.fromkeys(
                (
                    *media_match.reason_codes,
                    *(
                        str(reason.get("code"))
                        for reason in media_match.decision_reasons
                        if reason.get("code")
                    ),
                )
            )
        )
        await session.flush()
        session.add_all(
            [
                MediaMatchEpisode(
                    media_match_id=media_match.id,
                    media_episode_id=episode.id,
                    ordinal=ordinal,
                )
                for ordinal, episode in enumerate(episode_records)
            ]
        )
        return decision

    async def _persist_filtered_nodes(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        classified_nodes: list[tuple[CloudNode, ClassificationResult]],
    ) -> None:
        for node, result in classified_nodes:
            if result.classification in {
                SourceClassification.MEDIA,
                SourceClassification.SUBTITLE,
            }:
                continue
            if (
                result.classification == SourceClassification.EXTRA
                and job.config.get("extras_policy") == "INCLUDE"
            ):
                continue
            if result.relative_path in _included_paths(job):
                continue
            session.add(
                SourceItem(
                    job_id=job.id,
                    cloud_file_id=node.id,
                    parent_file_id=node.parent_id,
                    source_path=node.path,
                    filename=node.name,
                    extension=PurePosixPath(node.name).suffix,
                    size_bytes=node.size_bytes,
                    fingerprint=node.fingerprint,
                    relative_path=result.relative_path,
                    classification=result.classification,
                    filter_reason=result.reason_code,
                    is_ignored=True,
                )
            )
        await session.flush()

    async def _load_season_metadata(
        self,
        tmdb_id: int,
        season_number: int,
        season_numbers: frozenset[int],
        season_cache: dict[tuple[int, int], SeasonMetadata | None],
    ) -> SeasonMetadata | None:
        cache_key = (tmdb_id, season_number)
        if cache_key not in season_cache:
            missing_seasons = [
                number for number in season_numbers if (tmdb_id, number) not in season_cache
            ]
            semaphore = asyncio.Semaphore(TMDB_SEASON_CONCURRENCY)

            async def load_season(number: int) -> tuple[int, SeasonMetadata | None]:
                async with semaphore:
                    try:
                        season = await self._tmdb_service.get_tv_season(tmdb_id, number)
                    except MetadataServiceError:
                        season = None
                    return number, season

            loaded_seasons = await asyncio.gather(
                *(load_season(number) for number in missing_seasons)
            )
            season_cache.update(
                {(tmdb_id, number): metadata for number, metadata in loaded_seasons}
            )
        return season_cache.get(cache_key)

    async def _complete_identification(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        decisions: list[MatchDecision],
    ) -> None:
        (
            job.approved_items,
            job.review_items,
            job.failed_items,
        ) = _summarize_decisions(decisions)
        job.status = JobStatus.REVIEW_REQUIRED if job.review_items else JobStatus.READY
        job.progress = READY_PROGRESS
        job.current_stage = "等待审核" if job.status == JobStatus.REVIEW_REQUIRED else "可以执行"
        record_job_progress(
            session,
            job,
            stage=ProgressStage.AUTO_APPROVE,
            state=(
                ProgressState.WAITING_REVIEW
                if job.status == JobStatus.REVIEW_REQUIRED
                else ProgressState.COMPLETED
            ),
            completed=len(decisions),
            total=len(decisions),
            succeeded=job.approved_items,
            failed=job.failed_items,
            message=job.current_stage,
        )
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="IDENTIFY_COMPLETED",
                message=(f"识别完成：{job.approved_items} 自动通过，{job.review_items} 待审核"),
            )
        )
        if job.config.get("auto_approve_enabled", True):
            session.add(
                AuditEvent(
                    job_id=job.id,
                    event_type="AUTO_APPROVAL_COMPLETED",
                    message=f"自动审批完成：{job.approved_items} 条达到置信度阈值",
                )
            )
        await session.commit()


async def _apply_version_recommendations(session: AsyncSession, job: OrganizeJob) -> None:
    matches = list(
        (
            await session.scalars(
                select(MediaMatch)
                .join(SourceItem)
                .where(
                    SourceItem.job_id == job.id,
                    MediaMatch.decision.in_(
                        [MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED, MatchDecision.REVIEW]
                    ),
                )
            )
        ).all()
    )
    groups: dict[str, list[MediaMatch]] = {}
    for media_match in matches:
        if media_match.version_group_key:
            groups.setdefault(media_match.version_group_key, []).append(media_match)
    for group_matches in groups.values():
        if len(group_matches) == 1:
            group_matches[0].version_recommendation = "SINGLE"
            continue
        recommended = max(group_matches, key=lambda item: item.version_score)
        for media_match in group_matches:
            media_match.version_recommendation = "PENDING"
            media_match.decision = MatchDecision.REVIEW
            media_match.decision_reasons = [
                *media_match.decision_reasons,
                {
                    "code": "VERSION_CONFIRMATION_REQUIRED",
                    "message": (
                        "检测到同一内容的多个版本；当前为推荐版本，确认后执行"
                        if media_match.id == recommended.id
                        else "检测到同一内容的多个版本；请与推荐版本比较后选择"
                    ),
                    "severity": "WARNING",
                    "overridable": True,
                    "origin": "QUALITY_PROFILE",
                },
            ]
            media_match.quality_profile = {
                **media_match.quality_profile,
                "recommended": media_match.id == recommended.id,
                "recommendation_reason": "按当前质量偏好得分最高",
            }


def _summarize_decisions(
    decisions: list[MatchDecision],
) -> tuple[int, int, int]:
    approved = decisions.count(MatchDecision.AUTO_APPROVED)
    review = decisions.count(MatchDecision.REVIEW) + decisions.count(MatchDecision.UNRESOLVED)
    return approved, review, 0


def _apply_auto_approval_policy(
    decision: MatchDecision,
    *,
    auto_approve_enabled: bool,
    has_candidates: bool,
    reason_codes: tuple[str, ...],
) -> MatchDecision:
    if has_candidates and "AI_MANUAL_CONFIRMATION_REQUIRED" in reason_codes:
        return MatchDecision.REVIEW
    if decision == MatchDecision.AUTO_APPROVED and not auto_approve_enabled:
        return MatchDecision.REVIEW
    return decision


def _standard_decision_reasons(
    parsed: ParsedMediaName,
    decision: MatchDecision,
    confidence: float,
    hint: MetadataHint | None,
) -> list[dict[str, object]]:
    reasons: list[dict[str, object]] = []
    if hint is not None and hint.error_code:
        reasons.append(
            {
                "code": hint.error_code,
                "message": "关联 NFO 读取或解析失败，已继续使用其他识别方式。",
                "severity": "WARNING",
                "overridable": True,
                "origin": MatchOrigin.NFO.value,
            }
        )
    if "AI_MANUAL_CONFIRMATION_REQUIRED" in parsed.reason_codes:
        reasons.append(
            {
                "code": "AI_MANUAL_CONFIRMATION_REQUIRED",
                "message": "AI 仅辅助判断作品名称，结果必须人工确认。",
                "severity": "WARNING",
                "overridable": True,
                "origin": MatchOrigin.AI.value,
            }
        )
    elif decision == MatchDecision.AUTO_APPROVED:
        reasons.append(
            {
                "code": "TMDB_SCORE_AUTO_APPROVED",
                "message": f"TMDB 候选评分 {confidence:.0%}，达到自动通过阈值。",
                "severity": "INFO",
                "overridable": False,
                "origin": MatchOrigin.TMDB.value,
            }
        )
    elif decision == MatchDecision.REVIEW:
        reasons.append(
            {
                "code": "CANDIDATE_REVIEW_REQUIRED",
                "message": f"候选评分 {confidence:.0%}，需要人工确认。",
                "severity": "WARNING",
                "overridable": True,
                "origin": MatchOrigin.TMDB.value,
            }
        )
    elif decision == MatchDecision.UNRESOLVED:
        reasons.append(
            {
                "code": "NO_VALID_CANDIDATE",
                "message": "未找到可安全采用的元数据候选。",
                "severity": "BLOCKING",
                "overridable": True,
                "origin": MatchOrigin.TMDB.value,
            }
        )
    return reasons


def _should_commit_metadata_batch(
    item_number: int,
    total_items: int,
) -> bool:
    return item_number % METADATA_COMMIT_BATCH_SIZE == 0 or item_number == total_items


def _update_metadata_progress(
    job: OrganizeJob,
    decisions: list[MatchDecision],
    identified_items: int,
    total_items: int,
) -> None:
    (
        job.approved_items,
        job.review_items,
        job.failed_items,
    ) = _summarize_decisions(decisions)
    progress_ratio = identified_items / total_items if total_items else 1
    progress_span = METADATA_COMPLETE_PROGRESS - RULE_PARSE_COMPLETE_PROGRESS
    job.progress = RULE_PARSE_COMPLETE_PROGRESS + progress_span * progress_ratio
    job.current_stage = f"元数据识别 {identified_items}/{total_items}"


async def _is_cancel_requested(session: AsyncSession, job_id: str) -> bool:
    is_cancel_requested = await session.scalar(
        select(OrganizeJob.is_cancel_requested).where(OrganizeJob.id == job_id)
    )
    return bool(is_cancel_requested)


async def _cancel_scan(session: AsyncSession, job: OrganizeJob) -> None:
    job.status = JobStatus.CANCELED
    job.current_stage = "扫描已取消"
    session.add(
        AuditEvent(
            job_id=job.id,
            event_type="JOB_CANCELED",
            message="扫描任务已安全停止，未执行云端写操作",
            severity="warning",
        )
    )
    await session.commit()


def _media_signature(parsed: ParsedMediaName) -> tuple[object, ...]:
    return (
        parsed.media_type,
        parsed.title.casefold(),
        parsed.year,
        parsed.season_number,
        parsed.episode_numbers,
    )


def _classification_policy(job: OrganizeJob) -> ClassificationPolicy:
    sample_max_mb = job.config.get("sample_max_mb", 300)
    sample_limit = sample_max_mb if isinstance(sample_max_mb, int) else 300
    exclude_globs_value = job.config.get("exclude_globs", [])
    exclude_globs = (
        tuple(item for item in exclude_globs_value if isinstance(item, str))
        if isinstance(exclude_globs_value, list)
        else ()
    )
    return ClassificationPolicy(
        source_root=job.source_directory_path,
        target_root=job.target_directory_path,
        sample_max_bytes=sample_limit * 1024**2,
        exclude_globs=exclude_globs,
    )


def _included_paths(job: OrganizeJob) -> frozenset[str]:
    value = job.config.get("include_paths", [])
    if not isinstance(value, list):
        return frozenset()
    return frozenset(item for item in value if isinstance(item, str))


def _relative_path(path: str, root: str) -> str:
    source_path = PurePosixPath(path)
    try:
        return str(source_path.relative_to(PurePosixPath(root)))
    except ValueError:
        return str(source_path)


def _group_key(parsed: ParsedMediaName, parent_path: str) -> str:
    title = parsed.context_group or parsed.title or PurePosixPath(parent_path).name
    return "|".join(
        (
            parsed.media_type.value,
            title.casefold(),
            str(parsed.year or ""),
        )
    )


def _group_season_numbers(
    pending_records: list[PendingMediaRecord],
) -> dict[str, frozenset[int]]:
    seasons_by_group: dict[str, set[int]] = {}
    for pending_record in pending_records:
        if pending_record.parsed.season_number is None:
            continue
        seasons_by_group.setdefault(pending_record.group_key, set()).add(
            pending_record.parsed.season_number
        )
    return {
        group_key: frozenset(season_numbers)
        for group_key, season_numbers in seasons_by_group.items()
    }


def _merge_group_context(
    parsed: ParsedMediaName, group_recognition: ParsedMediaName
) -> ParsedMediaName:
    reason_codes = tuple(
        dict.fromkeys(
            (
                *parsed.reason_codes,
                *group_recognition.reason_codes,
                "GROUP_CONTEXT_REUSED",
            )
        )
    )
    return ParsedMediaName(
        media_type=group_recognition.media_type,
        title=group_recognition.title,
        year=group_recognition.year or parsed.year,
        season_number=parsed.season_number,
        episode_numbers=parsed.episode_numbers,
        edition=parsed.edition,
        confidence=max(parsed.confidence, group_recognition.confidence),
        reason_codes=reason_codes,
        is_ignored=parsed.is_ignored,
        episode_date=parsed.episode_date,
        quality_tags=parsed.quality_tags,
        release_group=parsed.release_group,
        part_number=parsed.part_number,
        context_group=parsed.context_group,
    )


def _merge_candidate_identity(
    parsed: ParsedMediaName,
    candidate: MetadataCandidate,
    origin: MatchOrigin,
) -> ParsedMediaName:
    return ParsedMediaName(
        media_type=candidate.media_type,
        title=candidate.title,
        year=candidate.year or parsed.year,
        season_number=parsed.season_number,
        episode_numbers=parsed.episode_numbers,
        edition=parsed.edition,
        confidence=1,
        reason_codes=tuple(
            dict.fromkeys(
                (*parsed.reason_codes, f"{origin.value}_IDENTITY", "EXPLICIT_ID_RESOLVED")
            )
        ),
        is_ignored=parsed.is_ignored,
        episode_date=parsed.episode_date,
        quality_tags=parsed.quality_tags,
        release_group=parsed.release_group,
        part_number=parsed.part_number,
        context_group=parsed.context_group,
    )
async def _persist_season_metadata(
    session: AsyncSession,
    media_entity_id: str,
    season_number: int,
    episode_numbers: tuple[int, ...],
    metadata: SeasonMetadata | None,
) -> tuple[MediaSeason, list[MediaEpisode]]:
    season = await session.scalar(
        select(MediaSeason).where(
            MediaSeason.media_entity_id == media_entity_id,
            MediaSeason.season_number == season_number,
        )
    )
    if season is None:
        season = MediaSeason(
            media_entity_id=media_entity_id,
            season_number=season_number,
            name=metadata.name if metadata else "",
            overview=metadata.overview if metadata else "",
            poster_url=metadata.poster_url if metadata else None,
            metadata_snapshot=metadata.snapshot if metadata else {},
        )
        session.add(season)
        await session.flush()
    metadata_by_number = (
        {episode.episode_number: episode for episode in metadata.episodes} if metadata else {}
    )
    records: list[MediaEpisode] = []
    for episode_number in episode_numbers:
        existing = await session.scalar(
            select(MediaEpisode).where(
                MediaEpisode.media_season_id == season.id,
                MediaEpisode.episode_number == episode_number,
            )
        )
        if existing is not None:
            records.append(existing)
            continue
        episode_metadata = metadata_by_number.get(episode_number)
        episode = MediaEpisode(
            media_season_id=season.id,
            tmdb_id=episode_metadata.tmdb_id if episode_metadata else None,
            episode_number=episode_number,
            name=episode_metadata.name if episode_metadata else f"第 {episode_number} 集",
            overview=episode_metadata.overview if episode_metadata else "",
            air_date=episode_metadata.air_date if episode_metadata else None,
            still_url=episode_metadata.still_url if episode_metadata else None,
            metadata_snapshot=episode_metadata.snapshot if episode_metadata else {},
        )
        session.add(episode)
        await session.flush()
        records.append(episode)
    return season, records


def _episode_title(episodes: list[MediaEpisode]) -> str:
    titles = [episode.name for episode in episodes if episode.name]
    return " / ".join(titles)
