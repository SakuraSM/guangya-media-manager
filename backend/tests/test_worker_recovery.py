from unittest.mock import AsyncMock

import pytest

from app.database import SessionFactory, engine
from app.domain import JobStatus
from app.models import Base, OrganizeJob
from app.worker import recover_interrupted_scans, run_queued_action


async def test_marks_interrupted_scan_as_failed_after_worker_restart() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionFactory() as session:
        job = OrganizeJob(
            name="中断恢复测试",
            source_directory_id="source",
            source_directory_path="/光鸭云盘/未整理",
            target_directory_id="target",
            target_directory_path="/光鸭云盘/电影与剧集",
            status=JobStatus.IDENTIFYING,
        )
        session.add(job)
        await session.commit()
        job_id = job.id

        await recover_interrupted_scans(session)
        await session.refresh(job)

    assert job.id == job_id
    assert job.status == JobStatus.FAILED
    assert job.error_message == "扫描因 Worker 重启中断，请重新扫描"


async def test_reloads_runtime_settings_for_each_queued_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organizer = AsyncMock()
    build_organizer = AsyncMock(return_value=organizer)
    login_manager = AsyncMock()

    class SessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(
            self,
            exception_type: type[BaseException] | None,
            exception: BaseException | None,
            traceback: object,
        ) -> None:
            return None

    monkeypatch.setattr(
        "app.worker.SessionFactory",
        lambda: SessionContext(),
    )
    monkeypatch.setattr(
        "app.worker.build_organizer_service",
        build_organizer,
    )
    provider = AsyncMock()

    await run_queued_action(
        action="scan",
        job_id="job-1",
        provider=provider,
        login_manager=login_manager,
    )
    await run_queued_action(
        action="scan",
        job_id="job-2",
        provider=provider,
        login_manager=login_manager,
    )

    assert build_organizer.await_count == 2
    organizer.run_action.assert_any_await("scan", "job-1")
    organizer.run_action.assert_any_await("scan", "job-2")
