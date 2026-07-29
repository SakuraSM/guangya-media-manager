from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.dependencies import DatabaseSession
from app.domain import JobStatus, MatchDecision, MediaType
from app.models import (
    AuditEvent,
    CloudAccount,
    MediaEntity,
    MediaMatch,
    OrganizeJob,
    SourceItem,
)
from app.schemas import (
    AuditEventView,
    CloudAccountView,
    DashboardMetrics,
    DashboardView,
    JobView,
    LibraryItem,
)
from app.security import require_admin_session

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_admin_session)])


@router.get("/dashboard", response_model=DashboardView)
async def get_dashboard(session: DatabaseSession) -> DashboardView:
    account = await session.scalar(select(CloudAccount).limit(1))
    active_job = await session.scalar(
        select(OrganizeJob)
        .where(
            OrganizeJob.status.not_in(
                [
                    JobStatus.COMPLETED,
                    JobStatus.PARTIAL_FAILED,
                    JobStatus.FAILED,
                    JobStatus.CANCELED,
                ]
            )
        )
        .order_by(OrganizeJob.updated_at.desc())
        .limit(1)
    )
    recent_jobs = list(
        (
            await session.scalars(
                select(OrganizeJob).order_by(OrganizeJob.updated_at.desc()).limit(8)
            )
        ).all()
    )
    recent_events = list(
        (
            await session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(8)
            )
        ).all()
    )
    pending_review = int(
        await session.scalar(
            select(func.count())
            .select_from(MediaMatch)
            .where(MediaMatch.decision.in_([MatchDecision.REVIEW, MatchDecision.UNRESOLVED]))
        )
        or 0
    )
    completed_today = int(
        await session.scalar(
            select(func.coalesce(func.sum(OrganizeJob.approved_items), 0)).where(
                OrganizeJob.status == JobStatus.COMPLETED,
                OrganizeJob.updated_at >= datetime.now(UTC).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            )
        )
        or 0
    )
    failed = int(
        await session.scalar(
            select(func.sum(OrganizeJob.failed_items)).where(
                OrganizeJob.status.in_([JobStatus.FAILED, JobStatus.PARTIAL_FAILED])
            )
        )
        or 0
    )
    copied_bytes = int(
        await session.scalar(select(func.coalesce(func.sum(OrganizeJob.copied_bytes), 0)))
        or 0
    )
    return DashboardView(
        account=CloudAccountView.model_validate(account) if account else None,
        metrics=DashboardMetrics(
            pending_review=pending_review or (active_job.review_items if active_job else 0),
            completed_today=completed_today,
            failed=failed or (active_job.failed_items if active_job else 0),
            copied_bytes=copied_bytes,
        ),
        active_job=JobView.model_validate(active_job) if active_job else None,
        recent_jobs=[JobView.model_validate(job) for job in recent_jobs],
        recent_events=[AuditEventView.model_validate(event) for event in recent_events],
    )


@router.get("/library", response_model=list[LibraryItem])
async def get_library(session: DatabaseSession) -> list[LibraryItem]:
    statement = (
        select(MediaMatch, MediaEntity, SourceItem, OrganizeJob)
        .join(MediaEntity, MediaEntity.id == MediaMatch.media_entity_id)
        .join(SourceItem, SourceItem.id == MediaMatch.source_item_id)
        .join(OrganizeJob, OrganizeJob.id == SourceItem.job_id)
        .where(
            OrganizeJob.status.in_(
                [JobStatus.COMPLETED, JobStatus.PARTIAL_FAILED]
            ),
            MediaMatch.decision.in_(
                [MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED]
            ),
        )
        .order_by(OrganizeJob.updated_at.desc())
    )
    rows = (await session.execute(statement)).all()
    return [
        LibraryItem(
            id=media_match.id,
            title=entity.title,
            year=entity.year,
            media_type=MediaType(entity.media_type),
            poster_url=entity.poster_url,
            target_path=media_match.target_path,
            source_filename=source_item.filename,
            completed_at=job.updated_at,
        )
        for media_match, entity, source_item, job in rows
    ]
