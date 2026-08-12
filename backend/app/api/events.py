import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.database import SessionFactory
from app.models import JobProgressEvent, OrganizeJob
from app.schemas import JobView
from app.security import require_admin_session

router = APIRouter(
    prefix="/events",
    tags=["events"],
    dependencies=[Depends(require_admin_session)],
)

EVENT_POLL_INTERVAL_SECONDS = 0.5
EVENT_BATCH_SIZE = 100


@router.get("/jobs")
async def stream_job_progress(
    job_id: Annotated[str | None, Query()] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    cursor = _parse_cursor(last_event_id)
    return StreamingResponse(
        _event_stream(job_id=job_id, cursor=cursor),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _event_stream(*, job_id: str | None, cursor: int) -> AsyncIterator[str]:
    async with SessionFactory() as session:
        latest_statement = select(func.max(JobProgressEvent.id))
        if job_id:
            latest_statement = latest_statement.where(JobProgressEvent.job_id == job_id)
        latest_event_id = int(await session.scalar(latest_statement) or 0)
    yield _sse_payload(
        event_type="sync",
        data={"job_id": job_id, "latest_event_id": latest_event_id},
    )
    if cursor == 0:
        cursor = latest_event_id

    while True:
        async with SessionFactory() as session:
            statement = select(JobProgressEvent).where(JobProgressEvent.id > cursor)
            if job_id:
                statement = statement.where(JobProgressEvent.job_id == job_id)
            events = list(
                (
                    await session.scalars(
                        statement.order_by(JobProgressEvent.id.asc()).limit(EVENT_BATCH_SIZE)
                    )
                ).all()
            )
            for progress_event in events:
                cursor = progress_event.id
                job = await session.scalar(
                    select(OrganizeJob).where(OrganizeJob.id == progress_event.job_id)
                )
                payload: dict[str, object] = {
                    "event_id": progress_event.id,
                    "type": progress_event.event_type,
                    "job_id": progress_event.job_id,
                    "scope": progress_event.scope,
                    "match_id": progress_event.match_id,
                    "group_key": progress_event.group_key,
                    "file_operation_id": progress_event.file_operation_id,
                    "payload": progress_event.payload,
                    "created_at": progress_event.created_at.isoformat(),
                }
                if job is not None:
                    payload["job"] = JobView.model_validate(job).model_dump(mode="json")
                yield _sse_payload(
                    event_type="progress",
                    event_id=progress_event.id,
                    data=payload,
                )
        yield ": keepalive\n\n"
        await asyncio.sleep(EVENT_POLL_INTERVAL_SECONDS)


def _parse_cursor(last_event_id: str | None) -> int:
    if not last_event_id:
        return 0
    try:
        return max(int(last_event_id), 0)
    except ValueError:
        return 0


def _sse_payload(
    *,
    event_type: str,
    data: dict[str, object],
    event_id: int | None = None,
) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.extend(
        (
            f"event: {event_type}",
            f"data: {json.dumps(data, ensure_ascii=False)}",
            "",
            "",
        )
    )
    return "\n".join(lines)
