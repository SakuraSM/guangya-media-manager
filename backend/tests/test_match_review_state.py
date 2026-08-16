from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain import MatchDecision
from app.models import Base, MediaMatch, OrganizeJob, SourceItem
from app.services.match_review_state import (
    decision_for_version,
    is_match_approved,
    is_match_review_pending,
    pending_review_filter,
    reviewed_filter,
)


def _match(
    decision: MatchDecision,
    version_recommendation: str = "SINGLE",
) -> MediaMatch:
    return MediaMatch(
        source_item_id="source-item",
        decision=decision,
        version_recommendation=version_recommendation,
    )


def test_approved_match_with_pending_version_still_needs_review() -> None:
    media_match = _match(MatchDecision.APPROVED, "PENDING")

    assert is_match_review_pending(media_match) is True
    assert is_match_approved(media_match) is False


def test_confirmed_version_moves_approved_match_to_reviewed() -> None:
    media_match = _match(MatchDecision.APPROVED, "CONFIRMED")

    assert is_match_review_pending(media_match) is False
    assert is_match_approved(media_match) is True


def test_ignored_match_is_terminal_even_with_stale_version_state() -> None:
    media_match = _match(MatchDecision.IGNORED, "PENDING")

    assert is_match_review_pending(media_match) is False
    assert is_match_approved(media_match) is False


def test_unselected_version_cannot_be_reapproved_by_metadata_review() -> None:
    media_match = _match(MatchDecision.IGNORED, "NOT_SELECTED")

    assert decision_for_version(media_match, MatchDecision.APPROVED) == MatchDecision.IGNORED
    assert is_match_approved(media_match) is False


async def test_review_filters_use_the_same_version_pending_semantics() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        job = OrganizeJob(
            name="审核口径测试",
            source_directory_id="source",
            source_directory_path="/source",
            target_directory_id="target",
            target_directory_path="/target",
        )
        session.add(job)
        await session.flush()
        records = [
            ("approved-pending", MatchDecision.APPROVED, "PENDING"),
            ("approved-confirmed", MatchDecision.APPROVED, "CONFIRMED"),
            ("metadata-review", MatchDecision.REVIEW, "SINGLE"),
            ("ignored-stale", MatchDecision.IGNORED, "PENDING"),
        ]
        for cloud_file_id, decision, version_recommendation in records:
            source_item = SourceItem(
                job_id=job.id,
                cloud_file_id=cloud_file_id,
                filename=f"{cloud_file_id}.mkv",
                source_path=f"/source/{cloud_file_id}.mkv",
                relative_path=f"{cloud_file_id}.mkv",
            )
            session.add(source_item)
            await session.flush()
            session.add(
                MediaMatch(
                    source_item_id=source_item.id,
                    decision=decision,
                    version_recommendation=version_recommendation,
                )
            )
        await session.commit()

        pending = list(
            (await session.scalars(select(MediaMatch).where(pending_review_filter()))).all()
        )
        reviewed = list(
            (await session.scalars(select(MediaMatch).where(reviewed_filter()))).all()
        )

    await engine.dispose()

    assert {(item.decision, item.version_recommendation) for item in pending} == {
        (MatchDecision.APPROVED, "PENDING"),
        (MatchDecision.REVIEW, "SINGLE"),
    }
    assert {(item.decision, item.version_recommendation) for item in reviewed} == {
        (MatchDecision.APPROVED, "CONFIRMED"),
        (MatchDecision.IGNORED, "PENDING"),
    }
