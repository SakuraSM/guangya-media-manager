import asyncio
import json
from collections.abc import AsyncIterator, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import DatabaseSession, Services
from app.database import SessionFactory
from app.domain import (
    JobStatus,
    MatchDecision,
    OperationStatus,
    OperationType,
    SourceAction,
    SourceClassification,
)
from app.models import (
    AuditEvent,
    FileOperation,
    MediaMatch,
    OrganizeJob,
    SourceItem,
)
from app.schemas import (
    BatchApproveMatchesRequest,
    BatchApproveMatchesResult,
    CreateJobRequest,
    JobPage,
    JobView,
    ManualMatchRequest,
    MatchCandidate,
    MediaGroupUpdateResult,
    MediaMatchPage,
    MediaMatchView,
    SourceItemView,
    UpdateMatchRequest,
    UpdateMediaGroupRequest,
    UpdateSourceItemRequest,
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


@router.get("/page", response_model=JobPage)
async def list_jobs_page(
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=10, le=100),
) -> JobPage:
    total = await session.scalar(select(func.count(OrganizeJob.id)))
    job_count = total or 0
    jobs = list(
        (
            await session.scalars(
                select(OrganizeJob)
                .order_by(OrganizeJob.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return JobPage(
        items=[JobView.model_validate(job) for job in jobs],
        total=job_count,
        page=page,
        page_size=page_size,
        pages=(job_count + page_size - 1) // page_size,
    )


@router.post("", response_model=JobView, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: CreateJobRequest,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    return await services.organizer.create_job(request, session)


@router.get("/{job_id}", response_model=JobView)
async def get_job(job_id: str, session: DatabaseSession) -> OrganizeJob:
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
        JobStatus.READY,
        JobStatus.CANCELED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前状态不能重新扫描",
        )
    job.is_cancel_requested = False
    await session.commit()
    await services.queue.enqueue("scan", job_id)
    return job


@router.get("/{job_id}/matches", response_model=MediaMatchPage)
async def list_matches(
    job_id: str,
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    decision: MatchDecision | None = None,
) -> MediaMatchPage:
    await _get_job_or_404(session, job_id)
    filters = [SourceItem.job_id == job_id]
    if decision is not None:
        filters.append(MediaMatch.decision == decision)
    total = await session.scalar(select(func.count(MediaMatch.id)).join(SourceItem).where(*filters))
    match_count = total or 0
    statement = (
        select(MediaMatch)
        .join(SourceItem)
        .options(
            selectinload(MediaMatch.source_item),
            selectinload(MediaMatch.media_entity),
        )
        .where(*filters)
        .order_by(
            MediaMatch.group_key.asc(),
            MediaMatch.season_number.asc().nulls_first(),
            SourceItem.relative_path.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    matches = (await session.scalars(statement)).all()
    source_item_ids = [media_match.source_item_id for media_match in matches]
    copy_operations = (
        (
            await session.scalars(
                select(FileOperation)
                .where(
                    FileOperation.job_id == job_id,
                    FileOperation.source_item_id.in_(source_item_ids),
                    FileOperation.operation_type == OperationType.COPY,
                )
                .order_by(FileOperation.updated_at.desc())
            )
        ).all()
        if source_item_ids
        else []
    )
    operations_by_source_id: dict[str, FileOperation] = {}
    for operation in copy_operations:
        if operation.source_item_id is not None:
            operations_by_source_id.setdefault(
                operation.source_item_id,
                operation,
            )
    return MediaMatchPage(
        items=[
            _to_match_view(
                media_match,
                operations_by_source_id.get(media_match.source_item_id),
            )
            for media_match in matches
        ],
        total=match_count,
        page=page,
        page_size=page_size,
        pages=(match_count + page_size - 1) // page_size,
    )


@router.get("/{job_id}/items", response_model=list[SourceItemView])
async def list_source_items(
    job_id: str,
    session: DatabaseSession,
    classification: SourceClassification | None = None,
) -> list[SourceItemView]:
    statement = select(SourceItem).where(SourceItem.job_id == job_id)
    if classification is not None:
        statement = statement.where(SourceItem.classification == classification)
    statement = statement.order_by(SourceItem.relative_path.asc())
    items = (await session.scalars(statement)).all()
    return [_to_source_item_view(item) for item in items]


@router.put("/{job_id}/items/{item_id}", response_model=SourceItemView)
async def update_source_item(
    job_id: str,
    item_id: str,
    request: UpdateSourceItemRequest,
    session: DatabaseSession,
    services: Services,
) -> SourceItemView:
    item = await session.scalar(
        select(SourceItem).where(
            SourceItem.id == item_id,
            SourceItem.job_id == job_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="扫描项不存在")
    if request.action == SourceAction.INCLUDE and item.classification not in {
        SourceClassification.EXTRA,
        SourceClassification.UNKNOWN,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该类型不能人工恢复",
        )
    item.user_action = request.action
    job = await _get_job_or_404(session, job_id)
    include_paths_value = job.config.get("include_paths", [])
    include_paths = (
        {path for path in include_paths_value if isinstance(path, str)}
        if isinstance(include_paths_value, list)
        else set()
    )
    if request.action == SourceAction.INCLUDE:
        include_paths.add(item.relative_path)
    else:
        include_paths.discard(item.relative_path)
    job.config = {**job.config, "include_paths": sorted(include_paths)}
    await session.commit()
    await session.refresh(item)
    response = _to_source_item_view(item)
    if job.status in {
        JobStatus.DRAFT,
        JobStatus.FAILED,
        JobStatus.REVIEW_REQUIRED,
        JobStatus.READY,
    }:
        await services.queue.enqueue("scan", job_id)
    return response


@router.put(
    "/{job_id}/groups/{group_key:path}",
    response_model=MediaGroupUpdateResult,
)
async def update_media_group(
    job_id: str,
    group_key: str,
    request: UpdateMediaGroupRequest,
    session: DatabaseSession,
    services: Services,
) -> MediaGroupUpdateResult:
    try:
        updated_items = await services.organizer.update_group_matches(
            job_id=job_id,
            group_key=group_key,
            request=UpdateMatchRequest(
                decision=request.decision,
                candidate_tmdb_id=request.candidate_tmdb_id,
            ),
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return MediaGroupUpdateResult(
        group_key=group_key,
        updated_items=updated_items,
    )


@router.put(
    "/{job_id}/matches/batch",
    response_model=BatchApproveMatchesResult,
)
async def batch_approve_matches(
    job_id: str,
    request: BatchApproveMatchesRequest,
    session: DatabaseSession,
    services: Services,
) -> BatchApproveMatchesResult:
    try:
        updated_items = await services.organizer.approve_matches(
            job_id=job_id,
            request=request,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return BatchApproveMatchesResult(updated_items=updated_items)


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
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return await _load_match_view(session, media_match.id)


@router.post(
    "/{job_id}/matches/{match_id}/retry",
    response_model=MediaMatchView,
)
async def retry_match(
    job_id: str,
    match_id: str,
    session: DatabaseSession,
    services: Services,
) -> MediaMatchView:
    try:
        media_match = await services.organizer.retry_match(
            job_id=job_id,
            match_id=match_id,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return await _load_match_view(session, media_match.id)


@router.post(
    "/{job_id}/matches/{match_id}/manual",
    response_model=MediaMatchView,
)
async def assign_manual_match(
    job_id: str,
    match_id: str,
    request: ManualMatchRequest,
    session: DatabaseSession,
    services: Services,
) -> MediaMatchView:
    try:
        media_match = await services.organizer.apply_manual_match(
            job_id=job_id,
            match_id=match_id,
            request=request,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return await _load_match_view(session, media_match.id)


async def _load_match_view(session: AsyncSession, match_id: str) -> MediaMatchView:
    statement = (
        select(MediaMatch)
        .options(
            selectinload(MediaMatch.source_item),
            selectinload(MediaMatch.media_entity),
        )
        .where(MediaMatch.id == match_id)
    )
    refreshed_match = await session.scalar(statement)
    if refreshed_match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_match_view(refreshed_match)


@router.post("/{job_id}/execute", response_model=JobView, status_code=status.HTTP_202_ACCEPTED)
async def execute_job(
    job_id: str,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    job = await _get_job_or_404(session, job_id)
    if job.status not in {JobStatus.READY, JobStatus.PARTIAL_FAILED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务尚未完成审核，或当前状态不能整批执行",
        )
    if job.config.get("_auto_execute_queued", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="自动整理已经加入执行队列",
        )
    if job.status == JobStatus.PARTIAL_FAILED:
        retryable_copy_id = await session.scalar(
            select(FileOperation.id).where(
                FileOperation.job_id == job.id,
                FileOperation.operation_type == OperationType.COPY,
                FileOperation.status.in_([OperationStatus.FAILED, OperationStatus.RUNNING]),
            )
        )
        if retryable_copy_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该任务没有可重试的复制文件",
            )
    job.is_cancel_requested = False
    await session.commit()
    await services.queue.enqueue("execute", job_id)
    return job


@router.post("/{job_id}/cancel", response_model=JobView)
async def cancel_job(
    job_id: str,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    job = await _get_job_or_404(session, job_id)
    try:
        return await services.organizer.request_cancel(job, session)
    except OrganizerError as error:
        raise _organizer_http_error(error) from error


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


async def _enqueue_auto_execute_if_ready(
    job_id: str,
    session: AsyncSession,
    services: Services,
) -> None:
    job = await _get_job_or_404(session, job_id)
    if (
        job.status != JobStatus.READY
        or not job.config.get("auto_execute_after_approval", False)
        or job.config.get("_auto_execute_queued", False)
    ):
        return
    job.config = {**job.config, "_auto_execute_queued": True}
    job.current_stage = "审批完成，等待自动整理"
    session.add(
        AuditEvent(
            job_id=job.id,
            event_type="AUTO_EXECUTE_QUEUED",
            message="全部审批完成，已加入自动整理队列",
        )
    )
    await session.commit()
    try:
        await services.queue.enqueue("execute", job.id)
    except Exception:
        job.config = {
            key: value for key, value in job.config.items() if key != "_auto_execute_queued"
        }
        job.current_stage = "自动整理入队失败，可手动执行"
        await session.commit()
        raise


def _to_match_view(
    media_match: MediaMatch,
    execution_operation: FileOperation | None = None,
) -> MediaMatchView:
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
        selected_tmdb_id=(media_match.media_entity.tmdb_id if media_match.media_entity else None),
        candidates=[
            MatchCandidate.model_validate(candidate) for candidate in media_match.candidates
        ],
        target_path=media_match.target_path,
        reason_codes=media_match.reason_codes,
        group_key=media_match.group_key,
        episode_title=media_match.episode_title,
        episode_date=media_match.episode_date,
        release_info=media_match.release_info,
        execution_status=(execution_operation.status if execution_operation else None),
        execution_error=(execution_operation.error_message if execution_operation else None),
    )


def _to_source_item_view(source_item: SourceItem) -> SourceItemView:
    return SourceItemView(
        id=source_item.id,
        filename=source_item.filename,
        source_path=source_item.source_path,
        relative_path=source_item.relative_path,
        size_bytes=source_item.size_bytes,
        classification=source_item.classification,
        filter_reason=source_item.filter_reason,
        user_action=source_item.user_action,
        group_key=source_item.group_key,
        is_reviewable=source_item.classification
        in {SourceClassification.EXTRA, SourceClassification.UNKNOWN},
    )


def _organizer_http_error(error: OrganizerError) -> HTTPException:
    error_message = str(error)
    error_status = (
        status.HTTP_404_NOT_FOUND
        if "not found" in error_message.casefold()
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=error_status, detail=error_message)


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
