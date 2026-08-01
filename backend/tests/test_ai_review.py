from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.domain import MatchDecision, MediaType
from app.models import MediaMatch, SourceItem
from app.services.organizer_ai_review import _approve_group, _pending_groups


def test_ai_review_skips_records_that_are_already_approved() -> None:
    pending = _match("pending", MatchDecision.REVIEW)
    auto_approved = _match("automatic", MatchDecision.AUTO_APPROVED)
    approved = _match("manual", MatchDecision.APPROVED)

    groups = _pending_groups([pending, auto_approved, approved])

    assert groups == {pending.group_key: [pending]}


@pytest.mark.asyncio
async def test_ai_review_approves_work_group_without_changing_episode_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _match("first", MatchDecision.REVIEW, episode_number=1)
    second = _match("second", MatchDecision.REVIEW, episode_number=9)

    async def persist_candidate(*_: object, **__: object) -> SimpleNamespace:
        return SimpleNamespace(id="entity-42")

    monkeypatch.setattr(
        "app.services.organizer_ai_review.persist_candidate_payload",
        persist_candidate,
    )

    updated_items = await _approve_group(MagicMock(), [first, second], 42)

    assert updated_items == 2
    assert first.decision == MatchDecision.APPROVED
    assert second.decision == MatchDecision.APPROVED
    assert first.episode_numbers == [1]
    assert second.episode_numbers == [9]
    assert first.media_entity_id == "entity-42"
    assert "AI_REVIEW_APPROVED" in first.reason_codes


def _match(
    match_id: str,
    decision: MatchDecision,
    *,
    episode_number: int = 1,
) -> MediaMatch:
    source_item = SourceItem(
        id=f"source-{match_id}",
        filename=f"{episode_number:02d}.mkv",
        source_path=f"/媒体/示例剧/第一季/{episode_number:02d}.mkv",
        relative_path=f"示例剧/第一季/{episode_number:02d}.mkv",
        extension=".mkv",
    )
    return MediaMatch(
        id=match_id,
        source_item=source_item,
        media_type=MediaType.TV,
        parsed_title="示例剧",
        season_number=1,
        episode_numbers=[episode_number],
        decision=decision,
        group_key="TV|示例剧",
        candidates=[
            {
                "tmdb_id": 42,
                "title": "示例剧",
                "original_title": "Example Show",
                "year": 2026,
                "media_type": "TV",
                "score": 0.72,
                "poster_url": None,
                "backdrop_url": None,
                "overview": "",
            }
        ],
        release_info={},
        reason_codes=["AI_MANUAL_CONFIRMATION_REQUIRED"],
    )
