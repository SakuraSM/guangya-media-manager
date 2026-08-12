from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import ProgressStage, ProgressState
from app.models import FileOperation, JobProgressEvent, MediaMatch, OrganizeJob


def _enum_value(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return str(raw_value)


def record_job_progress(
    session: AsyncSession,
    job: OrganizeJob,
    *,
    stage: ProgressStage,
    state: ProgressState,
    completed: int = 0,
    total: int = 0,
    succeeded: int = 0,
    failed: int = 0,
    skipped: int = 0,
    current_group: str | None = None,
    current_match_id: str | None = None,
    message: str | None = None,
) -> None:
    job.revision = (job.revision or 0) + 1
    detail: dict[str, object] = {
        "stage": stage.value,
        "state": state.value,
        "completed": completed or 0,
        "total": total or 0,
        "succeeded": succeeded or 0,
        "failed": failed or 0,
        "skipped": skipped or 0,
    }
    if current_group:
        detail["current_group"] = current_group
    if current_match_id:
        detail["current_match_id"] = current_match_id
    if message:
        detail["message"] = message
    job.progress_detail = detail
    session.add(
        JobProgressEvent(
            job_id=job.id,
            event_type="job.updated",
            scope="JOB",
            payload={"revision": job.revision, "progress_detail": detail},
        )
    )


def record_match_progress(
    session: AsyncSession,
    job: OrganizeJob,
    media_match: MediaMatch,
    *,
    stage: ProgressStage,
    state: ProgressState,
    message: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "stage": stage.value,
        "state": state.value,
        "source_item_id": media_match.source_item_id,
        "decision": _enum_value(media_match.decision),
        "confidence": media_match.confidence,
        "reason_codes": media_match.reason_codes,
        "match_origin": media_match.match_origin,
    }
    if message:
        payload["message"] = message
    session.add(
        JobProgressEvent(
            job_id=job.id,
            event_type="match.updated",
            scope="MATCH",
            match_id=media_match.id,
            group_key=media_match.group_key,
            payload=payload,
        )
    )


def record_group_progress(
    session: AsyncSession,
    job: OrganizeJob,
    *,
    group_key: str,
    stage: ProgressStage,
    state: ProgressState,
    completed: int,
    total: int,
    message: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "stage": stage.value,
        "state": state.value,
        "completed": completed,
        "total": total,
    }
    if message:
        payload["message"] = message
    session.add(
        JobProgressEvent(
            job_id=job.id,
            event_type="group.progress",
            scope="GROUP",
            group_key=group_key,
            payload=payload,
        )
    )


def record_file_operation_progress(
    session: AsyncSession,
    job: OrganizeJob,
    operation: FileOperation,
    *,
    details: Mapping[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {
        "operation_type": _enum_value(operation.operation_type),
        "status": _enum_value(operation.status),
    }
    if operation.source_item_id:
        payload["source_item_id"] = operation.source_item_id
    if operation.error_message:
        payload["error_message"] = operation.error_message
    if details:
        payload.update(details)
    session.add(
        JobProgressEvent(
            job_id=job.id,
            event_type="file-operation.updated",
            scope="FILE_OPERATION",
            file_operation_id=operation.id,
            payload=payload,
        )
    )
