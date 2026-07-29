from app.domain import MatchDecision, MediaType
from app.services.media_parser import ParsedMediaName
from app.services.organizer_scan import _merge_group_context, _summarize_decisions


def test_unresolved_matches_are_review_items_not_failures() -> None:
    approved, review, failed = _summarize_decisions(
        [
            MatchDecision.AUTO_APPROVED,
            MatchDecision.REVIEW,
            MatchDecision.UNRESOLVED,
        ]
    )

    assert approved == 1
    assert review == 2
    assert failed == 0


def test_group_context_preserves_external_failure_reason() -> None:
    parsed = ParsedMediaName(
        media_type=MediaType.TV,
        title="示例剧",
        year=None,
        season_number=1,
        episode_numbers=(2,),
        edition="",
        confidence=0.75,
        reason_codes=("DIRECTORY_CONTEXT",),
        is_ignored=False,
    )
    group = ParsedMediaName(
        media_type=MediaType.TV,
        title="示例剧",
        year=None,
        season_number=1,
        episode_numbers=(1,),
        edition="",
        confidence=0.75,
        reason_codes=("DIRECTORY_CONTEXT", "TMDB_FAILED"),
        is_ignored=False,
    )

    merged = _merge_group_context(parsed, group)

    assert "TMDB_FAILED" in merged.reason_codes
    assert merged.episode_numbers == (2,)
