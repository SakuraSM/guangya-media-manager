from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain import JobStatus, MatchDecision, MediaType
from app.models import Base, MediaMatch, OrganizeJob, SourceItem
from app.services.organizer_execute import ExecutionWorkflow


async def test_partial_execution_selects_only_unpublished_approved_matches() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        job = OrganizeJob(
            id="job",
            name="partial",
            source_directory_id="source",
            source_directory_path="/source",
            target_directory_id="target",
            target_directory_path="/target",
            status=JobStatus.REVIEW_REQUIRED,
            config={"_executed_match_ids": ["published"]},
        )
        session.add(job)
        session.add_all(
            [
                _source_with_match("published", MatchDecision.APPROVED),
                _source_with_match("next", MatchDecision.APPROVED),
                _source_with_match("pending", MatchDecision.REVIEW),
            ]
        )
        await session.commit()

        workflow = object.__new__(ExecutionWorkflow)
        matches = await workflow._load_executable_matches(session, job)

    await engine.dispose()
    assert [media_match.id for media_match in matches] == ["next"]
    assert job.executed_items == 1


def _source_with_match(match_id: str, decision: MatchDecision) -> SourceItem:
    source_item = SourceItem(
        id=f"source-{match_id}",
        job_id="job",
        cloud_file_id=f"cloud-{match_id}",
        source_path=f"/source/{match_id}.mkv",
        filename=f"{match_id}.mkv",
        extension=".mkv",
    )
    source_item.media_match = MediaMatch(
        id=match_id,
        media_type=MediaType.MOVIE,
        decision=decision,
        version_recommendation="SINGLE",
    )
    return source_item
