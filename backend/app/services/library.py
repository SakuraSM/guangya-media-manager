from dataclasses import dataclass
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import JobStatus, MatchDecision, MediaType
from app.models import (
    MediaEntity,
    MediaEpisode,
    MediaMatch,
    MediaMatchEpisode,
    MediaSeason,
    OrganizeJob,
    SourceItem,
)
from app.schemas import LibraryEpisode, LibraryItem, LibraryItemDetail, LibrarySeason


@dataclass(frozen=True)
class SeasonDescriptor:
    id: str
    season_number: int
    name: str
    overview: str
    poster_url: str | None


async def load_library_items(session: AsyncSession) -> list[LibraryItem]:
    statement = (
        select(MediaMatch, MediaEntity, OrganizeJob)
        .join(MediaEntity, MediaEntity.id == MediaMatch.media_entity_id)
        .join(SourceItem, SourceItem.id == MediaMatch.source_item_id)
        .join(OrganizeJob, OrganizeJob.id == SourceItem.job_id)
        .where(
            OrganizeJob.status.in_([JobStatus.COMPLETED, JobStatus.PARTIAL_FAILED]),
            MediaMatch.decision.in_([MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED]),
        )
        .order_by(OrganizeJob.updated_at.desc())
    )
    rows = (await session.execute(statement)).all()
    items_by_entity: dict[str, LibraryItem] = {}
    match_ids_by_entity: dict[str, set[str]] = {}
    season_keys_by_entity: dict[str, set[int]] = {}
    episode_keys_by_entity: dict[str, set[tuple[int, int]]] = {}

    for media_match, entity, job in rows:
        media_type = MediaType(entity.media_type)
        if entity.id not in items_by_entity:
            items_by_entity[entity.id] = LibraryItem(
                id=entity.id,
                tmdb_id=entity.tmdb_id,
                title=entity.title,
                year=entity.year,
                media_type=media_type,
                poster_url=entity.poster_url,
                target_path=_library_root_path(media_match.target_path, media_type),
                completed_at=job.updated_at,
                file_count=0,
                season_count=0,
                episode_count=0,
            )
            match_ids_by_entity[entity.id] = set()
            season_keys_by_entity[entity.id] = set()
            episode_keys_by_entity[entity.id] = set()

        match_ids_by_entity[entity.id].add(media_match.id)
        if media_type != MediaType.TV or media_match.season_number is None:
            continue
        season_keys_by_entity[entity.id].add(media_match.season_number)
        episode_keys_by_entity[entity.id].update(
            (media_match.season_number, episode_number)
            for episode_number in media_match.episode_numbers
        )

    for entity_id, library_item in items_by_entity.items():
        library_item.file_count = len(match_ids_by_entity[entity_id])
        library_item.season_count = len(season_keys_by_entity[entity_id])
        library_item.episode_count = len(episode_keys_by_entity[entity_id])

    return list(items_by_entity.values())


async def load_library_detail(
    session: AsyncSession,
    entity_id: str,
) -> LibraryItemDetail | None:
    statement = (
        select(MediaMatch, MediaEntity, SourceItem, OrganizeJob)
        .join(MediaEntity, MediaEntity.id == MediaMatch.media_entity_id)
        .join(SourceItem, SourceItem.id == MediaMatch.source_item_id)
        .join(OrganizeJob, OrganizeJob.id == SourceItem.job_id)
        .where(
            MediaEntity.id == entity_id,
            OrganizeJob.status.in_([JobStatus.COMPLETED, JobStatus.PARTIAL_FAILED]),
            MediaMatch.decision.in_([MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED]),
        )
        .order_by(OrganizeJob.updated_at.desc())
    )
    rows = (await session.execute(statement)).all()
    if not rows:
        return None

    first_match, entity, _, latest_job = rows[0]
    media_type = MediaType(entity.media_type)
    seasons_by_number: dict[int, LibrarySeason] = {}
    seen_episode_keys: set[tuple[int, int]] = set()

    if media_type == MediaType.TV:
        match_ids = [media_match.id for media_match, _, _, _ in rows]
        episode_records_by_match = await _load_episode_records(
            session,
            entity_id=entity_id,
            match_ids=match_ids,
        )
        for media_match, _, source_item, _ in rows:
            episode_records = episode_records_by_match.get(media_match.id, [])
            if episode_records:
                _append_persisted_episodes(
                    media_match=media_match,
                    source_item=source_item,
                    episode_records=episode_records,
                    seasons_by_number=seasons_by_number,
                    seen_episode_keys=seen_episode_keys,
                )
                continue
            _append_fallback_episodes(
                entity_id=entity_id,
                media_match=media_match,
                source_item=source_item,
                seasons_by_number=seasons_by_number,
                seen_episode_keys=seen_episode_keys,
            )

    seasons = sorted(seasons_by_number.values(), key=lambda season: season.season_number)
    for season in seasons:
        season.episodes.sort(key=lambda episode: episode.episode_number)
        season.episode_count = len(season.episodes)

    return LibraryItemDetail(
        id=entity.id,
        tmdb_id=entity.tmdb_id,
        title=entity.title,
        year=entity.year,
        media_type=media_type,
        poster_url=entity.poster_url,
        target_path=_library_root_path(first_match.target_path, media_type),
        completed_at=latest_job.updated_at,
        file_count=len({media_match.id for media_match, _, _, _ in rows}),
        season_count=len(seasons),
        episode_count=sum(season.episode_count for season in seasons),
        overview=entity.overview,
        backdrop_url=entity.backdrop_url,
        seasons=seasons,
    )


async def _load_episode_records(
    session: AsyncSession,
    *,
    entity_id: str,
    match_ids: list[str],
) -> dict[str, list[tuple[MediaEpisode, MediaSeason]]]:
    statement = (
        select(MediaMatchEpisode.media_match_id, MediaEpisode, MediaSeason)
        .join(MediaEpisode, MediaEpisode.id == MediaMatchEpisode.media_episode_id)
        .join(MediaSeason, MediaSeason.id == MediaEpisode.media_season_id)
        .where(
            MediaMatchEpisode.media_match_id.in_(match_ids),
            MediaSeason.media_entity_id == entity_id,
        )
        .order_by(MediaSeason.season_number, MediaEpisode.episode_number)
    )
    rows = (await session.execute(statement)).all()
    records_by_match: dict[str, list[tuple[MediaEpisode, MediaSeason]]] = {}
    for match_id, episode, season in rows:
        records_by_match.setdefault(match_id, []).append((episode, season))
    return records_by_match


def _append_persisted_episodes(
    *,
    media_match: MediaMatch,
    source_item: SourceItem,
    episode_records: list[tuple[MediaEpisode, MediaSeason]],
    seasons_by_number: dict[int, LibrarySeason],
    seen_episode_keys: set[tuple[int, int]],
) -> None:
    for episode, season in episode_records:
        _append_library_episode(
            seasons_by_number=seasons_by_number,
            seen_episode_keys=seen_episode_keys,
            season=SeasonDescriptor(
                id=season.id,
                season_number=season.season_number,
                name=season.name,
                overview=season.overview,
                poster_url=season.poster_url,
            ),
            episode=LibraryEpisode(
                id=episode.id,
                episode_number=episode.episode_number,
                title=episode.name,
                overview=episode.overview,
                air_date=episode.air_date,
                still_url=episode.still_url,
                source_filename=source_item.filename,
                target_path=media_match.target_path,
            ),
        )


def _library_root_path(target_path: str, media_type: MediaType) -> str:
    if not target_path:
        return ""
    path = PurePosixPath(target_path)
    parent_index = 1 if media_type == MediaType.TV else 0
    if len(path.parents) <= parent_index:
        return str(path.parent)
    return str(path.parents[parent_index])


def _append_library_episode(
    *,
    seasons_by_number: dict[int, LibrarySeason],
    seen_episode_keys: set[tuple[int, int]],
    season: SeasonDescriptor,
    episode: LibraryEpisode,
) -> None:
    episode_key = (season.season_number, episode.episode_number)
    if episode_key in seen_episode_keys:
        return
    seen_episode_keys.add(episode_key)
    library_season = seasons_by_number.setdefault(
        season.season_number,
        LibrarySeason(
            id=season.id,
            season_number=season.season_number,
            name=season.name,
            overview=season.overview,
            poster_url=season.poster_url,
            episode_count=0,
            episodes=[],
        ),
    )
    library_season.episodes.append(episode)


def _append_fallback_episodes(
    *,
    entity_id: str,
    media_match: MediaMatch,
    source_item: SourceItem,
    seasons_by_number: dict[int, LibrarySeason],
    seen_episode_keys: set[tuple[int, int]],
) -> None:
    if media_match.season_number is None:
        return
    season_number = media_match.season_number
    fallback_season = SeasonDescriptor(
        id=f"{entity_id}:season:{season_number}",
        season_number=season_number,
        name="",
        overview="",
        poster_url=None,
    )
    episode_title = (
        media_match.episode_title if len(media_match.episode_numbers) == 1 else ""
    )
    for episode_number in media_match.episode_numbers:
        _append_library_episode(
            seasons_by_number=seasons_by_number,
            seen_episode_keys=seen_episode_keys,
            season=fallback_season,
            episode=LibraryEpisode(
                id=f"{media_match.id}:episode:{episode_number}",
                episode_number=episode_number,
                title=episode_title,
                overview="",
                air_date=media_match.episode_date,
                still_url=None,
                source_filename=source_item.filename,
                target_path=media_match.target_path,
            ),
        )
