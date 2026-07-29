import asyncio
import json
from collections.abc import AsyncIterator, Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import DatabaseSession, Services
from app.database import SessionFactory
from app.domain import JobStatus
from app.models import AuditEvent, MediaMatch, OrganizeJob, SourceItem
from app.schemas import (
    CreateJobRequest,
    JobView,
    MatchCandidate,
    MediaMatchView,
    UpdateMatchRequest,
)
from app.security import require_admin_session
from app.services.organizer import OrganizerError

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_admin_session)],
)


@router.get("", response_model=list[JobView])
async def list_jobs(session: DatabaseSession) -> list[OrganizeJob]:
    statement = select(OrganizeJob).order_by(OrganizeJob.updated_at.desc())
    return list((await session.scalars(statement)).all())


@router.post("", response_model=JobView, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: CreateJobRequest,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    return await services.organizer.create_job(request, session)


@router.get("/{job_id}", response_model=JobView)
async def get_job(
    job_id: str, session: DatabaseSession
) -> OrganizeJob:
    return await _get_job_or_404(session, job_id)


@router.post("/{job_id}/scan", response_model=JobView, status_code=status.HTTP_202_ACCEPTED)
async def scan_job(
    job_id: str,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    job = await _get_job_or_404(session, job_id)
    if job.status not in {
        JobStatus.DRAFT,
        JobStatus.FAILED,
        JobStatus.REVIEW_REQUIRED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前状态不能重新扫描",
        )
    await services.queue.enqueue("scan", job_id)
    return job


@router.get("/{job_id}/matches", response_model=list[MediaMatchView])
async def list_matches(
    job_id: str,
    session: DatabaseSession,
) -> list[MediaMatchView]:
    statement = (
        select(MediaMatch)
        .join(SourceItem)
        .options(
            selectinload(MediaMatch.source_item),
            selectinload(MediaMatch.media_entity),
        )
        .where(SourceItem.job_id == job_id)
        .order_by(MediaMatch.confidence.desc())
    )
    matches = (await session.scalars(statement)).all()
    return [_to_match_view(media_match) for media_match in matches]


@router.put("/{job_id}/matches/{match_id}", response_model=MediaMatchView)
async def update_match(
    job_id: str,
    match_id: str,
    request: UpdateMatchRequest,
    session: DatabaseSession,
    services: Services,
) -> MediaMatchView:
    try:
        media_match = await services.organizer.update_match(
            job_id=job_id,
            match_id=match_id,
            request=request,
            session=session,
        )
    except OrganizerError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    statement = (
        select(MediaMatch)
        .options(
            selectinload(MediaMatch.source_item),
            selectinload(MediaMatch.media_entity),
        )
        .where(MediaMatch.id == media_match.id)
    )
    refreshed_match = await session.scalar(statement)
    if refreshed_match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_match_view(refreshed_match)


@router.post(
    "/{job_id}/execute", response_model=JobView, status_code=status.HTTP_202_ACCEPTED
)
async def execute_job(
    job_id: str,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    job = await _get_job_or_404(session, job_id)
    if job.status != JobStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="仍有未审核或未识别文件",
        )
    await services.queue.enqueue("execute", job_id)
    return job


@router.post("/{job_id}/cancel", response_model=JobView)
async def cancel_job(
    job_id: str,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    job = await _get_job_or_404(session, job_id)
    await services.organizer.request_cancel(job, session)
    return job


@router.get("/{job_id}/events")
async def stream_job_events(job_id: str) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _get_job_or_404(session: AsyncSession, job_id: str) -> OrganizeJob:
    job = await session.scalar(select(OrganizeJob).where(OrganizeJob.id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


def _to_match_view(media_match: MediaMatch) -> MediaMatchView:
    return MediaMatchView(
        id=media_match.id,
        source_item_id=media_match.source_item_id,
        filename=media_match.source_item.filename,
        source_path=media_match.source_item.source_path,
        size_bytes=media_match.source_item.size_bytes,
        media_type=media_match.media_type,
        parsed_title=media_match.parsed_title,
        parsed_year=media_match.parsed_year,
        season_number=media_match.season_number,
        episode_numbers=media_match.episode_numbers,
        edition=media_match.edition,
        confidence=media_match.confidence,
        decision=media_match.decision,
        selected_tmdb_id=(
            media_match.media_entity.tmdb_id if media_match.media_entity else None
        ),
        candidates=[
            MatchCandidate.model_validate(candidate) for candidate in media_match.candidates
        ],
        target_path=media_match.target_path,
        reason_codes=media_match.reason_codes,
    )


async def _event_stream(job_id: str) -> AsyncIterator[str]:
    last_event_id = ""
    while True:
        async with SessionFactory() as session:
            statement = (
                select(AuditEvent)
                .where(AuditEvent.job_id == job_id)
                .order_by(AuditEvent.created_at.asc())
            )
            events = (await session.scalars(statement)).all()
            new_events = _events_after(events, last_event_id)
            for event in new_events:
                last_event_id = event.id
                payload = json.dumps(
                    {
                        "id": event.id,
                        "type": event.event_type,
                        "message": event.message,
                        "severity": event.severity,
                        "created_at": event.created_at.isoformat(),
                    },
                    ensure_ascii=False,
                )
                yield f"id: {event.id}\nevent: job-event\ndata: {payload}\n\n"
        yield ": keepalive\n\n"
        await asyncio.sleep(1)


def _events_after(events: Sequence[AuditEvent], last_event_id: str) -> Sequence[AuditEvent]:
    if not last_event_id:
        return events
    for event_index, event in enumerate(events):
        if event.id == last_event_id:
            return events[event_index + 1 :]
    return events
