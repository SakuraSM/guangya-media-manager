from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

from app.domain import MatchDecision
from app.models import MediaMatch

PENDING_MATCH_DECISIONS = frozenset(
    {MatchDecision.REVIEW, MatchDecision.UNRESOLVED}
)
PENDING_VERSION_RECOMMENDATION = "PENDING"
SELECTED_VERSION_RECOMMENDATIONS = frozenset({"SINGLE", "CONFIRMED"})


def is_match_review_pending(media_match: MediaMatch) -> bool:
    """Return whether metadata or version selection still needs a decision."""

    return media_match.decision in PENDING_MATCH_DECISIONS or (
        media_match.decision != MatchDecision.IGNORED
        and media_match.version_recommendation == PENDING_VERSION_RECOMMENDATION
    )


def is_match_approved(media_match: MediaMatch) -> bool:
    return (
        media_match.decision
        in {MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED}
        and not is_match_review_pending(media_match)
        and media_match.version_recommendation in SELECTED_VERSION_RECOMMENDATIONS
    )


def decision_for_version(
    media_match: MediaMatch,
    decision: MatchDecision,
) -> MatchDecision:
    if media_match.version_recommendation == "NOT_SELECTED":
        return MatchDecision.IGNORED
    return decision


def pending_review_filter() -> ColumnElement[bool]:
    return or_(
        MediaMatch.decision.in_(PENDING_MATCH_DECISIONS),
        and_(
            MediaMatch.decision != MatchDecision.IGNORED,
            MediaMatch.version_recommendation == PENDING_VERSION_RECOMMENDATION,
        ),
    )


def reviewed_filter() -> ColumnElement[bool]:
    return or_(
        MediaMatch.decision == MatchDecision.IGNORED,
        and_(
            MediaMatch.decision.in_(
                {MatchDecision.AUTO_APPROVED, MatchDecision.APPROVED}
            ),
            MediaMatch.version_recommendation != PENDING_VERSION_RECOMMENDATION,
        ),
    )
