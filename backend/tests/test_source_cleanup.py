from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain import (
    MatchDecision,
    OperationStatus,
    OperationType,
    SourceClassification,
)
from app.models import (
    Base,
    FileOperation,
    JobProgressEvent,
    MediaMatch,
    OrganizeJob,
    SourceItem,
)
from app.providers.base import ProviderTask
from app.services.organizer_cleanup import SourceCleanupExecutor
from app.services.organizer_scan import ScanWorkflow


async def test_cleanup_moves_only_safe_selected_and_ignored_files_to_recycle_bin() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    provider = SimpleNamespace(
        trash_items=AsyncMock(return_value=ProviderTask(task_id="trash-task")),
        task_is_complete=AsyncMock(return_value=True),
    )
    async with session_factory() as session:
        job = _job()
        media = _source("media", SourceClassification.MEDIA)
        subtitle = _source("subtitle", SourceClassification.SUBTITLE)
        subtitle.associated_media_item_id = media.id
        ignored = _source("ignored", SourceClassification.IGNORED)
        protected = _source(
            "protected",
            SourceClassification.IGNORED,
            source_path="/source/output/protected.tmp",
            filter_reason="TARGET_TREE",
        )
        unknown = _source("unknown", SourceClassification.UNKNOWN)
        media.media_match = MediaMatch(
            id="match-media",
            decision=MatchDecision.APPROVED,
        )
        session.add(job)
        session.add_all([media, subtitle, ignored, protected, unknown])
        await session.commit()

        result = await SourceCleanupExecutor(provider).execute(  # type: ignore[arg-type]
            session=session,
            job=job,
            matches=[media.media_match],
            include_ignored=True,
        )
        await SourceCleanupExecutor(provider).execute(  # type: ignore[arg-type]
            session=session,
            job=job,
            matches=[media.media_match],
            include_ignored=True,
        )
        operations = list(
            (
                await session.scalars(
                    select(FileOperation).where(
                        FileOperation.operation_type == OperationType.TRASH
                    )
                )
            ).all()
        )
        progress_events = list(
            (
                await session.scalars(
                    select(JobProgressEvent).where(
                        JobProgressEvent.event_type == "file-operation.updated"
                    )
                )
            ).all()
        )

    await engine.dispose()
    assert result.completed == 3
    assert result.failed == 0
    assert result.skipped == 1
    provider.trash_items.assert_awaited_once()
    assert set(provider.trash_items.await_args.args[0]) == {
        "cloud-media",
        "cloud-subtitle",
        "cloud-ignored",
    }
    assert {operation.source_item_id for operation in operations} == {
        "media",
        "subtitle",
        "ignored",
    }
    assert all(operation.status == OperationStatus.COMPLETED for operation in operations)
    assert all(operation.target_path == "光鸭回收站" for operation in operations)
    assert job.progress_detail["operations"]["TRASH"]["completed"] == 3
    assert any(event.payload.get("source_filename") == "media.mkv" for event in progress_events)


async def test_cleanup_failure_is_recorded_and_never_retried_automatically() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    provider = SimpleNamespace(
        trash_items=AsyncMock(side_effect=RuntimeError("ambiguous timeout")),
        task_is_complete=AsyncMock(return_value=True),
    )
    async with session_factory() as session:
        job = _job(trash_ignored_source_files=False)
        media = _source("media", SourceClassification.MEDIA)
        media.media_match = MediaMatch(
            id="match-media",
            decision=MatchDecision.APPROVED,
        )
        session.add_all([job, media])
        await session.commit()
        executor = SourceCleanupExecutor(provider)  # type: ignore[arg-type]

        first_result = await executor.execute(
            session=session,
            job=job,
            matches=[media.media_match],
            include_ignored=False,
        )
        second_result = await executor.execute(
            session=session,
            job=job,
            matches=[media.media_match],
            include_ignored=False,
        )
        operation = await session.scalar(select(FileOperation))

    await engine.dispose()
    assert first_result.failed == 1
    assert second_result.skipped == 1
    provider.trash_items.assert_awaited_once()
    assert operation is not None
    assert operation.status == OperationStatus.FAILED
    assert "ambiguous timeout" not in (operation.error_message or "")


async def test_scan_with_only_ignored_files_completes_cleanup_without_execution() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    provider = SimpleNamespace(
        trash_items=AsyncMock(return_value=ProviderTask(task_id="trash-task")),
        task_is_complete=AsyncMock(return_value=True),
    )
    async with session_factory() as session:
        job = _job()
        session.add_all([job, _source("ignored", SourceClassification.IGNORED)])
        await session.commit()
        workflow = object.__new__(ScanWorkflow)
        workflow._source_cleanup = SourceCleanupExecutor(provider)  # type: ignore[arg-type]

        await workflow._complete_identification(session, job, [])

    await engine.dispose()
    assert job.status.value == "COMPLETED"
    assert job.current_stage == "扫描完成，1 个无关文件已移入回收站"
    provider.trash_items.assert_awaited_once_with(["cloud-ignored"])


def _job(*, trash_ignored_source_files: bool = True) -> OrganizeJob:
    return OrganizeJob(
        id="job",
        name="source cleanup",
        source_directory_id="source",
        source_directory_path="/source",
        target_directory_id="target",
        target_directory_path="/source/output",
        config={
            "trash_organized_source_files": True,
            "trash_ignored_source_files": trash_ignored_source_files,
        },
    )


def _source(
    source_id: str,
    classification: SourceClassification,
    *,
    source_path: str | None = None,
    filter_reason: str = "",
) -> SourceItem:
    path = source_path or f"/source/{source_id}.mkv"
    return SourceItem(
        id=source_id,
        job_id="job",
        cloud_file_id=f"cloud-{source_id}",
        source_path=path,
        relative_path=path.removeprefix("/source/"),
        filename=path.rsplit("/", 1)[-1],
        extension=".mkv",
        classification=classification,
        filter_reason=filter_reason,
    )
