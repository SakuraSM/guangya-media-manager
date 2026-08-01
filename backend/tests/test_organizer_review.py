from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain import JobStatus, MatchDecision, MediaType
from app.models import MediaMatch, OrganizeJob, SourceItem
from app.schemas import ManualMatchRequest, UpdateMatchRequest
from app.services.organizer import (
    ManualEpisodeMappingContext,
    OrganizerError,
    OrganizerService,
    _group_episode_mapping,
    _manual_episode_mapping,
)


class ScalarResult:
    def __init__(self, items: list[MediaMatch]) -> None:
        self._items = items

    def all(self) -> list[MediaMatch]:
        return self._items


async def test_group_update_validates_all_candidates_before_mutating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_match = _match(
        match_id="first",
        filename="S01E01.mkv",
        candidate_id=42,
    )
    second_match = _match(
        match_id="second",
        filename="S01E02.mkv",
        candidate_id=7,
    )
    job = OrganizeJob(id="job", status=JobStatus.REVIEW_REQUIRED)

    async def load_test_job(*_: object, **__: object) -> OrganizeJob:
        return job

    monkeypatch.setattr("app.services.organizer.load_job", load_test_job)
    session = MagicMock()
    session.scalars = AsyncMock(return_value=ScalarResult([first_match, second_match]))
    session.commit = AsyncMock()
    service = object.__new__(OrganizerService)

    with pytest.raises(OrganizerError, match="候选不存在"):
        await service.update_group_matches(
            job_id=job.id,
            group_key="TV|示例剧|2026",
            request=UpdateMatchRequest(
                decision=MatchDecision.APPROVED,
                candidate_tmdb_id=42,
            ),
            session=session,
        )

    assert first_match.decision == MatchDecision.REVIEW
    assert second_match.decision == MatchDecision.REVIEW
    session.commit.assert_not_awaited()


def test_group_manual_match_preserves_each_sibling_episode_mapping() -> None:
    anchor = _match(
        match_id="first",
        filename="S01E01.mkv",
        candidate_id=42,
    )
    anchor.season_number = 1
    anchor.episode_numbers = [1]
    sibling = _match(
        match_id="second",
        filename="S02E08.mkv",
        candidate_id=42,
    )
    sibling.season_number = 2
    sibling.episode_numbers = [8]
    request = ManualMatchRequest(
        tmdb_id=42,
        title="纠正后的剧名",
        media_type=MediaType.TV,
        season_number=3,
        episode_numbers=[6],
    )

    assert _group_episode_mapping(
        media_match=anchor,
        anchor_match_id=anchor.id,
        request=request,
        source_root="/媒体",
    ) == (3, (6,))
    assert _group_episode_mapping(
        media_match=sibling,
        anchor_match_id=anchor.id,
        request=request,
        source_root="/媒体",
    ) == (2, (8,))


def test_group_manual_match_reparses_missing_sibling_mapping() -> None:
    sibling = _match(
        match_id="second",
        filename="Example.S01E09.mkv",
        candidate_id=42,
    )
    sibling.source_item.source_path = "/媒体/示例剧/Season 01/Example.S01E09.mkv"
    request = ManualMatchRequest(
        tmdb_id=42,
        title="示例剧",
        media_type=MediaType.TV,
        season_number=1,
        episode_numbers=[1],
    )

    assert _group_episode_mapping(
        media_match=sibling,
        anchor_match_id="first",
        request=request,
        source_root="/媒体",
    ) == (1, (9,))


def test_manual_match_infers_numeric_episode_from_parent_season() -> None:
    media_match = _match(
        match_id="numeric",
        filename="12.mkv",
        candidate_id=42,
    )
    media_match.season_number = None
    media_match.episode_numbers = []
    media_match.source_item.source_path = "/媒体/示例剧/第2季/12.mkv"
    request = ManualMatchRequest(
        tmdb_id=42,
        title="示例剧",
        media_type=MediaType.TV,
    )

    assert _manual_episode_mapping(
        ManualEpisodeMappingContext(
            media_match=media_match,
            request=request,
            source_root="/媒体",
        )
    ) == (2, (12,))


def _match(
    *,
    match_id: str,
    filename: str,
    candidate_id: int,
) -> MediaMatch:
    source_item = SourceItem(
        id=f"source-{match_id}",
        filename=filename,
        extension=".mkv",
    )
    return MediaMatch(
        id=match_id,
        source_item=source_item,
        media_type=MediaType.TV,
        decision=MatchDecision.REVIEW,
        group_key="TV|示例剧|2026",
        candidates=[
            {
                "tmdb_id": candidate_id,
                "title": "示例剧",
                "original_title": "Example",
                "year": 2026,
                "media_type": "TV",
                "score": 0.9,
                "poster_url": None,
                "backdrop_url": None,
                "overview": "",
            }
        ],
    )
