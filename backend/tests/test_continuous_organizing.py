from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain import (
    JobTriggerType,
    LibraryCategory,
    MatchDecision,
    MediaType,
    QualityProfile,
    RegionBucket,
    RuleScheduleType,
)
from app.models import Base, MediaMatch, OrganizeJob, OrganizeRule, SourceItem
from app.providers.base import CloudNode
from app.services.incremental_scan import IncrementalDirectoryScanner
from app.services.media_classification import apply_output_layout, classify_media
from app.services.organize_rules import OrganizeRuleError, next_run_at
from app.services.organizer_scan import _apply_version_recommendations
from app.services.quality import (
    build_quality_decision,
    version_group_key,
    version_selection_sort_key,
)


def test_classification_uses_tmdb_genre_and_origin() -> None:
    decision = classify_media(
        media_type=MediaType.TV,
        title="示例动画",
        metadata={
            "metadata": {
                "genre_ids": [16],
                "origin_country": ["JP"],
                "original_language": "ja",
            }
        },
    )
    assert decision.category == LibraryCategory.ANIME
    assert decision.region == RegionBucket.JP_KR
    assert apply_output_layout(
        "TV/示例动画/Season 01/E01.mkv",
        category=decision.category,
        region=decision.region,
        classified=True,
        include_region=True,
    ) == "动漫/日韩/示例动画/Season 01/E01.mkv"


def test_quality_profile_recommends_remux_over_web_release() -> None:
    remux = build_quality_decision(
        filename="Movie.2160p.UHD.BluRay.REMUX.DV.HEVC.Atmos.mkv",
        release_info={"quality_tags": ["2160p", "REMUX", "DV", "HEVC", "Atmos"]},
        size_bytes=60 * 1024**3,
        preference=QualityProfile.QUALITY,
    )
    web = build_quality_decision(
        filename="Movie.1080p.WEB-DL.H264.AAC.mkv",
        release_info={"quality_tags": ["1080p", "WEB-DL", "H264", "AAC"]},
        size_bytes=5 * 1024**3,
        preference=QualityProfile.QUALITY,
    )
    assert remux.score > web.score
    assert remux.profile["hdr"] == "DOLBY VISION"
    assert version_group_key(
        identity="TMDB:1",
        media_type=MediaType.MOVIE,
        season=None,
        episodes=[],
        edition="",
    ) == version_group_key(
        identity="TMDB:1",
        media_type=MediaType.MOVIE,
        season=None,
        episodes=[],
        edition="",
    )
    assert version_group_key(
        identity="TMDB:1",
        media_type=MediaType.MOVIE,
        season=None,
        episodes=[],
        edition="",
        part_number=1,
    ) != version_group_key(
        identity="TMDB:1",
        media_type=MediaType.MOVIE,
        season=None,
        episodes=[],
        edition="",
        part_number=2,
    )


def test_version_selection_tie_breaker_matches_profile_intent() -> None:
    larger_quality = version_selection_sort_key(
        score=100,
        size_bytes=20,
        stable_name="larger.mkv",
        preference=QualityProfile.QUALITY,
    )
    smaller_quality = version_selection_sort_key(
        score=100,
        size_bytes=10,
        stable_name="smaller.mkv",
        preference=QualityProfile.QUALITY,
    )
    larger_space_saving = version_selection_sort_key(
        score=100,
        size_bytes=20,
        stable_name="larger.mkv",
        preference=QualityProfile.SPACE_SAVING,
    )
    smaller_space_saving = version_selection_sort_key(
        score=100,
        size_bytes=10,
        stable_name="smaller.mkv",
        preference=QualityProfile.SPACE_SAVING,
    )

    assert larger_quality < smaller_quality
    assert smaller_space_saving < larger_space_saving


@pytest.mark.parametrize(
    ("keep_count", "expected_selected"),
    ((1, {"best"}), (0, {"best", "other"})),
)
async def test_version_groups_are_selected_automatically(
    keep_count: int,
    expected_selected: set[str],
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        job = OrganizeJob(
            id="job",
            name="自动选版",
            source_directory_id="source",
            source_directory_path="/source",
            target_directory_id="target",
            target_directory_path="/target",
            config={
                "quality_profile": QualityProfile.QUALITY.value,
                "version_keep_count": keep_count,
            },
        )
        session.add(job)
        session.add_all(
            [
                _version_source("best", score=120, size_bytes=20),
                _version_source("other", score=80, size_bytes=10),
            ]
        )
        await session.commit()

        await _apply_version_recommendations(session, job)
        await session.commit()
        matches = list((await session.scalars(select(MediaMatch))).all())

    await engine.dispose()
    selected = {
        media_match.id
        for media_match in matches
        if media_match.version_recommendation == "CONFIRMED"
    }
    assert selected == expected_selected
    assert all(media_match.version_recommendation != "PENDING" for media_match in matches)
    assert {
        media_match.id
        for media_match in matches
        if media_match.decision == MatchDecision.IGNORED
    } == ({"best", "other"} - expected_selected)
    assert all(
        media_match.quality_profile["selection_mode"] == "AUTO"
        for media_match in matches
    )


def _version_source(match_id: str, *, score: float, size_bytes: int) -> SourceItem:
    source_item = SourceItem(
        id=f"source-{match_id}",
        job_id="job",
        cloud_file_id=f"cloud-{match_id}",
        source_path=f"/source/{match_id}.mkv",
        relative_path=f"{match_id}.mkv",
        filename=f"{match_id}.mkv",
        extension=".mkv",
    )
    source_item.media_match = MediaMatch(
        id=match_id,
        decision=MatchDecision.AUTO_APPROVED,
        version_group_key="same-content",
        version_score=score,
        quality_profile={"size_bytes": size_bytes},
    )
    return source_item


def test_cron_schedule_uses_rule_timezone() -> None:
    rule = OrganizeRule(
        name="daily",
        source_directory_id="source",
        source_directory_path="/source",
        target_directory_id="target",
        target_directory_path="/target",
        schedule_type=RuleScheduleType.CRON,
        cron_expression="0 3 * * *",
        timezone="Asia/Shanghai",
    )
    result = next_run_at(rule, datetime(2026, 8, 12, 18, 0, tzinfo=UTC))
    assert result == datetime(2026, 8, 12, 19, 0, tzinfo=UTC)


def test_disabled_rule_has_no_next_run() -> None:
    rule = OrganizeRule(
        name="disabled",
        enabled=False,
        source_directory_id="source",
        source_directory_path="/source",
        target_directory_id="target",
        target_directory_path="/target",
        schedule_type=RuleScheduleType.INTERVAL,
        interval_minutes=30,
    )
    assert next_run_at(rule, datetime.now(UTC)) is None


@pytest.mark.parametrize(
    "expression",
    (
        "x x x x x",
        "60 * * * *",
        "0 24 * * *",
        "0 3 0 * *",
        "0 3 * 13 *",
        "0 3 * * 7",
        "*/0 * * * *",
        "0 3 20-10 * *",
    ),
)
def test_invalid_cron_expression_is_rejected(expression: str) -> None:
    rule = OrganizeRule(
        name="invalid-cron",
        source_directory_id="source",
        source_directory_path="/source",
        target_directory_id="target",
        target_directory_path="/target",
        schedule_type=RuleScheduleType.CRON,
        cron_expression=expression,
        timezone="Asia/Shanghai",
    )
    with pytest.raises(OrganizeRuleError):
        next_run_at(rule, datetime.now(UTC))


@pytest.mark.asyncio
async def test_incremental_scan_only_returns_changed_files() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = MutableProvider()
    async with session_factory() as session:
        rule = OrganizeRule(
            name="incremental",
            source_directory_id="root",
            source_directory_path="/source",
            target_directory_id="target",
            target_directory_path="/target",
        )
        session.add(rule)
        await session.flush()
        first_job = _rule_job(rule.id)
        session.add(first_job)
        await session.flush()
        first = await IncrementalDirectoryScanner(provider).scan(session, first_job)
        await session.commit()
        assert [node.id for node in first.nodes] == ["file-1"]
        assert first.changed_items == 1

        second_job = _rule_job(rule.id)
        session.add(second_job)
        await session.flush()
        second = await IncrementalDirectoryScanner(provider).scan(session, second_job)
        assert second.nodes == []
        assert second.skipped_directories == 1

        provider.size_bytes = 2048
        third_job = _rule_job(rule.id)
        session.add(third_job)
        await session.flush()
        third = await IncrementalDirectoryScanner(provider).scan(session, third_job)
        assert [node.id for node in third.nodes] == ["file-1"]
        assert third.changed_items == 1
    await engine.dispose()


class MutableProvider:
    size_bytes = 1024

    async def list_directory(self, parent_id: str, parent_path: str) -> list[CloudNode]:
        return [
            CloudNode(
                id="file-1",
                parent_id=parent_id,
                name="Movie.1080p.mkv",
                path=f"{parent_path}/Movie.1080p.mkv",
                is_directory=False,
                size_bytes=self.size_bytes,
                fingerprint=f"fp-{self.size_bytes}",
            )
        ]


def _rule_job(rule_id: str) -> OrganizeJob:
    return OrganizeJob(
        name="run",
        source_directory_id="root",
        source_directory_path="/source",
        target_directory_id="target",
        target_directory_path="/target",
        rule_id=rule_id,
        trigger_type=JobTriggerType.SCHEDULED,
    )
