import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from xml.etree import ElementTree

from app.domain import MatchOrigin, MediaType

MAX_NFO_BYTES = 1024 * 1024
MAX_XML_NODES = 10_000
MAX_XML_DEPTH = 48
TMDB_TAG = re.compile(
    r"(?:\{tmdb-(?P<brace>\d+)\}|\[tmdbid(?:-|=)(?P<bracket>\d+)\])",
    re.IGNORECASE,
)
IMDB_TAG = re.compile(r"\{imdb-(?P<id>tt\d{7,10})\}", re.IGNORECASE)


class MetadataHintError(ValueError):
    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    provider: "ExternalIdProvider"
    provider_id: str


class ExternalIdProvider(StrEnum):
    TMDB = "TMDB"
    IMDB = "IMDB"


@dataclass(frozen=True, slots=True)
class MetadataHint:
    origin: MatchOrigin
    identity: ExternalIdentity | None = None
    title: str = ""
    original_title: str = ""
    year: int | None = None
    media_type: MediaType = MediaType.UNKNOWN
    season_number: int | None = None
    episode_number: int | None = None
    plot: str = ""
    source_path: str = ""
    error_code: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "origin": self.origin.value,
            "provider": self.identity.provider.value if self.identity else None,
            "provider_id": self.identity.provider_id if self.identity else None,
            "title": self.title,
            "original_title": self.original_title,
            "year": self.year,
            "media_type": self.media_type.value,
            "season_number": self.season_number,
            "episode_number": self.episode_number,
            "source_path": self.source_path,
            "error_code": self.error_code,
        }


def extract_path_hint(path: str, *, filename: str) -> MetadataHint | None:
    full_path = PurePosixPath(path)
    directory_parts = list(full_path.parent.parts)
    for part in reversed(directory_parts):
        identity = _identity_from_text(part)
        if identity is not None:
            return MetadataHint(
                origin=MatchOrigin.PATH_ID,
                identity=identity,
                source_path=str(full_path.parent),
            )
    identity = _identity_from_text(filename)
    if identity is None:
        return None
    return MetadataHint(
        origin=MatchOrigin.PATH_ID,
        identity=identity,
        source_path=str(full_path),
    )


def parse_nfo(content: bytes, *, source_path: str = "") -> MetadataHint:
    if len(content) > MAX_NFO_BYTES:
        raise MetadataHintError("NFO exceeds the safe size limit", reason_code="NFO_TOO_LARGE")
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise MetadataHintError(
            "NFO contains forbidden XML declarations",
            reason_code="NFO_UNSAFE_XML",
        )
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise MetadataHintError("NFO is not valid XML", reason_code="NFO_INVALID_XML") from error
    _validate_xml_tree(root)
    identity = _nfo_identity(root)
    root_name = _local_name(root.tag)
    media_type = (
        MediaType.TV
        if root_name in {"tvshow", "episodedetails"}
        else MediaType.MOVIE
        if root_name == "movie"
        else MediaType.UNKNOWN
    )
    return MetadataHint(
        origin=MatchOrigin.NFO,
        identity=identity,
        title=_text(root, "title"),
        original_title=_text(root, "originaltitle"),
        year=_integer(_text(root, "year")),
        media_type=media_type,
        season_number=_integer(_text(root, "season")),
        episode_number=_integer(_text(root, "episode")),
        plot=_text(root, "plot"),
        source_path=source_path,
    )


def choose_nfo_path(media_path: str, nfo_paths: set[str]) -> str | None:
    media = PurePosixPath(media_path)
    candidates = (
        str(media.with_suffix(".nfo")),
        str(media.parent / "movie.nfo"),
        str(media.parent / "tvshow.nfo"),
        str(media.parent.parent / "tvshow.nfo"),
    )
    return next((candidate for candidate in candidates if candidate in nfo_paths), None)


def _identity_from_text(value: str) -> ExternalIdentity | None:
    tmdb_match = TMDB_TAG.search(value)
    if tmdb_match:
        return ExternalIdentity(
            ExternalIdProvider.TMDB,
            tmdb_match.group("brace") or tmdb_match.group("bracket"),
        )
    imdb_match = IMDB_TAG.search(value)
    if imdb_match:
        return ExternalIdentity(ExternalIdProvider.IMDB, imdb_match.group("id").lower())
    return None


def _nfo_identity(root: ElementTree.Element) -> ExternalIdentity | None:
    for node in root.iter():
        if _local_name(node.tag) != "uniqueid" or not node.text:
            continue
        identity_type = (node.attrib.get("type") or "").casefold()
        value = node.text.strip()
        if identity_type == "tmdb" and value.isdigit():
            return ExternalIdentity(ExternalIdProvider.TMDB, value)
        if identity_type == "imdb" and re.fullmatch(r"tt\d{7,10}", value, re.IGNORECASE):
            return ExternalIdentity(ExternalIdProvider.IMDB, value.lower())
    tmdb_id = _text(root, "tmdbid")
    if tmdb_id.isdigit():
        return ExternalIdentity(ExternalIdProvider.TMDB, tmdb_id)
    imdb_id = _text(root, "imdbid")
    if re.fullmatch(r"tt\d{7,10}", imdb_id, re.IGNORECASE):
        return ExternalIdentity(ExternalIdProvider.IMDB, imdb_id.lower())
    return None


def _validate_xml_tree(root: ElementTree.Element) -> None:
    count = 0
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_XML_NODES or depth > MAX_XML_DEPTH:
            raise MetadataHintError("NFO XML is too complex", reason_code="NFO_XML_LIMIT")
        stack.extend((child, depth + 1) for child in node)


def _text(root: ElementTree.Element, name: str) -> str:
    for node in root.iter():
        if _local_name(node.tag) == name and node.text:
            return node.text.strip()
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _integer(value: str) -> int | None:
    return int(value) if value.isdigit() else None
