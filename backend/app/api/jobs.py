from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import DatabaseSession, Services
from app.api.events import _event_stream as _progress_event_stream
from app.domain import (
    JobStatus,
    MatchDecision,
    MatchReviewState,
    MediaType,
    MetadataSource,
    OperationStatus,
    OperationType,
    ProgressStage,
    ProgressState,
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
    LocalMetadataGroupRequest,
    ManualMatchPreview,
    ManualMatchRequest,
    MatchCandidate,
    MediaGroupUpdateResult,
    MediaMatchPage,
    MediaMatchView,
    SourceItemView,
    TmdbEpisodeSummary,
    TmdbSeasonSummary,
    UpdateClassificationRequest,
    UpdateMatchRequest,
    UpdateMediaGroupRequest,
    UpdateSourceItemRequest,
    UpdateVersionGroupRequest,
    VersionGroupUpdateResult,
)
from app.security import require_admin_session
from app.services.metadata import MetadataServiceError
from app.services.organizer import OrganizerError
from app.services.organizer_support import candidate_to_dict
from app.services.progress_events import record_job_progress

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
    review_state: MatchReviewState | None = None,
) -> MediaMatchPage:
    await _get_job_or_404(session, job_id)
    filters = [SourceItem.job_id == job_id]
    if decision is not None:
        filters.append(MediaMatch.decision == decision)
    if review_state == MatchReviewState.PENDING:
        filters.append(
            MediaMatch.decision.in_([MatchDecision.REVIEW, MatchDecision.UNRESOLVED])
        )
    elif review_state == MatchReviewState.REVIEWED:
        filters.append(
            MediaMatch.decision.in_(
                [
                    MatchDecision.AUTO_APPROVED,
                    MatchDecision.APPROVED,
                    MatchDecision.IGNORED,
                ]
            )
        )
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


@router.get("/{job_id}/tmdb/search", response_model=list[MatchCandidate])
async def search_tmdb(
    job_id: str,
    session: DatabaseSession,
    services: Services,
    q: Annotated[str, Query(min_length=1, max_length=160)],
    media_type: Annotated[MediaType, Query()] = MediaType.TV,
    year: Annotated[int | None, Query(ge=1870, le=2100)] = None,
) -> list[MatchCandidate]:
    await _get_job_or_404(session, job_id)
    if media_type == MediaType.UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="TMDB 搜索类型必须是电影或电视剧",
        )
    try:
        candidates = await services.tmdb_service.search_query(
            query=q,
            media_type=media_type,
            year=year,
        )
    except MetadataServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TMDB 搜索失败：{error.reason_code}",
        ) from error
    return [
        MatchCandidate.model_validate(candidate_to_dict(candidate))
        for candidate in candidates
    ]


@router.get(
    "/{job_id}/tmdb/tv/{tmdb_id}/seasons",
    response_model=list[TmdbSeasonSummary],
)
async def list_tmdb_seasons(
    job_id: str,
    tmdb_id: int,
    session: DatabaseSession,
    services: Services,
) -> list[TmdbSeasonSummary]:
    await _get_job_or_404(session, job_id)
    try:
        seasons = await services.tmdb_service.get_tv_seasons(tmdb_id)
    except MetadataServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TMDB 季度读取失败：{error.reason_code}",
        ) from error
    return [
        TmdbSeasonSummary(
            season_number=season.season_number,
            name=season.name,
            episode_count=season.episode_count,
            poster_url=season.poster_url,
        )
        for season in seasons
    ]


@router.get(
    "/{job_id}/tmdb/tv/{tmdb_id}/seasons/{season_number}",
    response_model=list[TmdbEpisodeSummary],
)
async def list_tmdb_episodes(
    job_id: str,
    tmdb_id: int,
    season_number: int,
    session: DatabaseSession,
    services: Services,
) -> list[TmdbEpisodeSummary]:
    await _get_job_or_404(session, job_id)
    try:
        season = await services.tmdb_service.get_tv_season(
            tmdb_id,
            season_number,
        )
    except MetadataServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TMDB 剧集读取失败：{error.reason_code}",
        ) from error
    if season is None:
        return []
    return [
        TmdbEpisodeSummary(
            episode_number=episode.episode_number,
            name=episode.name,
            overview=episode.overview,
            air_date=episode.air_date,
            still_url=episode.still_url,
        )
        for episode in season.episodes
    ]


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
    "/{job_id}/groups/{group_key}/classification",
    response_model=MediaGroupUpdateResult,
)
async def update_group_classification(
    job_id: str,
    group_key: str,
    request: UpdateClassificationRequest,
    session: DatabaseSession,
    services: Services,
) -> MediaGroupUpdateResult:
    try:
        updated_items = await services.organizer.update_group_classification(
            job_id=job_id,
            group_key=group_key,
            category=request.library_category,
            region=request.region_bucket,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    return MediaGroupUpdateResult(group_key=group_key, updated_items=updated_items)


@router.put(
    "/{job_id}/version-groups/{version_group_key}",
    response_model=VersionGroupUpdateResult,
)
async def confirm_version_group(
    job_id: str,
    version_group_key: str,
    request: UpdateVersionGroupRequest,
    session: DatabaseSession,
    services: Services,
) -> VersionGroupUpdateResult:
    try:
        updated_items = await services.organizer.confirm_version_group(
            job_id=job_id,
            version_group_key=version_group_key,
            selected_match_ids=request.selected_match_ids,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return VersionGroupUpdateResult(
        version_group_key=version_group_key,
        updated_items=updated_items,
    )


@router.get(
    "/{job_id}/version-groups/{version_group_key}",
    response_model=list[MediaMatchView],
)
async def get_version_group(
    job_id: str,
    version_group_key: str,
    session: DatabaseSession,
) -> list[MediaMatchView]:
    await _get_job_or_404(session, job_id)
    matches = list(
        (
            await session.scalars(
                select(MediaMatch)
                .join(SourceItem)
                .options(
                    selectinload(MediaMatch.source_item),
                    selectinload(MediaMatch.media_entity),
                )
                .where(
                    SourceItem.job_id == job_id,
                    MediaMatch.version_group_key == version_group_key,
                )
                .order_by(MediaMatch.version_score.desc())
            )
        ).all()
    )
    return [_to_match_view(media_match) for media_match in matches]


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
                provider=request.provider,
                provider_id=request.provider_id,
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


@router.post(
    "/{job_id}/groups/{group_key:path}/retry",
    response_model=MediaGroupUpdateResult,
)
async def retry_media_group(
    job_id: str,
    group_key: str,
    session: DatabaseSession,
    services: Services,
) -> MediaGroupUpdateResult:
    try:
        updated_items = await services.organizer.retry_group(
            job_id=job_id,
            group_key=group_key,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
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


@router.post(
    "/{job_id}/matches/ai-review",
    response_model=JobView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_ai_review(
    job_id: str,
    session: DatabaseSession,
    services: Services,
) -> OrganizeJob:
    job = await _get_job_or_404(session, job_id)
    if job.status not in {
        JobStatus.REVIEW_REQUIRED,
        JobStatus.READY,
        JobStatus.FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前任务状态不能进行 AI 审核",
        )
    if not services.ai_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="尚未配置 AI 服务，请先在设置中填写 AI Provider",
        )
    if job.ai_review_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AI 审核已经在进行中",
        )
    if job.review_items == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="没有需要 AI 审核的记录",
        )
    job.config = {**job.config, "_ai_review_queued": True}
    job.current_stage = "等待 AI 审核作品名称"
    record_job_progress(
        session,
        job,
        stage=ProgressStage.AI_REVIEW,
        state=ProgressState.QUEUED,
        total=job.review_items,
        message=job.current_stage,
    )
    session.add(
        AuditEvent(
            job_id=job.id,
            event_type="AI_REVIEW_QUEUED",
            message="已授权 AI 按目录和文件名审核作品名称",
        )
    )
    await session.commit()
    try:
        await services.queue.enqueue("ai_review", job.id)
    except Exception:
        job.config = {
            key: value for key, value in job.config.items() if key != "_ai_review_queued"
        }
        job.current_stage = "AI 审核入队失败，可重试"
        await session.commit()
        raise
    return job


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


@router.post(
    "/{job_id}/matches/{match_id}/manual/group",
    response_model=MediaGroupUpdateResult,
)
async def assign_manual_group_match(
    job_id: str,
    match_id: str,
    request: ManualMatchRequest,
    session: DatabaseSession,
    services: Services,
) -> MediaGroupUpdateResult:
    try:
        group_key, updated_items = (
            await services.organizer.apply_manual_group_match(
                job_id=job_id,
                match_id=match_id,
                request=request,
                session=session,
            )
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return MediaGroupUpdateResult(
        group_key=group_key,
        updated_items=updated_items,
    )


@router.post(
    "/{job_id}/matches/{match_id}/local/group",
    response_model=MediaGroupUpdateResult,
)
async def assign_local_group_match(
    job_id: str,
    match_id: str,
    request: LocalMetadataGroupRequest,
    session: DatabaseSession,
    services: Services,
) -> MediaGroupUpdateResult:
    try:
        group_key, updated_items = await services.organizer.apply_local_group_match(
            job_id=job_id,
            match_id=match_id,
            request=request,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error
    await _enqueue_auto_execute_if_ready(job_id, session, services)
    return MediaGroupUpdateResult(group_key=group_key, updated_items=updated_items)


@router.post(
    "/{job_id}/matches/{match_id}/manual/preview",
    response_model=ManualMatchPreview,
)
async def preview_manual_match(
    job_id: str,
    match_id: str,
    request: ManualMatchRequest,
    session: DatabaseSession,
    services: Services,
) -> ManualMatchPreview:
    try:
        return await services.organizer.preview_manual_match(
            job_id=job_id,
            match_id=match_id,
            request=request,
            session=session,
        )
    except OrganizerError as error:
        raise _organizer_http_error(error) from error


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
        _progress_event_stream(job_id=job_id, cursor=0),
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
    record_job_progress(
        session,
        job,
        stage=ProgressStage.AUTO_EXECUTE,
        state=ProgressState.QUEUED,
        completed=job.approved_items,
        total=job.total_items,
        succeeded=job.approved_items,
        message=job.current_stage,
    )
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
        metadata_source=(
            media_match.media_entity.metadata_source if media_match.media_entity else None
        ),
        metadata_provider=(
            MetadataSource(media_match.metadata_provider)
            if media_match.metadata_provider
            else None
        ),
        provider_id=media_match.provider_id,
        match_origin=media_match.match_origin,
        metadata_hint=media_match.metadata_hint,
        decision_reasons=media_match.decision_reasons,
        candidates=[
            MatchCandidate.model_validate(candidate) for candidate in media_match.candidates
        ],
        target_path=media_match.target_path,
        reason_codes=media_match.reason_codes,
        group_key=media_match.group_key,
        episode_title=media_match.episode_title,
        episode_date=media_match.episode_date,
        release_info=media_match.release_info,
        library_category=media_match.library_category,
        region_bucket=media_match.region_bucket,
        classification_reasons=media_match.classification_reasons,
        quality_profile=media_match.quality_profile,
        version_group_key=media_match.version_group_key,
        version_score=media_match.version_score,
        version_recommendation=media_match.version_recommendation,
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
