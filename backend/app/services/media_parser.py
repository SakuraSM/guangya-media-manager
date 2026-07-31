import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.domain import MediaType

VIDEO_EXTENSIONS = frozenset({".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".wmv"})
SUBTITLE_EXTENSIONS = frozenset({".srt", ".ass", ".ssa", ".sub", ".vtt"})
IGNORED_MARKERS = ("sample", "trailer", "preview", "片花")
SPECIAL_DIRECTORY_MARKERS = frozenset(
    {"special", "specials", "番外", "番外篇", "特别篇", "特辑", "sp", "ova", "oad"}
)
RELEASE_MARKERS = re.compile(
    r"\b(?:8K|4K|2160p|1080p|720p|BluRay|WEB[- .]?DL|WEBRip|HDTV|REMUX|"
    r"x26[45]|H\.?26[45]|HEVC|AV1|HDR(?:10)?\+?|DV|DoVi|AAC|DTS(?:-HD)?|"
    r"Atmos|DDP?\d?(?:\.\d)?)\b",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<year>19\d{2}|20\d{2})[ ._-](?P<month>\d{1,2})[ ._-](?P<day>\d{1,2})(?!\d)"
)
EPISODE_PATTERN = re.compile(
    r"(?i)(?:S(?P<season>\d{1,2})[ ._-]*E(?P<episode>\d{1,3})"
    r"|(?P<season_alt>\d{1,2})x(?P<episode_alt>\d{1,3})"
    r"|EP?(?P<episode_only>\d{1,3})"
    r"|第(?P<episode_cn>\d{1,3})(?:集|话))"
)
MULTI_EPISODE_PATTERN = re.compile(
    r"(?i)(?:(?:E|EP|第)(?P<start>\d{1,3})(?:-|E|至)(?:E|EP)?"
    r"(?P<end>\d{1,3})(?:集|话)?|^(?:第)?(?P<bare_start>\d{1,3})"
    r"(?:-|至)(?P<bare_end>\d{1,3})(?:集|话)?$)"
)
BARE_EPISODE_PATTERN = re.compile(
    r"^(?:第)?(?P<start>\d{1,3})(?:[-至](?P<end>\d{1,3}))?(?:集|话)?$"
)
SEASON_DIRECTORY_PATTERN = re.compile(r"(?i)^(?:season[ ._-]*|s)(?P<number>\d{1,2})$")
CHINESE_SEASON_PATTERN = re.compile(r"^第?(?P<number>\d{1,2})季$")
CHINESE_ORDINAL_SEASON_PATTERN = re.compile(r"第(?P<number>[零〇一二两三四五六七八九十百]+)季")
SEASON_IN_DIRECTORY_PATTERN = re.compile(
    r"(?i)(?:^|[ ._-])(?:season[ ._-]*|s|第?)(?P<number>\d{1,2})季?(?:$|[ ._+-])"
)
COLLECTION_SUFFIX_PATTERN = re.compile(r"(?i)\s+(?:全?\d+\s*-\s*\d+季|全\d+季|合集).*$")
EPISODE_COUNT_PATTERN = re.compile(r"(?i)(?:全\s*)?\d+\s*集(?:全|完)?")
SUBTITLE_DESCRIPTION_PATTERN = re.compile(
    r"(?i)(?:内嵌|内封|外挂)?\s*(?:简中|繁中|中字|中文字幕|双语)?\s*字幕"
)
EMPTY_BRACKETS_PATTERN = re.compile(r"(?:\(\s*\)|（\s*）|\[\s*\]|【\s*】)")
PART_PATTERN = re.compile(r"(?i)(?:^|[ ._-])(?:cd|dvd|part|pt|disc|disk)[ ._-]?(\d+)$")
RELEASE_GROUP_PATTERN = re.compile(r"-(?P<group>[A-Za-z0-9][A-Za-z0-9._]{1,31})$")
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
    episode_date: str | None = None
    quality_tags: tuple[str, ...] = ()
    release_group: str = ""
    part_number: int | None = None
    context_group: str = ""


def is_supported_media(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


def is_subtitle(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUBTITLE_EXTENSIONS


def parse_media_filename(
    filename: str,
    *,
    parent_path: str = "",
    source_root: str = "",
    inferred_season_number: int | None = None,
) -> ParsedMediaName:
    stem = Path(filename).stem
    normalized = SPACE_PATTERN.sub(" ", SEPARATOR_PATTERN.sub(" ", stem)).strip()
    is_ignored = any(marker in normalized.lower() for marker in IGNORED_MARKERS)

    episode_match = EPISODE_PATTERN.search(normalized)
    season_number = _extract_number(episode_match, "season", "season_alt")
    first_episode = _extract_number(episode_match, "episode", "episode_alt")
    if episode_match and first_episode is None:
        episode_only = episode_match.group("episode_only") or episode_match.group("episode_cn")
        if episode_only:
            season_number = 1
            first_episode = int(episode_only)
    context = _parse_directory_context(parent_path, source_root)
    bare_episode_match = BARE_EPISODE_PATTERN.fullmatch(normalized)
    resolved_context_season = context.season_number
    if resolved_context_season is None:
        resolved_context_season = inferred_season_number
    if episode_match is None and bare_episode_match and resolved_context_season is not None:
        first_episode = int(bare_episode_match.group("start"))
        season_number = resolved_context_season
    episode_numbers = _extract_episode_numbers(normalized, first_episode)
    episode_date = _parse_episode_date(normalized)
    is_tv = episode_match is not None or first_episode is not None or episode_date is not None
    media_type = MediaType.TV if is_tv else MediaType.MOVIE

    year_match = YEAR_PATTERN.search(normalized)
    year = int(year_match.group(1)) if year_match else None
    cutoff_positions = [
        match.start()
        for match in (episode_match, year_match, RELEASE_MARKERS.search(normalized))
        if match is not None
    ]
    title_end = min(cutoff_positions) if cutoff_positions else len(normalized)
    title = _clean_title(normalized[:title_end])
    if context.title and (not title or bare_episode_match is not None):
        title = context.title
        year = year or context.year
    edition = _extract_edition(normalized)
    quality_tags = _extract_quality_tags(stem)
    release_group = _extract_release_group(stem)
    part_number = _extract_part_number(normalized)

    confidence = 0.45
    reason_codes: list[str] = ["TITLE_PARSED"] if title else ["TITLE_MISSING"]
    if year is not None:
        confidence += 0.18
        reason_codes.append("YEAR_PARSED")
    if episode_match is not None:
        confidence += 0.25
        reason_codes.append("EPISODE_PARSED")
    elif first_episode is not None and resolved_context_season is not None:
        confidence += 0.3
        reason_codes.extend(("DIRECTORY_CONTEXT", "EPISODE_PARSED"))
        if inferred_season_number is not None and context.season_number is None:
            reason_codes.extend(
                ("DIRECTORY_SEQUENCE_INFERRED", "PARENT_DIRECTORY_TITLE")
            )
    elif episode_date is not None:
        confidence += 0.2
        reason_codes.append("DATE_EPISODE_PARSED")
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
        episode_date=episode_date,
        quality_tags=quality_tags,
        release_group=release_group,
        part_number=part_number,
        context_group=context.title,
    )


def parse_bare_episode_numbers(filename: str) -> tuple[int, ...]:
    normalized = SPACE_PATTERN.sub(
        " ",
        SEPARATOR_PATTERN.sub(" ", Path(filename).stem),
    ).strip()
    match = BARE_EPISODE_PATTERN.fullmatch(normalized)
    if match is None:
        return ()
    start = int(match.group("start"))
    end_value = match.group("end")
    if end_value is None:
        return (start,)
    end = int(end_value)
    if end < start or end - start > 20:
        return ()
    return tuple(range(start, end + 1))


@dataclass(frozen=True, slots=True)
class DirectoryContext:
    title: str
    year: int | None
    season_number: int | None


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
    start = int(multi_match.group("start") or multi_match.group("bare_start"))
    end = int(multi_match.group("end") or multi_match.group("bare_end"))
    if end < start or end - start > 20:
        return (first_episode,)
    return tuple(range(start, end + 1))


def _parse_directory_context(parent_path: str, source_root: str) -> DirectoryContext:
    if not parent_path:
        return DirectoryContext("", None, None)
    parent = PurePosixPath(parent_path)
    root = PurePosixPath(source_root) if source_root else None
    parts = list(parent.parts)
    if root is not None and parent.is_relative_to(root):
        parts = [root.name, *parent.relative_to(root).parts]
    season_number: int | None = None
    title = ""
    year: int | None = None
    for part in reversed(parts):
        normalized_part = SPACE_PATTERN.sub(" ", SEPARATOR_PATTERN.sub(" ", part)).strip()
        if season_number is None:
            season_number = _season_number_from_directory(normalized_part)
            if season_number is not None:
                combined_title = _title_from_season_directory(normalized_part)
                if combined_title:
                    title = combined_title
                else:
                    continue
        if _is_generic_directory(normalized_part):
            continue
        if not title:
            title = _clean_directory_title(normalized_part)
            year_match = YEAR_PATTERN.search(normalized_part)
            if year is None and year_match:
                year = int(year_match.group(1))
    return DirectoryContext(title=title, year=year, season_number=season_number)


def _season_number_from_directory(value: str) -> int | None:
    if value.casefold() in SPECIAL_DIRECTORY_MARKERS:
        return 0
    match = (
        SEASON_DIRECTORY_PATTERN.fullmatch(value)
        or CHINESE_SEASON_PATTERN.fullmatch(value)
        or SEASON_IN_DIRECTORY_PATTERN.search(value)
    )
    if match:
        return int(match.group("number"))
    chinese_match = CHINESE_ORDINAL_SEASON_PATTERN.search(value)
    return _parse_chinese_number(chinese_match.group("number")) if chinese_match else None


def _title_from_season_directory(value: str) -> str:
    match = SEASON_IN_DIRECTORY_PATTERN.search(value)
    if match is not None:
        return _clean_directory_title(value[: match.start()])
    chinese_match = CHINESE_ORDINAL_SEASON_PATTERN.search(value)
    return (
        _clean_directory_title(value[: chinese_match.start()]) if chinese_match is not None else ""
    )


def _clean_directory_title(value: str) -> str:
    without_year = YEAR_PATTERN.sub("", value)
    without_empty_brackets = EMPTY_BRACKETS_PATTERN.sub("", without_year)
    without_episode_count = EPISODE_COUNT_PATTERN.sub("", without_empty_brackets)
    without_subtitles = SUBTITLE_DESCRIPTION_PATTERN.sub("", without_episode_count)
    without_collection = COLLECTION_SUFFIX_PATTERN.sub("", without_subtitles)
    without_quality = RELEASE_MARKERS.sub("", without_collection)
    title = re.split(r"(?i)\s*\+(?:电影|番外|特辑|movie).*$", without_quality)[0]
    return _clean_title(title)


def _is_generic_directory(value: str) -> bool:
    return value.casefold() in {
        "tv",
        "tv shows",
        "shows",
        "剧集",
        "电视剧",
        "movies",
        "movie",
        "电影",
        "未整理",
        "光鸭云盘",
    }


def _parse_chinese_number(value: str) -> int:
    digit_values = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value == "十":
        return 10
    if "百" in value:
        hundreds, remainder = value.split("百", 1)
        return digit_values.get(hundreds, 1) * 100 + _parse_chinese_number(remainder)
    if "十" in value:
        tens, ones = value.split("十", 1)
        return digit_values.get(tens, 1) * 10 + digit_values.get(ones, 0)
    return digit_values.get(value, 0)


def _parse_episode_date(normalized: str) -> str | None:
    match = DATE_PATTERN.search(normalized)
    if match is None:
        return None
    month = int(match.group("month"))
    day = int(match.group("day"))
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    return f"{match.group('year')}-{month:02d}-{day:02d}"


def _clean_title(value: str) -> str:
    title = value.strip(" -_[]()（）【】")
    return SPACE_PATTERN.sub(" ", title)


def _extract_edition(normalized: str) -> str:
    edition_markers = [
        marker
        for marker in ("REMUX", "BluRay", "WEB-DL", "WEBRip", "2160p", "1080p", "720p")
        if marker.lower() in normalized.lower()
    ]
    return " ".join(edition_markers[:2])


def _extract_quality_tags(normalized: str) -> tuple[str, ...]:
    tags: list[str] = []
    for match in RELEASE_MARKERS.finditer(normalized):
        tag = match.group(0)
        canonical = re.sub(r"(?i)WEB[ .-]?DL", "WEB-DL", tag)
        if canonical.casefold() not in {item.casefold() for item in tags}:
            tags.append(canonical)
    return tuple(tags)


def _extract_release_group(stem: str) -> str:
    match = RELEASE_GROUP_PATTERN.search(stem)
    return match.group("group") if match else ""


def _extract_part_number(normalized: str) -> int | None:
    match = PART_PATTERN.search(normalized)
    return int(match.group(1)) if match else None
