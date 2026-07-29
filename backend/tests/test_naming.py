from app.domain import MediaType
from app.services.media_parser import ParsedMediaName
from app.services.naming import (
    NamingInput,
    build_subtitle_filename,
    build_target_relative_path,
    sanitize_path_segment,
)


def test_builds_movie_path() -> None:
    parsed = ParsedMediaName(
        media_type=MediaType.MOVIE,
        title="Interstellar",
        year=2014,
        season_number=None,
        episode_numbers=(),
        edition="REMUX 2160p",
        confidence=0.98,
        reason_codes=(),
        is_ignored=False,
    )

    target_path = build_target_relative_path(
        NamingInput(title="星际穿越", year=2014, parsed=parsed, extension=".mkv")
    )

    assert target_path == "Movies/星际穿越 (2014)/星际穿越 (2014) - REMUX 2160p.mkv"


def test_builds_tv_multi_episode_path() -> None:
    parsed = ParsedMediaName(
        media_type=MediaType.TV,
        title="Example Show",
        year=2024,
        season_number=2,
        episode_numbers=(3, 4),
        edition="1080p",
        confidence=0.95,
        reason_codes=(),
        is_ignored=False,
    )

    target_path = build_target_relative_path(
        NamingInput(
            title="示例剧集",
            year=2024,
            parsed=parsed,
            extension="mkv",
            episode_title="新世界",
        )
    )

    assert target_path == (
        "TV/示例剧集 (2024)/Season 02/"
        "示例剧集 (2024) - S02E03E04 - 新世界.mkv"
    )


def test_sanitizes_unsafe_path_characters() -> None:
    assert sanitize_path_segment('Bad:<Name>?*"') == "Bad Name"


def test_builds_language_qualified_subtitle_filename() -> None:
    subtitle_filename = build_subtitle_filename(
        "TV/绝命毒师 (2008)/Season 01/绝命毒师 (2008) - S01E03.mkv",
        "Breaking.Bad.S01E03.zh-CN.srt",
    )

    assert subtitle_filename == "绝命毒师 (2008) - S01E03.zh-CN.srt"
