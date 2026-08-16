from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain import JobStatus, OperationType, ProgressStage, ProgressState
from app.models import Base, JobProgressEvent, OrganizeJob
from app.services.progress_events import record_job_progress


async def test_progress_event_persists_with_job_revision() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await _assert_progress_event(session)
    await engine.dispose()


async def _assert_progress_event(session) -> None:
    job = OrganizeJob(
        name="实时任务",
        source_directory_id="source",
        source_directory_path="/source",
        target_directory_id="target",
        target_directory_path="/target",
        status=JobStatus.IDENTIFYING,
    )
    session.add(job)
    await session.flush()

    record_job_progress(
        session,
        job,
        stage=ProgressStage.IDENTIFY,
        state=ProgressState.RUNNING,
        completed=3,
        total=10,
        current_group="TV|庆余年|2019",
        message="元数据识别 3/10",
    )
    await session.commit()

    event = await session.scalar(select(JobProgressEvent).where(JobProgressEvent.job_id == job.id))
    assert event is not None
    assert job.revision == 1
    assert job.progress_detail["completed"] == 3
    assert event.event_type == "job.updated"
    assert event.payload["revision"] == 1

    record_job_progress(
        session,
        job,
        stage=ProgressStage.COPY,
        state=ProgressState.COMPLETED,
        completed=8,
        total=8,
        succeeded=7,
        skipped=1,
        operation_type=OperationType.COPY,
        current_filename="S01E08.mkv",
    )
    record_job_progress(
        session,
        job,
        stage=ProgressStage.CLEANUP,
        state=ProgressState.RUNNING,
        completed=2,
        total=7,
        succeeded=2,
        operation_type=OperationType.TRASH,
        current_filename="S01E02.mkv",
    )
    await session.commit()

    operation_summaries = job.progress_detail["operations"]
    assert isinstance(operation_summaries, dict)
    assert operation_summaries["COPY"]["completed"] == 8
    assert operation_summaries["TRASH"]["completed"] == 2
    assert job.progress_detail["current_filename"] == "S01E02.mkv"
