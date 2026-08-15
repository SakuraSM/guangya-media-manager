from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.models import OrganizeJob
from app.providers.base import CloudNode
from app.schemas import JobConfig
from app.services.media_parser import parse_media_filename
from app.services.organizer_scan_progress import IncrementalMatchStore
from app.services.title_preprocessor import apply_title_extraction


def test_title_preprocessor_uses_named_group_and_preserves_episode_metadata() -> None:
    parsed = parse_media_filename("[广告]漫长的季节.S01E03.2160p.WEB-DL.mkv")

    result = apply_title_extraction(
        parsed,
        "[广告]漫长的季节.S01E03.2160p.WEB-DL.mkv",
        r"^\[[^\]]+\](?P<title>.+?)\.S\d+E\d+.*$",
    )

    assert result.title == "漫长的季节"
    assert result.context_group == "漫长的季节"
    assert result.season_number == 1
    assert result.episode_numbers == (3,)
    assert result.quality_tags == parsed.quality_tags
    assert "CUSTOM_TITLE_EXTRACTED" in result.reason_codes


def test_title_preprocessor_uses_first_group_then_full_match() -> None:
    parsed = parse_media_filename("prefix-繁花-01.mkv")

    first_group = apply_title_extraction(
        parsed,
        "prefix-繁花-01.mkv",
        r"^prefix-(.+?)-\d+$",
    )
    full_match = apply_title_extraction(parsed, "繁花.mkv", r"繁花")

    assert first_group.title == "繁花"
    assert full_match.title == "繁花"


def test_title_preprocessor_keeps_parsed_title_when_pattern_does_not_match() -> None:
    parsed = parse_media_filename("繁花.S01E01.mkv")

    assert apply_title_extraction(parsed, "繁花.S01E01.mkv", r"^不存在-(.+)$") == parsed


def test_job_config_rejects_invalid_title_extraction_regex() -> None:
    with pytest.raises(ValidationError, match="标题提取正则无效"):
        JobConfig(title_extraction_regex="[")


def test_scan_store_groups_files_by_preprocessed_title() -> None:
    job = OrganizeJob(
        id="job",
        source_directory_path="/媒体",
        config={
            "title_extraction_regex": r"^\[站点\](?P<title>.+?)\.S\d+E\d+.*$"
        },
    )
    store = IncrementalMatchStore(MagicMock(), job)

    record = store._build_pending_record(
        CloudNode(
            id="episode",
            parent_id="season",
            name="[站点]繁花.S01E02.1080p.mkv",
            path="/媒体/繁花/Season 01/[站点]繁花.S01E02.1080p.mkv",
            is_directory=False,
        ),
        {},
    )

    assert record.parsed.title == "繁花"
    assert record.group_key == "TV|繁花|"
    assert record.media_match.metadata_hint["title_extraction"] == {
        "pattern": r"^\[站点\](?P<title>.+?)\.S\d+E\d+.*$",
        "extracted_title": "繁花",
    }
