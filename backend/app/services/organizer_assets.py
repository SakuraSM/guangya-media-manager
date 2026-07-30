from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain import MediaType
from app.models import (
    AuditEvent,
    MediaEpisode,
    MediaMatch,
    MediaMatchEpisode,
    MediaSeason,
    OrganizeJob,
)
from app.providers.base import CloudProvider
from app.services.metadata import MetadataServiceError, TmdbService
from app.services.organizer_asset_plan import (
    ScrapeAssetContext,
    build_image_asset_specs,
)
from app.services.organizer_asset_store import (
    AssetDownloadCache,
    CloudAssetStore,
    UploadAssetInput,
)
from app.services.organizer_cloud import MediaDirectories
from app.services.organizer_nfo import (
    episode_nfo_filename,
    render_episode_nfo,
    render_media_nfo,
    render_season_nfo,
)
from app.services.organizer_scrape_metadata import (
    DEFAULT_METADATA_LANGUAGE,
    image_url_for_quality,
    refresh_entity_metadata,
)


class AssetScraper:
    def __init__(
        self,
        provider: CloudProvider,
        tmdb_service: TmdbService,
    ) -> None:
        self._tmdb_service = tmdb_service
        self._asset_store = CloudAssetStore(provider)

    async def scrape(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        matches: list[MediaMatch],
        directories: dict[str, MediaDirectories],
    ) -> int:
        warning_count = 0
        refreshed_entity_ids: set[str] = set()
        download_cache = AssetDownloadCache()
        for media_match in matches:
            entity = media_match.media_entity
            if entity is None:
                continue
            if entity.id not in refreshed_entity_ids:
                warning_count += await self._refresh_entity(
                    session,
                    job,
                    media_match,
                )
                refreshed_entity_ids.add(entity.id)
            media_directories = directories[media_match.id]
            season = await self._load_season(session, media_match)
            episodes = await self._load_episodes(session, media_match)
            if job.config.get("generate_nfo", True):
                await self._upload_nfo_files(
                    session=session,
                    job=job,
                    media_match=media_match,
                    directories=media_directories,
                    season=season,
                    episodes=episodes,
                )
            warning_count += await self._upload_images(
                session=session,
                job=job,
                media_match=media_match,
                directories=media_directories,
                season=season,
                episodes=episodes,
                download_cache=download_cache,
            )
        await session.commit()
        return warning_count

    async def _refresh_entity(
        self,
        session: AsyncSession,
        job: OrganizeJob,
        media_match: MediaMatch,
    ) -> int:
        entity = media_match.media_entity
        if entity is None:
            return 0
        language_value = job.config.get(
            "scrape_metadata_language",
            DEFAULT_METADATA_LANGUAGE,
        )
        language = language_value if isinstance(language_value, str) else DEFAULT_METADATA_LANGUAGE
        try:
            await refresh_entity_metadata(
                self._tmdb_service,
                entity,
                language,
            )
        except MetadataServiceError as error:
            session.add(
                AuditEvent(
                    job_id=job.id,
                    event_type="SCRAPE_METADATA_DETAIL_FAILED",
                    message=f"TMDB 详情获取失败：{entity.title}",
                    severity="warning",
                    details={"reason_code": error.reason_code},
                )
            )
            return 1
        return 0

    async def _upload_nfo_files(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        media_match: MediaMatch,
        directories: MediaDirectories,
        season: MediaSeason | None,
        episodes: list[MediaEpisode],
    ) -> None:
        entity = media_match.media_entity
        if entity is None:
            return
        nfo_content = render_media_nfo(entity).encode()
        if media_match.media_type == MediaType.TV:
            await self._asset_store.upload(
                session,
                UploadAssetInput(
                    job=job,
                    media_match=media_match,
                    parent=directories.media_root,
                    filename="tvshow.nfo",
                    content=nfo_content,
                    asset_type="TVSHOW_NFO",
                    source_url=None,
                ),
            )
            if season is not None:
                await self._asset_store.upload(
                    session,
                    UploadAssetInput(
                        job=job,
                        media_match=media_match,
                        parent=directories.leaf,
                        filename="season.nfo",
                        content=render_season_nfo(season).encode(),
                        asset_type="SEASON_NFO",
                        source_url=None,
                    ),
                )
            if episodes:
                for episode in episodes:
                    episode_name = episode_nfo_filename(
                        media_match,
                        episode,
                        len(episodes),
                    )
                    await self._asset_store.upload(
                        session,
                        UploadAssetInput(
                            job=job,
                            media_match=media_match,
                            parent=directories.leaf,
                            filename=episode_name,
                            content=render_episode_nfo(entity, episode).encode(),
                            asset_type="EPISODE_NFO",
                            source_url=None,
                        ),
                    )
            else:
                episode_name = f"{PurePosixPath(media_match.target_path).stem}.nfo"
                await self._asset_store.upload(
                    session,
                    UploadAssetInput(
                        job=job,
                        media_match=media_match,
                        parent=directories.leaf,
                        filename=episode_name,
                        content=nfo_content,
                        asset_type="EPISODE_NFO",
                        source_url=None,
                    ),
                )
            return
        await self._asset_store.upload(
            session,
            UploadAssetInput(
                job=job,
                media_match=media_match,
                parent=directories.media_root,
                filename="movie.nfo",
                content=nfo_content,
                asset_type="MOVIE_NFO",
                source_url=None,
            ),
        )

    async def _upload_images(
        self,
        *,
        session: AsyncSession,
        job: OrganizeJob,
        media_match: MediaMatch,
        directories: MediaDirectories,
        season: MediaSeason | None,
        episodes: list[MediaEpisode],
        download_cache: AssetDownloadCache,
    ) -> int:
        warning_count = 0
        image_specs = build_image_asset_specs(
            ScrapeAssetContext(
                job_config=job.config,
                media_match=media_match,
                directories=directories,
                season=season,
                episodes=tuple(episodes),
            )
        )
        image_quality_value = job.config.get(
            "scrape_image_quality",
            "STANDARD",
        )
        image_quality = image_quality_value if isinstance(image_quality_value, str) else "STANDARD"
        for image_spec in image_specs:
            source_url = image_url_for_quality(
                image_spec.source_url,
                image_quality,
            )
            if not source_url.startswith(("http://", "https://")) or "/demo-" in source_url:
                continue
            content, is_new_download = await download_cache.get(source_url)
            if content is None:
                if is_new_download:
                    warning_count += 1
                continue
            await self._asset_store.upload(
                session,
                UploadAssetInput(
                    job=job,
                    media_match=media_match,
                    parent=image_spec.parent,
                    filename=image_spec.filename,
                    content=content,
                    asset_type=image_spec.asset_type,
                    source_url=source_url,
                ),
            )
        return warning_count

    async def _load_season(
        self, session: AsyncSession, media_match: MediaMatch
    ) -> MediaSeason | None:
        if media_match.media_entity_id is None or media_match.season_number is None:
            return None
        season: MediaSeason | None = await session.scalar(
            select(MediaSeason).where(
                MediaSeason.media_entity_id == media_match.media_entity_id,
                MediaSeason.season_number == media_match.season_number,
            )
        )
        return season

    async def _load_episodes(
        self, session: AsyncSession, media_match: MediaMatch
    ) -> list[MediaEpisode]:
        statement = (
            select(MediaEpisode)
            .join(
                MediaMatchEpisode,
                MediaMatchEpisode.media_episode_id == MediaEpisode.id,
            )
            .options(selectinload(MediaEpisode.media_season))
            .where(MediaMatchEpisode.media_match_id == media_match.id)
            .order_by(MediaMatchEpisode.ordinal)
        )
        return list((await session.scalars(statement)).all())
