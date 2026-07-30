from datetime import date
from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

import pytest

from app.domain import MediaType, OperationStatus, OperationType
from app.models import (
    FileOperation,
    MediaEntity,
    MediaEpisode,
    MediaMatch,
    MediaSeason,
    OrganizeJob,
)
from app.providers.base import CloudNode
from app.services.organizer_asset_plan import (
    ScrapeAssetContext,
    build_image_asset_specs,
)
from app.services.organizer_asset_store import (
    CloudAssetStore,
    UploadAssetInput,
)
from app.services.organizer_cloud import MediaDirectories
from app.services.organizer_nfo import (
    render_episode_nfo,
    render_media_nfo,
)
from app.services.organizer_scrape_metadata import image_url_for_quality


def test_movie_nfo_contains_moviepilot_compatible_details() -> None:
    entity = MediaEntity(
        tmdb_id=157336,
        media_type=MediaType.MOVIE,
        title="星际穿越",
        original_title="Interstellar",
        year=2014,
        overview="探索宇宙。",
        metadata_snapshot={
            "release_date": "2014-11-07",
            "vote_average": 8.4,
            "vote_count": 36000,
            "runtime": 169,
            "genres": [{"name": "科幻"}, {"name": "剧情"}],
            "production_companies": [{"name": "Legendary Pictures"}],
            "production_countries": [{"name": "美国"}],
            "external_ids": {"imdb_id": "tt0816692"},
            "credits": {
                "crew": [
                    {"job": "Director", "name": "Christopher Nolan"},
                ],
                "cast": [
                    {
                        "name": "Matthew McConaughey",
                        "character": "Cooper",
                        "order": 0,
                    }
                ],
            },
        },
    )

    root = ElementTree.fromstring(render_media_nfo(entity))

    assert root.tag == "movie"
    assert root.findtext("premiered") == "2014-11-07"
    assert root.findtext("rating") == "8.4"
    assert root.findtext("runtime") == "169"
    assert [node.text for node in root.findall("genre")] == ["科幻", "剧情"]
    assert root.findtext("director") == "Christopher Nolan"
    assert root.findtext("actor/name") == "Matthew McConaughey"
    assert root.findtext("uniqueid[@type='imdb']") == "tt0816692"


def test_episode_nfo_uses_real_episode_metadata() -> None:
    entity = MediaEntity(
        tmdb_id=1396,
        media_type=MediaType.TV,
        title="绝命毒师",
        original_title="Breaking Bad",
    )
    season = MediaSeason(
        media_entity=entity,
        season_number=1,
        name="第 1 季",
    )
    episode = MediaEpisode(
        media_season=season,
        tmdb_id=62085,
        episode_number=3,
        name="袋中猫",
        overview="沃尔特处理危机。",
        air_date=date(2008, 2, 10),
        metadata_snapshot={"vote_average": 8.1, "vote_count": 120},
    )

    root = ElementTree.fromstring(render_episode_nfo(entity, episode))

    assert root.findtext("season") == "1"
    assert root.findtext("episode") == "3"
    assert root.findtext("aired") == "2008-02-10"
    assert root.findtext("rating") == "8.1"


def test_tv_asset_plan_creates_compatibility_artwork() -> None:
    entity = MediaEntity(
        tmdb_id=1396,
        media_type=MediaType.TV,
        title="绝命毒师",
        poster_url="https://image.tmdb.org/t/p/w500/poster.jpg",
        backdrop_url="https://image.tmdb.org/t/p/w500/backdrop.jpg",
    )
    season = MediaSeason(
        media_entity=entity,
        season_number=1,
        poster_url="https://image.tmdb.org/t/p/w500/season.jpg",
    )
    episode = MediaEpisode(
        media_season=season,
        episode_number=3,
        still_url="https://image.tmdb.org/t/p/w500/still.jpg",
    )
    media_match = MediaMatch(
        media_entity=entity,
        media_type=MediaType.TV,
        season_number=1,
        target_path="TV/绝命毒师 (2008)/Season 01/绝命毒师 - S01E03.mkv",
    )
    directories = MediaDirectories(
        media_root=_directory("series", "/TV/绝命毒师 (2008)"),
        leaf=_directory("season", "/TV/绝命毒师 (2008)/Season 01"),
    )

    specs = build_image_asset_specs(
        ScrapeAssetContext(
            job_config={},
            media_match=media_match,
            directories=directories,
            season=season,
            episodes=(episode,),
        )
    )
    targets = {(spec.parent.id, spec.filename, spec.asset_type) for spec in specs}

    assert ("series", "fanart.jpg", "FANART") in targets
    assert ("series", "backdrop.jpg", "BACKDROP") in targets
    assert ("series", "season01-poster.jpg", "SEASON_POSTER") in targets
    assert ("season", "poster.jpg", "SEASON_POSTER_COMPAT") in targets
    assert (
        "season",
        "绝命毒师 - S01E03.jpg",
        "EPISODE_THUMB",
    ) in targets


def test_original_image_quality_uses_tmdb_original_path() -> None:
    standard_url = "https://image.tmdb.org/t/p/w500/example.jpg"

    assert image_url_for_quality(standard_url, "ORIGINAL") == (
        "https://image.tmdb.org/t/p/original/example.jpg"
    )


@pytest.mark.asyncio
async def test_asset_retry_reuses_existing_operation_and_cloud_file() -> None:
    provider = MagicMock()
    provider.list_directory = AsyncMock(
        return_value=[
            CloudNode(
                id="asset-cloud-id",
                parent_id="media-root",
                name="poster.jpg",
                path="/staging/poster.jpg",
                is_directory=False,
            )
        ]
    )
    provider.upload_bytes = AsyncMock()
    existing_operation = FileOperation(
        job_id="job",
        source_item_id="source",
        operation_type=OperationType.UPLOAD,
        status=OperationStatus.FAILED,
        target_path="/staging/poster.jpg",
        idempotency_key="existing-key",
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[existing_operation, None])
    session.add = MagicMock()
    media_match = MediaMatch(
        id="match",
        source_item_id="source",
        media_entity_id="entity",
        media_type=MediaType.MOVIE,
    )

    await CloudAssetStore(provider).upload(
        session,
        UploadAssetInput(
            job=OrganizeJob(id="job"),
            media_match=media_match,
            parent=_directory("media-root", "/staging"),
            filename="poster.jpg",
            content=b"poster",
            asset_type="POSTER",
            source_url="https://image.tmdb.org/t/p/w500/poster.jpg",
        ),
    )

    provider.upload_bytes.assert_not_awaited()
    assert existing_operation.status == OperationStatus.COMPLETED
    assert existing_operation.error_message is None
    assert session.add.call_args_list[0].args[0] is existing_operation


def _directory(node_id: str, path: str) -> CloudNode:
    return CloudNode(
        id=node_id,
        parent_id="",
        name=path.rsplit("/", maxsplit=1)[-1],
        path=path,
        is_directory=True,
    )
