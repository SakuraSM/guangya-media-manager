from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain import JobStatus, MatchDecision
from app.models import OrganizeJob
from app.services.organizer import OrganizerService
from app.services.organizer_scan import _apply_auto_approval_policy


def test_auto_approval_can_be_disabled_for_tmdb_matches() -> None:
    decision = _apply_auto_approval_policy(
        MatchDecision.AUTO_APPROVED,
        auto_approve_enabled=False,
        has_candidates=True,
        reason_codes=(),
    )

    assert decision == MatchDecision.REVIEW


def test_ai_match_always_requires_manual_confirmation() -> None:
    decision = _apply_auto_approval_policy(
        MatchDecision.AUTO_APPROVED,
        auto_approve_enabled=True,
        has_candidates=True,
        reason_codes=("AI_MANUAL_CONFIRMATION_REQUIRED",),
    )

    assert decision == MatchDecision.REVIEW


@pytest.mark.asyncio
async def test_ready_scan_starts_execution_when_auto_flow_is_enabled() -> None:
    job = OrganizeJob(
        id="job-1",
        status=JobStatus.READY,
        config={"auto_execute_after_approval": True},
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=job)
    session.add = MagicMock()
    session.commit = AsyncMock()
    scan_workflow = MagicMock()
    scan_workflow.run = AsyncMock()
    execution_workflow = MagicMock()
    execution_workflow.run = AsyncMock()
    service = object.__new__(OrganizerService)
    service._session_factory = lambda: _SessionContext(session)
    service._scan_workflow = scan_workflow
    service._execution_workflow = execution_workflow

    await service.run_action("scan", job.id)

    scan_workflow.run.assert_awaited_once_with(job.id)
    execution_workflow.run.assert_awaited_once_with(job.id)
    assert session.add.call_args.args[0].event_type == "AUTO_EXECUTE_STARTED"


class _SessionContext:
    def __init__(self, session: MagicMock) -> None:
        self._session = session

    async def __aenter__(self) -> MagicMock:
        return self._session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        return None
