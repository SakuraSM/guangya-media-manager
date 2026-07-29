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
