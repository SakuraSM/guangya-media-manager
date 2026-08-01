from collections import defaultdict
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.domain import JobStatus, MatchDecision
from app.models import AuditEvent, MediaMatch, OrganizeJob, SourceItem
from app.schemas import MatchCandidate as MatchCandidateSchema
from app.services.media_parser import ParsedMediaName, parse_media_filename
from app.services.metadata import (
    AiRecognitionService,
    MetadataCandidate,
    MetadataServiceError,
)
from app.services.naming import NamingInput, build_target_relative_path
from app.services.organizer_support import (
    find_candidate,
    load_job,
    persist_candidate_payload,
    validate_candidate,
)

AI_REVIEW_APPROVAL_THRESHOLD = 0.85
AI_REVIEW_PENDING_DECISIONS = {MatchDecision.REVIEW, MatchDecision.UNRESOLVED}
AI_REVIEW_EDITABLE_STATUSES = {
    JobStatus.REVIEW_REQUIRED,
    JobStatus.READY,
    JobStatus.FAILED,
}


class AiReviewWorkflow:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        ai_service: AiRecognitionService,
    ) -> None:
        self._session_factory = session_factory
        self._ai_service = ai_service

    async def run(self, job_id: str) -> None:
        async with self._session_factory() as session:
            job = await load_job(session, job_id)
            if job.status not in AI_REVIEW_EDITABLE_STATUSES:
                await self._finish_without_changes(session, job, "当前任务状态不能进行 AI 审核")
                return
            matches = list(
                (
                    await session.scalars(
                        select(MediaMatch)
                        .join(SourceItem)
                        .options(
                            selectinload(MediaMatch.source_item),
                            selectinload(MediaMatch.media_entity),
                        )
                        .where(SourceItem.job_id == job_id)
                        .order_by(MediaMatch.group_key, SourceItem.relative_path)
                    )
                ).all()
            )
            pending_groups = _pending_groups(matches)
            if not pending_groups:
                await self._finish_without_changes(session, job, "没有需要 AI 审核的低置信记录")
                return

            approved_groups = 0
            approved_items = 0
            retained_groups = 0
            failed_groups = 0
            total_groups = len(pending_groups)
            for group_number, group_matches in enumerate(pending_groups.values(), start=1):
                job.current_stage = f"AI 审核作品名称 {group_number}/{total_groups}"
                await session.commit()
                candidate = _representative_candidate(group_matches)
                if candidate is None:
                    retained_groups += 1
                    _append_group_reason(group_matches, "AI_REVIEW_NO_CANDIDATE")
                    continue
                try:
                    verdict = await self._ai_service.review_title_match(
                        candidate=_metadata_candidate(candidate),
                        parent_paths=_parent_paths(group_matches),
                        filenames=tuple(match.source_item.filename for match in group_matches),
                    )
                except MetadataServiceError as error:
                    failed_groups += 1
                    _append_group_reason(group_matches, error.reason_code)
                    continue
                if not verdict.is_match or verdict.confidence < AI_REVIEW_APPROVAL_THRESHOLD:
                    retained_groups += 1
                    _append_group_reason(group_matches, "AI_REVIEW_RETAINED")
                    continue
                updated_items = await _approve_group(session, group_matches, candidate.tmdb_id)
                if updated_items:
                    approved_groups += 1
                    approved_items += updated_items
                else:
                    retained_groups += 1
                await session.commit()

            await _refresh_job_readiness(session, job)
            summary = {
                "approved_groups": approved_groups,
                "approved_items": approved_items,
                "retained_groups": retained_groups,
                "failed_groups": failed_groups,
            }
            job.config = {
                key: value
                for key, value in job.config.items()
                if key != "_ai_review_queued"
            } | {"ai_review_summary": summary}
            job.current_stage = (
                f"AI 审核完成：通过 {approved_groups} 组，保留 {retained_groups + failed_groups} 组"
            )
            session.add(
                AuditEvent(
                    job_id=job.id,
                    event_type="AI_REVIEW_COMPLETED",
                    message=(
                        f"AI 作品级审核完成：通过 {approved_groups} 组/{approved_items} 个文件，"
                        f"保留 {retained_groups} 组，失败 {failed_groups} 组"
                    ),
                )
            )
            await session.commit()

    async def _finish_without_changes(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        message: str,
    ) -> None:
        job.config = {
            key: value for key, value in job.config.items() if key != "_ai_review_queued"
        }
        job.current_stage = message
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="AI_REVIEW_SKIPPED",
                message=message,
                severity="warning",
            )
        )
        await session.commit()


def _pending_groups(matches: list[MediaMatch]) -> dict[str, list[MediaMatch]]:
    groups: dict[str, list[MediaMatch]] = defaultdict(list)
    for media_match in matches:
        if media_match.decision not in AI_REVIEW_PENDING_DECISIONS:
            continue
        groups[media_match.group_key or media_match.id].append(media_match)
    return dict(groups)


def _representative_candidate(
    matches: list[MediaMatch],
) -> MatchCandidateSchema | None:
    representative = matches[0]
    selected_tmdb_id = (
        representative.media_entity.tmdb_id
        if representative.media_entity is not None
        else None
    )
    candidate_payload = (
        find_candidate(representative.candidates, selected_tmdb_id)
        if selected_tmdb_id is not None
        else representative.candidates[0] if representative.candidates else None
    )
    return validate_candidate(candidate_payload) if candidate_payload is not None else None


def _metadata_candidate(candidate: MatchCandidateSchema) -> MetadataCandidate:
    return MetadataCandidate(
        tmdb_id=candidate.tmdb_id,
        title=candidate.title,
        original_title=candidate.original_title,
        year=candidate.year,
        media_type=candidate.media_type,
        score=candidate.score,
        poster_url=candidate.poster_url,
        backdrop_url=candidate.backdrop_url,
        overview=candidate.overview,
    )


def _parent_paths(matches: list[MediaMatch]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(PurePosixPath(media_match.source_item.relative_path).parent)
            for media_match in matches
        )
    )


async def _approve_group(
    session: AsyncSession,
    matches: list[MediaMatch],
    candidate_tmdb_id: int,
) -> int:
    updated_items = 0
    for media_match in matches:
        candidate_payload = find_candidate(media_match.candidates, candidate_tmdb_id)
        if candidate_payload is None:
            _append_reason(media_match, "AI_REVIEW_GROUP_CANDIDATE_MISSING")
            continue
        candidate = validate_candidate(candidate_payload)
        entity = await persist_candidate_payload(session, candidate_payload)
        media_match.media_entity_id = entity.id
        media_match.confidence = candidate.score
        media_match.target_path = _target_path_for_candidate(media_match, candidate)
        media_match.decision = MatchDecision.APPROVED
        _append_reason(media_match, "AI_REVIEW_APPROVED")
        updated_items += 1
    return updated_items


def _append_group_reason(matches: list[MediaMatch], reason_code: str) -> None:
    for media_match in matches:
        _append_reason(media_match, reason_code)


def _append_reason(media_match: MediaMatch, reason_code: str) -> None:
    media_match.reason_codes = list(dict.fromkeys([*media_match.reason_codes, reason_code]))


async def _refresh_job_readiness(session: AsyncSession, job: OrganizeJob) -> None:
    matches = list(
        (
            await session.scalars(
                select(MediaMatch).join(SourceItem).where(SourceItem.job_id == job.id)
            )
        ).all()
    )
    job.review_items = sum(
        media_match.decision in AI_REVIEW_PENDING_DECISIONS for media_match in matches
    )
    job.approved_items = sum(
        media_match.decision in {MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED}
        for media_match in matches
    )
    job.failed_items = 0
    job.status = JobStatus.READY if job.review_items == 0 else JobStatus.REVIEW_REQUIRED


def _target_path_for_candidate(
    media_match: MediaMatch,
    candidate: MatchCandidateSchema,
) -> str:
    parsed_filename = parse_media_filename(media_match.source_item.filename)
    quality_tags_value = media_match.release_info.get("quality_tags", [])
    quality_tags = (
        tuple(value for value in quality_tags_value if isinstance(value, str))
        if isinstance(quality_tags_value, list)
        else ()
    )
    release_group_value = media_match.release_info.get("release_group", "")
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
        release_group=(
            release_group_value if isinstance(release_group_value, str) else ""
        ),
        part_number=parsed_filename.part_number,
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
