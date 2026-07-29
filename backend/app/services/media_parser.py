import re
from dataclasses import dataclass
from pathlib import Path

from app.domain import MediaType

VIDEO_EXTENSIONS = frozenset({".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".wmv"})
SUBTITLE_EXTENSIONS = frozenset({".srt", ".ass", ".ssa", ".sub", ".vtt"})
IGNORED_MARKERS = ("sample", "trailer", "preview", "片花")
RELEASE_MARKERS = re.compile(
    r"\b(?:2160p|1080p|720p|BluRay|WEB[- .]?DL|WEBRip|HDTV|REMUX|"
    r"x26[45]|H\.?26[45]|HEVC|AV1|AAC|DTS|Atmos|DDP?\d?(?:\.\d)?)\b",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
EPISODE_PATTERN = re.compile(
    r"(?i)(?:S(?P<season>\d{1,2})[ ._-]*E(?P<episode>\d{1,3})"
    r"|(?P<season_alt>\d{1,2})x(?P<episode_alt>\d{1,3})"
    r"|E(?P<episode_only>\d{1,3}))"
)
MULTI_EPISODE_PATTERN = re.compile(
    r"(?i)E(?P<start>\d{1,3})(?:-|E)E?(?P<end>\d{1,3})"
)
SEPARATOR_PATTERN = re.compile(r"[._]+")
SPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ParsedMediaName:
    media_type: MediaType
    title: str
    year: int | None
    season_number: int | None
    episode_numbers: tuple[int, ...]
    edition: str
    confidence: float
    reason_codes: tuple[str, ...]
    is_ignored: bool


def is_supported_media(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


def is_subtitle(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUBTITLE_EXTENSIONS


def parse_media_filename(filename: str) -> ParsedMediaName:
    stem = Path(filename).stem
    normalized = SPACE_PATTERN.sub(" ", SEPARATOR_PATTERN.sub(" ", stem)).strip()
    is_ignored = any(marker in normalized.lower() for marker in IGNORED_MARKERS)

    episode_match = EPISODE_PATTERN.search(normalized)
    season_number = _extract_number(episode_match, "season", "season_alt")
    first_episode = _extract_number(episode_match, "episode", "episode_alt")
    if episode_match and first_episode is None and episode_match.group("episode_only"):
        season_number = 1
        first_episode = int(episode_match.group("episode_only"))
    episode_numbers = _extract_episode_numbers(normalized, first_episode)
    media_type = MediaType.TV if episode_match else MediaType.MOVIE

    year_match = YEAR_PATTERN.search(normalized)
    year = int(year_match.group(1)) if year_match else None
    cutoff_positions = [
        match.start()
        for match in (episode_match, year_match, RELEASE_MARKERS.search(normalized))
        if match is not None
    ]
    title_end = min(cutoff_positions) if cutoff_positions else len(normalized)
    title = _clean_title(normalized[:title_end])
    edition = _extract_edition(normalized)

    confidence = 0.45
    reason_codes: list[str] = ["TITLE_PARSED"] if title else ["TITLE_MISSING"]
    if year is not None:
        confidence += 0.18
        reason_codes.append("YEAR_PARSED")
    if episode_match is not None:
        confidence += 0.25
        reason_codes.append("EPISODE_PARSED")
    if RELEASE_MARKERS.search(normalized):
        confidence += 0.08
        reason_codes.append("RELEASE_TAGS_REMOVED")
    if is_ignored:
        reason_codes.append("IGNORED_SAMPLE")

    return ParsedMediaName(
        media_type=media_type,
        title=title,
        year=year,
        season_number=season_number,
        episode_numbers=episode_numbers,
        edition=edition,
        confidence=min(confidence, 0.98) if title else 0,
        reason_codes=tuple(reason_codes),
        is_ignored=is_ignored,
    )


def _extract_number(
    match: re.Match[str] | None, primary_group: str, alternate_group: str
) -> int | None:
    if match is None:
        return None
    value = match.group(primary_group) or match.group(alternate_group)
    return int(value) if value else None


def _extract_episode_numbers(normalized: str, first_episode: int | None) -> tuple[int, ...]:
    if first_episode is None:
        return ()
    multi_match = MULTI_EPISODE_PATTERN.search(normalized)
    if multi_match is None:
        return (first_episode,)
    start = int(multi_match.group("start"))
    end = int(multi_match.group("end"))
    if end < start or end - start > 20:
        return (first_episode,)
    return tuple(range(start, end + 1))


def _clean_title(value: str) -> str:
    title = value.strip(" -_[]()")
    return SPACE_PATTERN.sub(" ", title)


def _extract_edition(normalized: str) -> str:
    edition_markers = [
        marker
        for marker in ("REMUX", "BluRay", "WEB-DL", "WEBRip", "2160p", "1080p", "720p")
        if marker.lower() in normalized.lower()
    ]
    return " ".join(edition_markers[:2])
