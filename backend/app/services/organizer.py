from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.domain import JobStatus, MatchDecision
from app.models import AuditEvent, MediaMatch, OrganizeJob, SourceItem
from app.providers.base import CloudProvider
from app.schemas import CreateJobRequest, UpdateMatchRequest
from app.schemas import MatchCandidate as MatchCandidateSchema
from app.services.media_parser import parse_media_filename
from app.services.metadata import AiRecognitionService, TmdbService
from app.services.naming import NamingInput, build_target_relative_path
from app.services.organizer_execute import ExecutionWorkflow
from app.services.organizer_scan import ScanWorkflow
from app.services.organizer_support import (
    OrganizerError,
    find_candidate,
    load_job,
    persist_candidate_payload,
    validate_candidate,
)

__all__ = ["OrganizerError", "OrganizerService"]


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
        statement = (
            select(MediaMatch)
            .join(SourceItem)
            .options(selectinload(MediaMatch.source_item))
            .where(MediaMatch.id == match_id, SourceItem.job_id == job_id)
        )
        media_match = await session.scalar(statement)
        if media_match is None:
            raise OrganizerError("Match not found")

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

    async def request_cancel(self, job: OrganizeJob, session: AsyncSession) -> None:
        job.is_cancel_requested = True
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="CANCEL_REQUESTED",
                message="已请求停止任务，暂存文件将保留",
                severity="warning",
            )
        )
        await session.commit()

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
        job.failed_items = unresolved_items
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
    parsed = parse_media_filename(media_match.source_item.filename)
    return build_target_relative_path(
        NamingInput(
            title=candidate.title,
            year=candidate.year,
            parsed=parsed,
            extension=media_match.source_item.extension,
        )
    )
