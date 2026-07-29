import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.domain import MediaType
from app.services.media_parser import ParsedMediaName

INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MULTIPLE_SPACES = re.compile(r"\s+")
SUBTITLE_LANGUAGE = re.compile(
    r"(?i)(?:^|[._ -])(?P<language>zh(?:-cn|-tw)?|chs|cht|en|eng)$"
)


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
            f"{episode_title}.{extension}"
        )
        return str(
            PurePosixPath(
                "TV",
                title_with_year,
                f"Season {season_number:02d}",
                filename,
            )
        )

    edition = (
        f" - {sanitize_path_segment(naming_input.parsed.edition)}"
        if naming_input.parsed.edition
        else ""
    )
    filename = f"{title_with_year}{edition}.{extension}"
    return str(PurePosixPath("Movies", title_with_year, filename))


def build_subtitle_filename(media_target_path: str, source_filename: str) -> str:
    media_stem = PurePosixPath(media_target_path).stem
    source_path = PurePosixPath(source_filename)
    language_match = SUBTITLE_LANGUAGE.search(source_path.stem)
    language_suffix = (
        f".{language_match.group('language')}" if language_match else ""
    )
    return f"{media_stem}{language_suffix}{source_path.suffix.lower()}"
