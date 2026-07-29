from app.domain import MediaType
from app.services.media_parser import parse_media_filename


def test_parses_movie_release_name() -> None:
    parsed = parse_media_filename(
        "Interstellar.2014.2160p.BluRay.REMUX.HEVC.DTS-HD.MA.7.1.mkv"
    )

    assert parsed.media_type == MediaType.MOVIE
    assert parsed.title == "Interstellar"
    assert parsed.year == 2014
    assert parsed.edition == "REMUX BluRay"
    assert parsed.confidence >= 0.7


def test_parses_tv_episode_name() -> None:
    parsed = parse_media_filename("Breaking.Bad.S01E03.1080p.WEB-DL.mkv")

    assert parsed.media_type == MediaType.TV
    assert parsed.title == "Breaking Bad"
    assert parsed.season_number == 1
    assert parsed.episode_numbers == (3,)


def test_parses_standalone_episode_marker_as_season_one() -> None:
    parsed = parse_media_filename("三体.Three.Body.2023.E03.2160p.WEB-DL.mkv")

    assert parsed.media_type == MediaType.TV
    assert parsed.season_number == 1
    assert parsed.episode_numbers == (3,)


def test_parses_multi_episode_range() -> None:
    parsed = parse_media_filename("Example.Show.S02E03-E05.1080p.mkv")

    assert parsed.season_number == 2
    assert parsed.episode_numbers == (3, 4, 5)


def test_marks_sample_as_ignored() -> None:
    parsed = parse_media_filename("Movie.2024.sample.1080p.mkv")

    assert parsed.is_ignored is True
    assert "IGNORED_SAMPLE" in parsed.reason_codes


def test_uses_chinese_season_directory_for_numeric_episode() -> None:
    parsed = parse_media_filename(
        "01.mp4",
        parent_path="/光鸭云盘/爱情公寓/第1季",
        source_root="/光鸭云盘",
    )

    assert parsed.media_type == MediaType.TV
    assert parsed.title == "爱情公寓"
    assert parsed.season_number == 1
    assert parsed.episode_numbers == (1,)
    assert "DIRECTORY_CONTEXT" in parsed.reason_codes


def test_parses_specials_directory_as_season_zero() -> None:
    parsed = parse_media_filename(
        "02.mkv",
        parent_path="/光鸭云盘/爱情公寓/番外",
        source_root="/光鸭云盘",
    )

    assert parsed.media_type == MediaType.TV
    assert parsed.season_number == 0
    assert parsed.episode_numbers == (2,)


def test_parses_chinese_multi_episode_range() -> None:
    parsed = parse_media_filename(
        "第03-05集.mp4",
        parent_path="/光鸭云盘/示例剧/Season 02",
        source_root="/光鸭云盘",
    )

    assert parsed.media_type == MediaType.TV
    assert parsed.season_number == 2
    assert parsed.episode_numbers == (3, 4, 5)


def test_parses_date_based_episode() -> None:
    parsed = parse_media_filename(
        "Daily.Show.2026-07-29.mkv",
        parent_path="/光鸭云盘/Daily Show",
        source_root="/光鸭云盘",
    )

    assert parsed.media_type == MediaType.TV
    assert parsed.episode_date == "2026-07-29"


def test_preserves_release_group_and_quality_tags() -> None:
    parsed = parse_media_filename(
        "Movie.2024.2160p.WEB-DL.HDR.HEVC.DDP5.1-GROUP.mkv"
    )

    assert parsed.quality_tags == ("2160p", "WEB-DL", "HDR", "HEVC", "DDP5.1")
    assert parsed.release_group == "GROUP"


def test_parses_show_title_and_season_from_combined_directory() -> None:
    parsed = parse_media_filename(
        "01.mp4",
        parent_path="/光鸭云盘/爱情公寓 第2季",
        source_root="/光鸭云盘",
    )

    assert parsed.title == "爱情公寓"
    assert parsed.season_number == 2
    assert parsed.episode_numbers == (1,)


def test_cleans_collection_suffix_from_show_directory() -> None:
    parsed = parse_media_filename(
        "01.mp4",
        parent_path="/光鸭云盘/爱情公寓 1-5季+电影+番外 4K/第3季",
        source_root="/光鸭云盘",
    )

    assert parsed.title == "爱情公寓"
    assert parsed.season_number == 3


def test_parses_real_world_chinese_ordinal_season_directory() -> None:
    source_root = "/光鸭云盘/爱情公寓 1-5季+电影+番外 4K"
    parsed = parse_media_filename(
        "01.mp4",
        parent_path=(
            f"{source_root}/"
            "第二季（2011）全20集 内嵌简中字幕 4K"
        ),
        source_root=source_root,
    )

    assert parsed.title == "爱情公寓"
    assert parsed.year is None
    assert parsed.season_number == 2
    assert parsed.episode_numbers == (1,)


def test_parses_real_world_specials_directory() -> None:
    source_root = "/光鸭云盘/爱情公寓 1-5季+电影+番外 4K"
    parsed = parse_media_filename(
        "01.mp4",
        parent_path=f"{source_root}/番外篇",
        source_root=source_root,
    )

    assert parsed.title == "爱情公寓"
    assert parsed.season_number == 0


def test_specials_subdirectory_removes_metadata_suffixes() -> None:
    source_root = "/光鸭云盘/爱情公寓 1-5季+电影+番外 4K"
    parsed = parse_media_filename(
        "01.mp4",
        parent_path=(
            f"{source_root}/番外篇/"
            "开心原力（2016）全6集 内嵌简中字幕 4K"
        ),
        source_root=source_root,
    )

    assert parsed.title == "开心原力"
    assert parsed.season_number == 0
    assert parsed.episode_numbers == (1,)
