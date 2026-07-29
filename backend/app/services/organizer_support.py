from dataclasses import asdict
from hashlib import sha256
from xml.sax.saxutils import escape

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import JobStatus, MatchDecision, MediaType
from app.models import AuditEvent, MediaEntity, MediaEpisode, MediaSeason, OrganizeJob
from app.schemas import MatchCandidate as MatchCandidateSchema
from app.services.media_parser import ParsedMediaName
from app.services.metadata import MetadataCandidate
from app.services.naming import NamingInput, build_target_relative_path


class OrganizerError(RuntimeError):
    pass


async def load_job(session: AsyncSession, job_id: str) -> OrganizeJob:
    job = await session.scalar(select(OrganizeJob).where(OrganizeJob.id == job_id))
    if job is None:
        raise OrganizerError("Job not found")
    return job


async def update_job_state(
    session: AsyncSession,
    job: OrganizeJob,
    *,
    status: JobStatus,
    progress: float,
    stage: str,
    event_type: str,
    message: str,
) -> None:
    job.status = status
    job.progress = progress
    job.current_stage = stage
    session.add(AuditEvent(job_id=job.id, event_type=event_type, message=message))
    await session.commit()


async def fail_job(
    session: AsyncSession,
    job: OrganizeJob,
    message: str,
    error: Exception,
    *,
    partial: bool = False,
) -> None:
    job.status = JobStatus.PARTIAL_FAILED if partial else JobStatus.FAILED
    job.error_message = str(error)
    job.current_stage = message
    session.add(
        AuditEvent(
            job_id=job.id,
            event_type="JOB_FAILED",
            message=message,
            severity="error",
            details={"error_type": type(error).__name__},
        )
    )
    await session.commit()


async def persist_metadata_candidate(
    session: AsyncSession, candidate: MetadataCandidate
) -> MediaEntity:
    existing = await session.scalar(
        select(MediaEntity).where(
            MediaEntity.tmdb_id == candidate.tmdb_id,
            MediaEntity.media_type == candidate.media_type,
        )
    )
    if existing:
        return existing
    entity = MediaEntity(
        tmdb_id=candidate.tmdb_id,
        media_type=candidate.media_type,
        title=candidate.title,
        original_title=candidate.original_title,
        year=candidate.year,
        overview=candidate.overview,
        poster_url=candidate.poster_url,
        backdrop_url=candidate.backdrop_url,
        metadata_snapshot=asdict(candidate),
    )
    session.add(entity)
    await session.flush()
    return entity


async def persist_candidate_payload(
    session: AsyncSession, candidate: dict[str, object]
) -> MediaEntity:
    candidate_schema = validate_candidate(candidate)
    metadata_candidate = MetadataCandidate(
        tmdb_id=candidate_schema.tmdb_id,
        title=candidate_schema.title,
        original_title=candidate_schema.original_title,
        year=candidate_schema.year,
        media_type=candidate_schema.media_type,
        score=candidate_schema.score,
        poster_url=candidate_schema.poster_url,
        backdrop_url=candidate_schema.backdrop_url,
        overview=candidate_schema.overview,
    )
    return await persist_metadata_candidate(session, metadata_candidate)


def target_path_for(
    parsed: ParsedMediaName,
    candidate: MetadataCandidate,
    extension: str,
    *,
    episode_title: str = "",
) -> str:
    return build_target_relative_path(
        NamingInput(
            title=candidate.title,
            year=candidate.year,
            parsed=parsed,
            extension=extension,
            episode_title=episode_title,
        )
    )


def candidate_to_dict(candidate: MetadataCandidate) -> dict[str, object]:
    return {
        "tmdb_id": candidate.tmdb_id,
        "title": candidate.title,
        "original_title": candidate.original_title,
        "year": candidate.year,
        "media_type": candidate.media_type.value,
        "score": candidate.score,
        "poster_url": candidate.poster_url,
        "backdrop_url": candidate.backdrop_url,
        "overview": candidate.overview,
    }


def decide_match(
    *,
    candidates: list[MetadataCandidate],
    auto_threshold: float,
    review_threshold: float,
) -> tuple[MatchDecision, float]:
    if not candidates:
        return MatchDecision.UNRESOLVED, 0
    score = candidates[0].score
    if score >= auto_threshold:
        return MatchDecision.AUTO_APPROVED, score
    if score >= review_threshold:
        return MatchDecision.REVIEW, score
    return MatchDecision.UNRESOLVED, score


def find_candidate(
    candidates: list[dict[str, object]], tmdb_id: int
) -> dict[str, object] | None:
    for candidate in candidates:
        try:
            candidate_schema = validate_candidate(candidate)
        except ValidationError:
            continue
        if candidate_schema.tmdb_id == tmdb_id:
            return candidate
    return None


def validate_candidate(candidate: dict[str, object]) -> MatchCandidateSchema:
    return MatchCandidateSchema.model_validate(candidate)


def read_config_float(config: dict[str, object], key: str, default: float) -> float:
    value = config.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default


def make_idempotency_key(action: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{action}:{digest}"


def render_nfo(entity: MediaEntity) -> str:
    root_tag = "tvshow" if entity.media_type == MediaType.TV else "movie"
    year = str(entity.year) if entity.year else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<{root_tag}>\n"
        f"  <title>{escape(entity.title)}</title>\n"
        f"  <originaltitle>{escape(entity.original_title)}</originaltitle>\n"
        f"  <year>{year}</year>\n"
        f"  <plot>{escape(entity.overview)}</plot>\n"
        f'  <uniqueid type="tmdb" default="true">{entity.tmdb_id}</uniqueid>\n'
        f"</{root_tag}>\n"
    )


def render_season_nfo(season: MediaSeason) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<season>\n"
        f"  <title>{escape(season.name)}</title>\n"
        f"  <seasonnumber>{season.season_number}</seasonnumber>\n"
        f"  <plot>{escape(season.overview)}</plot>\n"
        "</season>\n"
    )


def render_episode_nfo(entity: MediaEntity, episode: MediaEpisode) -> str:
    aired = episode.air_date.isoformat() if episode.air_date else ""
    unique_id = str(episode.tmdb_id) if episode.tmdb_id is not None else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<episodedetails>\n"
        f"  <title>{escape(episode.name)}</title>\n"
        f"  <showtitle>{escape(entity.title)}</showtitle>\n"
        f"  <season>{episode.media_season.season_number}</season>\n"
        f"  <episode>{episode.episode_number}</episode>\n"
        f"  <aired>{aired}</aired>\n"
        f"  <plot>{escape(episode.overview)}</plot>\n"
        f'  <uniqueid type="tmdb" default="true">{unique_id}</uniqueid>\n'
        "</episodedetails>\n"
    )
