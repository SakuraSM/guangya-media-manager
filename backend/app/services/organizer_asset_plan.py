from dataclasses import dataclass
from pathlib import PurePosixPath

from app.domain import MediaType
from app.models import MediaEpisode, MediaMatch, MediaSeason
from app.providers.base import CloudNode
from app.services.organizer_cloud import MediaDirectories


@dataclass(frozen=True, slots=True)
class ImageAssetSpec:
    filename: str
    source_url: str
    parent: CloudNode
    asset_type: str


@dataclass(frozen=True, slots=True)
class ScrapeAssetContext:
    job_config: dict[str, object]
    media_match: MediaMatch
    directories: MediaDirectories
    season: MediaSeason | None
    episodes: tuple[MediaEpisode, ...]


def build_image_asset_specs(
    context: ScrapeAssetContext,
) -> tuple[ImageAssetSpec, ...]:
    entity = context.media_match.media_entity
    if entity is None:
        return ()
    specs: list[ImageAssetSpec] = []
    if context.job_config.get("download_poster", True) and entity.poster_url:
        specs.append(
            ImageAssetSpec(
                filename="poster.jpg",
                source_url=entity.poster_url,
                parent=context.directories.media_root,
                asset_type="POSTER",
            )
        )
    if context.job_config.get("download_fanart", True) and entity.backdrop_url:
        specs.append(
            ImageAssetSpec(
                filename="fanart.jpg",
                source_url=entity.backdrop_url,
                parent=context.directories.media_root,
                asset_type="FANART",
            )
        )
        if context.job_config.get("download_backdrop_alias", True):
            specs.append(
                ImageAssetSpec(
                    filename="backdrop.jpg",
                    source_url=entity.backdrop_url,
                    parent=context.directories.media_root,
                    asset_type="BACKDROP",
                )
            )
    specs.extend(_season_image_specs(context))
    specs.extend(_episode_image_specs(context))
    return tuple(specs)


def _season_image_specs(
    context: ScrapeAssetContext,
) -> list[ImageAssetSpec]:
    if context.media_match.media_type != MediaType.TV:
        return []
    if not context.job_config.get("download_season_poster", True):
        return []
    season_number = context.media_match.season_number
    if season_number is None:
        return []
    entity = context.media_match.media_entity
    source_url = (
        context.season.poster_url
        if context.season and context.season.poster_url
        else entity.poster_url
        if entity
        else None
    )
    if not source_url:
        return []
    specs = [
        ImageAssetSpec(
            filename=f"season{season_number:02d}-poster.jpg",
            source_url=source_url,
            parent=context.directories.media_root,
            asset_type="SEASON_POSTER",
        )
    ]
    if context.job_config.get("season_artwork_compat", True):
        specs.append(
            ImageAssetSpec(
                filename="poster.jpg",
                source_url=source_url,
                parent=context.directories.leaf,
                asset_type="SEASON_POSTER_COMPAT",
            )
        )
    return specs


def _episode_image_specs(
    context: ScrapeAssetContext,
) -> list[ImageAssetSpec]:
    if context.media_match.media_type != MediaType.TV:
        return []
    if not context.job_config.get("download_episode_thumb", True):
        return []
    episode = next(
        (item for item in context.episodes if item.still_url),
        None,
    )
    if episode is None or episode.still_url is None:
        return []
    stem = PurePosixPath(context.media_match.target_path).stem
    return [
        ImageAssetSpec(
            filename=f"{stem}.jpg",
            source_url=episode.still_url,
            parent=context.directories.leaf,
            asset_type="EPISODE_THUMB",
        )
    ]
