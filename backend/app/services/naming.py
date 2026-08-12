import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.domain import MediaType
from app.services.media_parser import ParsedMediaName

INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MULTIPLE_SPACES = re.compile(r"\s+")
SUBTITLE_LANGUAGE_TOKENS = frozenset(
    {"zh", "zh-cn", "zh-tw", "chs", "cht", "en", "eng", "ja", "jpn", "ko", "kor"}
)
SUBTITLE_FLAG_TOKENS = frozenset({"forced", "default", "sdh", "cc", "hi", "foreign"})
SUBTITLE_TOKEN_CANONICAL = {
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
}


@dataclass(frozen=True, slots=True)
class NamingInput:
    title: str
    year: int | None
    parsed: ParsedMediaName
    extension: str
    episode_title: str = ""


def sanitize_path_segment(value: str) -> str:
    sanitized = INVALID_PATH_CHARS.sub(" ", value)
    return MULTIPLE_SPACES.sub(" ", sanitized).strip(" .")


def build_target_relative_path(naming_input: NamingInput) -> str:
    title = sanitize_path_segment(naming_input.title)
    title_with_year = f"{title} ({naming_input.year})" if naming_input.year else title
    extension = naming_input.extension.lower().lstrip(".")

    if naming_input.parsed.media_type == MediaType.TV:
        season_number = naming_input.parsed.season_number or 1
        episode_numbers = naming_input.parsed.episode_numbers or (1,)
        episode_token = "".join(f"E{episode:02d}" for episode in episode_numbers)
        episode_title = (
            f" - {sanitize_path_segment(naming_input.episode_title)}"
            if naming_input.episode_title
            else ""
        )
        filename = (
            f"{title_with_year} - S{season_number:02d}{episode_token}"
            f"{episode_title}{_release_suffix(naming_input.parsed)}.{extension}"
        )
        return str(
            PurePosixPath(
                "TV",
                title_with_year,
                f"Season {season_number:02d}",
                filename,
            )
        )

    edition = _release_suffix(naming_input.parsed)
    if not edition and naming_input.parsed.edition:
        edition = f" - {sanitize_path_segment(naming_input.parsed.edition)}"
    filename = f"{title_with_year}{edition}.{extension}"
    return str(PurePosixPath("Movies", title_with_year, filename))


def build_subtitle_filename(media_target_path: str, source_filename: str) -> str:
    media_stem = PurePosixPath(media_target_path).stem
    source_path = PurePosixPath(source_filename)
    suffix_tokens = _subtitle_suffix_tokens(source_path.stem)
    suffix = "".join(f".{token}" for token in suffix_tokens)
    return f"{media_stem}{suffix}{source_path.suffix.lower()}"


def _release_suffix(parsed: ParsedMediaName) -> str:
    tags: list[str] = []
    release_tags = tuple(
        tag for tag in ((parsed.edition,) + parsed.quality_tags) if tag
    )
    for tag in release_tags:
        sanitized = sanitize_path_segment(tag)
        if sanitized and sanitized.casefold() not in {existing.casefold() for existing in tags}:
            tags.append(sanitized)
    if not tags and not parsed.release_group:
        return ""
    version_label = f" - [{' '.join(tags)}]" if tags else ""
    release_group = (
        f"-{sanitize_path_segment(parsed.release_group)}" if parsed.release_group else ""
    )
    return f"{version_label}{release_group}"


def _subtitle_suffix_tokens(stem: str) -> tuple[str, ...]:
    normalized_tokens = [token.casefold() for token in re.split(r"[._ ]+", stem) if token]
    result: list[str] = []
    for token in normalized_tokens:
        if token in SUBTITLE_LANGUAGE_TOKENS | SUBTITLE_FLAG_TOKENS and token not in result:
            result.append(SUBTITLE_TOKEN_CANONICAL.get(token, token))
    return tuple(result)
