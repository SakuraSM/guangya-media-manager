from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import OperationStatus, OperationType
from app.models import (
    FileOperation,
    MediaAsset,
    MediaMatch,
    OrganizeJob,
)
from app.providers.base import CloudNode, CloudProvider
from app.services.organizer_support import make_idempotency_key
from app.services.progress_events import record_file_operation_progress

ASSET_DOWNLOAD_TIMEOUT_SECONDS = 20


@dataclass(frozen=True, slots=True)
class UploadAssetInput:
    job: OrganizeJob
    media_match: MediaMatch
    parent: CloudNode
    filename: str
    content: bytes
    asset_type: str
    source_url: str | None


class CloudAssetStore:
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider

    async def upload(
        self,
        session: AsyncSession,
        asset_input: UploadAssetInput,
    ) -> None:
        entity_id = asset_input.media_match.media_entity_id or "unknown"
        idempotency_key = make_idempotency_key(
            "asset",
            asset_input.job.id,
            entity_id,
            asset_input.parent.id,
            asset_input.filename,
        )
        existing = await session.scalar(
            select(FileOperation).where(FileOperation.idempotency_key == idempotency_key)
        )
        if existing and existing.status == OperationStatus.COMPLETED:
            return
        target_path = f"{asset_input.parent.path.rstrip('/')}/{asset_input.filename}"
        existing_nodes = await self._provider.list_directory(
            asset_input.parent.id,
            asset_input.parent.path,
        )
        uploaded = next(
            (node for node in existing_nodes if node.name == asset_input.filename),
            None,
        )
        if uploaded is None:
            uploaded = await self._provider.upload_bytes(
                asset_input.filename,
                asset_input.content,
                asset_input.parent.id,
            )
        if existing is None:
            existing = FileOperation(
                job_id=asset_input.job.id,
                source_item_id=asset_input.media_match.source_item_id,
                operation_type=OperationType.UPLOAD,
                target_path=target_path,
                idempotency_key=idempotency_key,
            )
        existing.source_item_id = asset_input.media_match.source_item_id
        existing.status = OperationStatus.COMPLETED
        existing.target_path = target_path
        existing.error_message = None
        session.add(existing)
        record_file_operation_progress(
            session,
            asset_input.job,
            existing,
            details={"asset_type": asset_input.asset_type},
        )

        media_asset = await session.scalar(
            select(MediaAsset).where(
                MediaAsset.job_id == asset_input.job.id,
                MediaAsset.asset_type == asset_input.asset_type,
                MediaAsset.target_path == target_path,
            )
        )
        if media_asset is None:
            media_asset = MediaAsset(
                job_id=asset_input.job.id,
                media_entity_id=asset_input.media_match.media_entity_id,
                asset_type=asset_input.asset_type,
                target_path=target_path,
            )
        media_asset.media_entity_id = asset_input.media_match.media_entity_id
        media_asset.cloud_file_id = uploaded.id
        media_asset.source_url = asset_input.source_url
        session.add(media_asset)


class AssetDownloadCache:
    def __init__(self) -> None:
        self._content_by_url: dict[str, bytes | None] = {}

    async def get(self, url: str) -> tuple[bytes | None, bool]:
        is_new_download = url not in self._content_by_url
        if is_new_download:
            self._content_by_url[url] = await _download_asset(url)
        return self._content_by_url[url], is_new_download


async def _download_asset(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=ASSET_DOWNLOAD_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError:
        return None
