import re
from dataclasses import dataclass
from hashlib import sha256

from app.domain import MediaType, QualityProfile

RESOLUTION_SCORES = {"8K": 5, "4320P": 5, "4K": 4, "2160P": 4, "1080P": 3, "720P": 2, "480P": 1}
SOURCE_SCORES = {"REMUX": 5, "BLURAY": 4, "WEB-DL": 3, "WEBDL": 3, "WEBRIP": 2, "HDTV": 1}


@dataclass(frozen=True, slots=True)
class QualityDecision:
    profile: dict[str, object]
    score: float
    reason: str


def build_quality_decision(
    *, filename: str,
    release_info: dict[str, object],
    size_bytes: int,
    preference: QualityProfile,
) -> QualityDecision:
    tags_value = release_info.get("quality_tags", [])
    tags = [str(value) for value in tags_value] if isinstance(tags_value, list) else []
    haystack = " ".join((filename, *tags)).upper().replace(".", "-")
    resolution = _first_token(haystack, RESOLUTION_SCORES)
    source = _first_token(haystack, SOURCE_SCORES)
    hdr = _tag_value(
        haystack,
        (("DOLBY VISION", ("DOLBY VISION", "DOVI", " DV ")), ("HDR", ("HDR",))),
        "SDR",
    )
    codec = _tag_value(
        haystack,
        (("AV1", ("AV1",)), ("HEVC", ("HEVC", "H265", "X265")), ("H264", ("H264", "X264"))),
        "UNKNOWN",
    )
    audio = _tag_value(
        haystack,
        (("ATMOS", ("ATMOS",)), ("DTS-HD", ("DTS-HD",)), ("DTS", ("DTS",)), ("AAC", ("AAC",))),
        "UNKNOWN",
    )
    base_quality = RESOLUTION_SCORES.get(resolution, 0) * 20 + SOURCE_SCORES.get(source, 0) * 8
    base_quality += {"DOLBY VISION": 10, "HDR": 6, "SDR": 0}[hdr]
    compatibility = {"H264": 25, "HEVC": 18, "AV1": 10, "UNKNOWN": 5}[codec]
    compatibility += 5 if hdr == "SDR" else 0
    size_gib = size_bytes / (1024**3)
    if preference == QualityProfile.COMPATIBILITY:
        score = compatibility + base_quality * 0.45
        reason = "优先通用编码和播放兼容性"
    elif preference == QualityProfile.SPACE_SAVING:
        score = base_quality * 0.35 + max(0, 40 - size_gib)
        reason = "在基本质量相近时优先较小文件"
    else:
        score = base_quality + min(size_gib, 30) * 0.2
        reason = "优先分辨率、片源和 HDR 等质量特征"
    return QualityDecision(
        profile={
            "resolution": resolution,
            "source": source,
            "hdr": hdr,
            "codec": codec,
            "audio": audio,
            "release_group": release_info.get("release_group") or "",
            "size_bytes": size_bytes,
            "preference": preference.value,
        },
        score=round(score, 3),
        reason=reason,
    )


def version_group_key(
    *,
    identity: str,
    media_type: MediaType,
    season: int | None,
    episodes: list[int],
    edition: str,
    part_number: int | None = None,
) -> str:
    semantic_edition = _semantic_edition(edition)
    raw = "|".join(
        (
            identity,
            media_type.value,
            str(season or ""),
            ",".join(map(str, episodes)),
            semantic_edition,
            str(part_number or ""),
        )
    )
    return sha256(raw.encode()).hexdigest()[:32]


def version_selection_sort_key(
    *,
    score: float,
    size_bytes: int,
    stable_name: str,
    preference: QualityProfile,
) -> tuple[float, int, str]:
    """Build a deterministic best-first key for versions with equal profile scores."""

    size_key = size_bytes if preference == QualityProfile.SPACE_SAVING else -size_bytes
    return (-score, size_key, stable_name.casefold())


def _first_token(haystack: str, scores: dict[str, int]) -> str:
    return next((token for token in scores if token in haystack), "UNKNOWN")


def _tag_value(
    haystack: str,
    options: tuple[tuple[str, tuple[str, ...]], ...],
    default: str,
) -> str:
    return next(
        (label for label, markers in options if any(marker in haystack for marker in markers)),
        default,
    )


def _semantic_edition(edition: str) -> str:
    normalized = re.sub(r"[._-]+", " ", edition.casefold())
    quality_tokens = {
        "remux", "bluray", "web dl", "webrip", "2160p", "1080p", "720p",
    }
    for token in quality_tokens:
        normalized = normalized.replace(token, " ")
    return re.sub(r"\s+", " ", normalized).strip()
