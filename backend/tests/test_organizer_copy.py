from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain import OperationStatus, OperationType
from app.models import FileOperation, OrganizeJob, SourceItem
from app.providers.base import CloudNode, ProviderTask
from app.services.organizer_copy import CopyExecutor, CopyPlanItem


@pytest.mark.asyncio
async def test_copy_plan_submits_same_directory_files_as_one_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.organizer_copy.RESULT_RESOLVE_DELAYS_SECONDS",
        (0, 0, 0),
    )
    provider = MagicMock()
    provider.list_directory = AsyncMock(
        side_effect=[
            [],
            [
                _file("copied-1", "01.mp4", 0),
                _file("copied-2", "02.mp4", 202),
            ],
        ]
    )
    provider.copy_items = AsyncMock(return_value=ProviderTask(task_id="task-1"))
    provider.task_is_complete = AsyncMock(return_value=True)
    provider.resolve_task_nodes = AsyncMock(return_value=[])
    provider.rename_item = AsyncMock()
    session = _session(scalar_values=[None, None])
    target = _directory()
    sources = [
        _source("source-1", "cloud-1", "01.mp4", 101),
        _source("source-2", "cloud-2", "02.mp4", 202),
    ]

    results = await CopyExecutor(provider).execute_plan(
        session=session,
        job=OrganizeJob(id="job-1"),
        items=[
            CopyPlanItem(sources[0], target, "剧名 - S01E01.mp4"),
            CopyPlanItem(sources[1], target, "剧名 - S01E02.mp4"),
        ],
    )

    provider.copy_items.assert_awaited_once_with(
        ["cloud-1", "cloud-2"],
        "season-1",
    )
    assert provider.resolve_task_nodes.await_count == 3
    assert provider.list_directory.await_count == 2
    assert provider.rename_item.await_count == 2
    assert all(result.succeeded for result in results)
    assert sum(result.copied_bytes for result in results) == 303


@pytest.mark.asyncio
async def test_copy_plan_recovers_completed_file_when_task_result_was_lost() -> None:
    source = _source("source-1", "cloud-1", "01.mp4", 101)
    target = _directory()
    operation = FileOperation(
        job_id="job-1",
        source_item_id=source.id,
        operation_type=OperationType.COPY,
        status=OperationStatus.RUNNING,
        source_path=source.source_path,
        target_path=f"{target.path}/剧名 - S01E01.mp4",
        idempotency_key="copy-key",
        provider_task_id="forgotten-task",
    )
    provider = MagicMock()
    provider.list_directory = AsyncMock(return_value=[_file("copied-1", "01.mp4", 101)])
    provider.task_is_complete = AsyncMock(return_value=True)
    provider.copy_items = AsyncMock()
    provider.rename_item = AsyncMock()
    session = _session(scalar_values=[operation])

    results = await CopyExecutor(provider).execute_plan(
        session=session,
        job=OrganizeJob(id="job-1"),
        items=[CopyPlanItem(source, target, "剧名 - S01E01.mp4")],
    )

    provider.copy_items.assert_not_awaited()
    provider.rename_item.assert_awaited_once_with(
        "copied-1",
        "剧名 - S01E01.mp4",
    )
    assert results[0].succeeded is True
    assert results[0].copied_bytes == 101
    assert operation.status == OperationStatus.COMPLETED
    assert operation.error_message is None


@pytest.mark.asyncio
async def test_copy_plan_records_unresolved_file_and_keeps_other_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.organizer_copy.RESULT_RESOLVE_DELAYS_SECONDS",
        (0, 0, 0),
    )
    provider = MagicMock()
    provider.list_directory = AsyncMock(side_effect=[[], [_file("copied-1", "01.mp4", 101)]])
    provider.copy_items = AsyncMock(return_value=ProviderTask(task_id="task-1"))
    provider.task_is_complete = AsyncMock(return_value=True)
    provider.resolve_task_nodes = AsyncMock(return_value=[])
    provider.rename_item = AsyncMock()
    session = _session(scalar_values=[None, None])
    target = _directory()

    results = await CopyExecutor(provider).execute_plan(
        session=session,
        job=OrganizeJob(id="job-1"),
        items=[
            CopyPlanItem(
                _source("source-1", "cloud-1", "01.mp4", 101),
                target,
                "剧名 - S01E01.mp4",
            ),
            CopyPlanItem(
                _source("source-2", "cloud-2", "02.mp4", 202),
                target,
                "剧名 - S01E02.mp4",
            ),
        ],
    )

    assert [result.succeeded for result in results] == [True, False]
    assert results[1].error_message == ("复制任务已完成，但无法在目标目录认领对应文件")
    operations = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], FileOperation)
        and call.args[0].operation_type == OperationType.COPY
    ]
    assert operations[0].status == OperationStatus.COMPLETED
    assert operations[1].status == OperationStatus.FAILED


def _session(*, scalar_values: list[FileOperation | None]) -> MagicMock:
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=scalar_values)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


def _directory() -> CloudNode:
    return CloudNode(
        id="season-1",
        parent_id="show-1",
        name="Season 01",
        path="/staging/TV/剧名/Season 01",
        is_directory=True,
    )


def _file(node_id: str, name: str, size_bytes: int) -> CloudNode:
    return CloudNode(
        id=node_id,
        parent_id="season-1",
        name=name,
        path=f"/staging/TV/剧名/Season 01/{name}",
        is_directory=False,
        size_bytes=size_bytes,
    )


def _source(
    source_id: str,
    cloud_file_id: str,
    filename: str,
    size_bytes: int,
) -> SourceItem:
    return SourceItem(
        id=source_id,
        job_id="job-1",
        cloud_file_id=cloud_file_id,
        source_path=f"/source/{filename}",
        filename=filename,
        size_bytes=size_bytes,
    )
