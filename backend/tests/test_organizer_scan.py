import asyncio

from sqlalchemy import func, select

from app.config import Settings
from app.database import SessionFactory, engine
from app.domain import MatchDecision, MediaType
from app.models import Base, MediaMatch, OrganizeJob, SourceItem
from app.providers.demo import DemoGuangyaProvider
from app.services.media_parser import ParsedMediaName
from app.services.metadata import AiRecognitionService, MetadataCandidate, TmdbService
from app.services.organizer_scan import (
    ScanWorkflow,
    _merge_group_context,
    _summarize_decisions,
)


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


async def test_rule_parsed_records_are_visible_while_metadata_is_pending() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    tmdb_service = BlockingTmdbService()
    workflow = ScanWorkflow(
        session_factory=SessionFactory,
        provider=DemoGuangyaProvider(),
        tmdb_service=tmdb_service,
        ai_service=AiRecognitionService(Settings()),
    )
    async with SessionFactory() as session:
        job = OrganizeJob(
            name="增量识别可见性测试",
            source_directory_id="source",
            source_directory_path="/光鸭云盘/未整理",
            target_directory_id="target",
            target_directory_path="/光鸭云盘/电影与剧集",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    scan_task = asyncio.create_task(workflow.run(job_id))
    try:
        await asyncio.wait_for(tmdb_service.search_started.wait(), timeout=2)
        async with SessionFactory() as observer_session:
            visible_count = await observer_session.scalar(
                select(func.count(MediaMatch.id))
                .join(SourceItem)
                .where(SourceItem.job_id == job_id)
            )
            first_match = await observer_session.scalar(
                select(MediaMatch).join(SourceItem).where(SourceItem.job_id == job_id).limit(1)
            )
    finally:
        tmdb_service.release_search.set()
        await scan_task

    assert visible_count is not None and visible_count > 0
    assert first_match is not None
    assert "METADATA_PENDING" in first_match.reason_codes


class BlockingTmdbService(TmdbService):
    def __init__(self) -> None:
        super().__init__(Settings())
        self.search_started = asyncio.Event()
        self.release_search = asyncio.Event()

    async def search(self, parsed: ParsedMediaName) -> list[MetadataCandidate]:
        self.search_started.set()
        await self.release_search.wait()
        return []
