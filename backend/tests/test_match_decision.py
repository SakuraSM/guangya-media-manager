from app.domain import MatchDecision, MatchOrigin, MediaType
from app.services.match_decision import DecisionOutcome, decide_identity_match


def test_explicit_identity_with_matching_type_is_auto_approved() -> None:
    result = decide_identity_match(
        origin=MatchOrigin.PATH_ID,
        identity_resolved=True,
        expected_type=MediaType.TV,
        actual_type=MediaType.TV,
        has_local_title=False,
        has_conflict=False,
        auto_approve_enabled=True,
    )

    assert result.outcome == DecisionOutcome.ACCEPT
    assert result.decision == MatchDecision.AUTO_APPROVED
    assert result.reasons[0].code == "EXPLICIT_ID_RESOLVED"


def test_local_title_without_identity_requires_review() -> None:
    result = decide_identity_match(
        origin=MatchOrigin.NFO,
        identity_resolved=False,
        expected_type=MediaType.TV,
        actual_type=MediaType.TV,
        has_local_title=True,
        has_conflict=False,
        auto_approve_enabled=True,
    )

    assert result.outcome == DecisionOutcome.WARN
    assert result.decision == MatchDecision.REVIEW


def test_path_and_nfo_identity_conflict_blocks_automatic_execution() -> None:
    result = decide_identity_match(
        origin=MatchOrigin.PATH_ID,
        identity_resolved=True,
        expected_type=MediaType.MOVIE,
        actual_type=MediaType.MOVIE,
        has_local_title=False,
        has_conflict=True,
        auto_approve_enabled=True,
    )

    assert result.outcome == DecisionOutcome.REJECT
    assert result.decision == MatchDecision.UNRESOLVED
    assert result.reasons[0].code == "IDENTITY_CONFLICT"
