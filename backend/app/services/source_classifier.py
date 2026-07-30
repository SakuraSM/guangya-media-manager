from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath

from app.domain import SourceClassification
from app.providers.base import CloudNode
from app.services.media_parser import is_subtitle, is_supported_media

DEFAULT_SAMPLE_MAX_BYTES = 300 * 1024**2
SYSTEM_FILENAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini"})
SYSTEM_DIRECTORY_NAMES = frozenset({"__macosx", "@eadir"})
ARCHIVE_EXTENSIONS = frozenset({".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"})
TEMP_EXTENSIONS = frozenset({".tmp", ".part", ".download", ".crdownload"})
EXISTING_ASSET_EXTENSIONS = frozenset({".nfo", ".jpg", ".jpeg", ".png", ".webp"})
EXTRA_DIRECTORY_NAMES = frozenset(
    {
        "extras",
        "samples",
        "bonus",
        "bonus disc",
        "trailers",
        "featurettes",
        "interviews",
        "behind the scenes",
        "deleted scenes",
        "clips",
        "shorts",
        "花絮",
        "预告",
        "幕后",
    }
)
EXTRA_FILENAME_MARKERS = (
    "-trailer",
    ".trailer",
    "_trailer",
    "-featurette",
    "-interview",
    "-behindthescenes",
    "-deleted",
    "-extra",
)


@dataclass(frozen=True, slots=True)
class ClassificationPolicy:
    source_root: str
    target_root: str = ""
    sample_max_bytes: int = DEFAULT_SAMPLE_MAX_BYTES
    exclude_globs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    classification: SourceClassification
    reason_code: str
    relative_path: str
    is_reviewable: bool = False


def classify_source_node(node: CloudNode, policy: ClassificationPolicy) -> ClassificationResult:
    relative_path = _relative_path(node.path, policy.source_root)
    path = PurePosixPath(node.path)
    lowered_name = node.name.casefold()
    lowered_parts = {part.casefold() for part in path.parts}

    if _is_within_target(node.path, policy.target_root):
        return _ignored(relative_path, "TARGET_TREE")
    if "_整理中" in path.parts:
        return _ignored(relative_path, "STAGING_TREE")
    if lowered_name in SYSTEM_FILENAMES or lowered_name.startswith("._"):
        return _ignored(relative_path, "SYSTEM_FILE")
    if lowered_parts & SYSTEM_DIRECTORY_NAMES:
        return _ignored(relative_path, "SYSTEM_DIRECTORY")
    if any(fnmatch(relative_path, pattern) for pattern in policy.exclude_globs):
        return _ignored(relative_path, "CUSTOM_GLOB")
    if node.is_directory:
        return ClassificationResult(SourceClassification.UNKNOWN, "DIRECTORY", relative_path)

    extension = path.suffix.casefold()
    if extension in ARCHIVE_EXTENSIONS:
        return _ignored(relative_path, "ARCHIVE")
    if extension in TEMP_EXTENSIONS:
        return _ignored(relative_path, "TEMPORARY_FILE")
    if extension in EXISTING_ASSET_EXTENSIONS:
        return ClassificationResult(
            SourceClassification.EXISTING_ASSET,
            "EXISTING_ASSET",
            relative_path,
        )
    if is_subtitle(node.name):
        return ClassificationResult(
            SourceClassification.SUBTITLE,
            "SUPPORTED_SUBTITLE",
            relative_path,
        )
    if not is_supported_media(node.name):
        return _ignored(relative_path, "UNSUPPORTED_FORMAT")
    if "sample" in lowered_name and node.size_bytes < policy.sample_max_bytes:
        return _ignored(relative_path, "SMALL_SAMPLE")
    if lowered_parts & EXTRA_DIRECTORY_NAMES or any(
        marker in lowered_name for marker in EXTRA_FILENAME_MARKERS
    ):
        return ClassificationResult(
            SourceClassification.EXTRA,
            "EXTRA_CONTENT",
            relative_path,
            is_reviewable=True,
        )
    return ClassificationResult(
        SourceClassification.MEDIA,
        "SUPPORTED_MEDIA",
        relative_path,
    )


def _ignored(relative_path: str, reason_code: str) -> ClassificationResult:
    return ClassificationResult(SourceClassification.IGNORED, reason_code, relative_path)


def _relative_path(path: str, source_root: str) -> str:
    source = PurePosixPath(path)
    if not source_root:
        return str(source)
    try:
        return str(source.relative_to(PurePosixPath(source_root)))
    except ValueError:
        return str(source)


def _is_within_target(path: str, target_root: str) -> bool:
    if not target_root:
        return False
    source = PurePosixPath(path)
    target = PurePosixPath(target_root)
    return source == target or target in source.parents
