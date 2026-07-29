from pathlib import PurePosixPath

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import MediaType, OperationStatus, OperationType
from app.models import (
    FileOperation,
    MediaAsset,
    MediaMatch,
    OrganizeJob,
)
from app.providers.base import CloudNode, CloudProvider
from app.services.organizer_cloud import MediaDirectories
from app.services.organizer_support import make_idempotency_key, render_nfo

ASSET_DOWNLOAD_TIMEOUT_SECONDS = 20


class AssetScraper:
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider

    async def scrape(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        matches: list[MediaMatch],
        directories: dict[str, MediaDirectories],
    ) -> int:
        warning_count = 0
        for media_match in matches:
            entity = media_match.media_entity
            if entity is None:
                continue
            media_directories = directories[media_match.id]
            if job.config.get("generate_nfo", True):
                await self._upload_nfo_files(
                    session, job, media_match, media_directories
                )
            warning_count += await self._upload_images(
                session, job, media_match, media_directories
            )
        await session.commit()
        return warning_count

    async def _upload_nfo_files(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        media_match: MediaMatch,
        directories: MediaDirectories,
    ) -> None:
        entity = media_match.media_entity
        if entity is None:
            return
        nfo_content = render_nfo(entity).encode()
        if media_match.media_type == MediaType.TV:
            episode_name = f"{PurePosixPath(media_match.target_path).stem}.nfo"
            await self._upload_asset(
                session=session,
                job=job,
                media_match=media_match,
                parent=directories.leaf,
                filename=episode_name,
                content=nfo_content,
                asset_type="EPISODE_NFO",
                source_url=None,
            )
            await self._upload_asset(
                session=session,
                job=job,
                media_match=media_match,
                parent=directories.media_root,
                filename="tvshow.nfo",
                content=nfo_content,
                asset_type="TVSHOW_NFO",
                source_url=None,
            )
            return
        await self._upload_asset(
            session=session,
            job=job,
            media_match=media_match,
            parent=directories.media_root,
            filename="movie.nfo",
            content=nfo_content,
            asset_type="MOVIE_NFO",
            source_url=None,
        )

    async def _upload_images(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        media_match: MediaMatch,
        directories: MediaDirectories,
    ) -> int:
        entity = media_match.media_entity
        if entity is None:
            return 0
        image_specs: list[tuple[str, str | None, CloudNode, str]] = []
        if job.config.get("download_poster", True):
            image_specs.append(
                ("poster.jpg", entity.poster_url, directories.media_root, "POSTER")
            )
        if job.config.get("download_fanart", True):
            image_specs.append(
                ("fanart.jpg", entity.backdrop_url, directories.media_root, "FANART")
            )
        if (
            media_match.media_type == MediaType.TV
            and job.config.get("download_season_poster", True)
        ):
            season_number = media_match.season_number or 1
            image_specs.append(
                (
                    f"season{season_number:02d}-poster.jpg",
                    entity.poster_url,
                    directories.leaf,
                    "SEASON_POSTER",
                )
            )

        warning_count = 0
        for filename, source_url, parent, asset_type in image_specs:
            if not source_url:
                continue
            if not source_url.startswith(("http://", "https://")) or "/demo-" in source_url:
                continue
            content = await _download_asset(source_url)
            if content is None:
                warning_count += 1
                continue
            await self._upload_asset(
                session=session,
                job=job,
                media_match=media_match,
                parent=parent,
                filename=filename,
                content=content,
                asset_type=asset_type,
                source_url=source_url,
            )
        return warning_count

    async def _upload_asset(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        media_match: MediaMatch,
        parent: CloudNode,
        filename: str,
        content: bytes,
        asset_type: str,
        source_url: str | None,
    ) -> None:
        entity_id = media_match.media_entity_id or "unknown"
        idempotency_key = make_idempotency_key(
            "asset", job.id, entity_id, parent.id, filename
        )
        existing = await session.scalar(
            select(FileOperation).where(
                FileOperation.idempotency_key == idempotency_key
            )
        )
        if existing and existing.status == OperationStatus.COMPLETED:
            return
        uploaded = await self._provider.upload_bytes(filename, content, parent.id)
        session.add(
            FileOperation(
                job_id=job.id,
                source_item_id=media_match.source_item_id,
                operation_type=OperationType.UPLOAD,
                status=OperationStatus.COMPLETED,
                target_path=f"{parent.path.rstrip('/')}/{filename}",
                idempotency_key=idempotency_key,
            )
        )
        session.add(
            MediaAsset(
                job_id=job.id,
                media_entity_id=media_match.media_entity_id,
                asset_type=asset_type,
                cloud_file_id=uploaded.id,
                target_path=f"{parent.path.rstrip('/')}/{filename}",
                source_url=source_url,
            )
        )


async def _download_asset(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(
            timeout=ASSET_DOWNLOAD_TIMEOUT_SECONDS
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError:
        return None
