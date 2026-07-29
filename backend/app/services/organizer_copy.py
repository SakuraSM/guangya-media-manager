from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import OperationStatus, OperationType
from app.models import FileOperation, OrganizeJob, SourceItem
from app.providers.base import CloudNode, CloudProvider
from app.services.organizer_cloud import wait_for_provider_task
from app.services.organizer_support import OrganizerError, make_idempotency_key


class CopyExecutor:
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider

    async def copy_and_rename(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        source_item: SourceItem,
        target_directory: CloudNode,
        final_filename: str,
    ) -> bool:
        target_path = f"{target_directory.path.rstrip('/')}/{final_filename}"
        idempotency_key = make_idempotency_key(
            "copy", job.id, source_item.id, target_path
        )
        operation = await session.scalar(
            select(FileOperation).where(
                FileOperation.idempotency_key == idempotency_key
            )
        )
        if operation and operation.status == OperationStatus.COMPLETED:
            return False
        if operation is None:
            operation = FileOperation(
                job_id=job.id,
                source_item_id=source_item.id,
                operation_type=OperationType.COPY,
                source_path=source_item.source_path,
                target_path=target_path,
                idempotency_key=idempotency_key,
            )
        operation.status = OperationStatus.RUNNING
        session.add(operation)
        await session.commit()

        existing = await self._find_existing(target_directory, final_filename)
        if existing is not None:
            if source_item.fingerprint and existing.fingerprint == source_item.fingerprint:
                operation.status = OperationStatus.SKIPPED
                await session.commit()
                return False
            raise OrganizerError(f"Staging path conflict: {target_path}")

        provider_task = await self._provider.copy_items(
            [source_item.cloud_file_id], target_directory.id
        )
        operation.provider_task_id = provider_task.task_id
        await wait_for_provider_task(self._provider, provider_task.task_id)
        copied_nodes = await self._provider.resolve_task_nodes(
            provider_task.task_id, target_directory.path
        )
        if len(copied_nodes) != 1:
            raise OrganizerError("Unable to resolve copied cloud file")
        copied_node = copied_nodes[0]
        if copied_node.name != final_filename:
            await self._provider.rename_item(copied_node.id, final_filename)
            session.add(
                FileOperation(
                    job_id=job.id,
                    source_item_id=source_item.id,
                    operation_type=OperationType.RENAME,
                    source_path=copied_node.path,
                    target_path=target_path,
                    status=OperationStatus.COMPLETED,
                    idempotency_key=make_idempotency_key(
                        "rename", job.id, source_item.id, final_filename
                    ),
                )
            )
        operation.status = OperationStatus.COMPLETED
        await session.commit()
        return True

    async def _find_existing(
        self, target_directory: CloudNode, filename: str
    ) -> CloudNode | None:
        nodes = await self._provider.list_directory(
            target_directory.id, target_directory.path
        )
        return next((node for node in nodes if node.name == filename), None)
