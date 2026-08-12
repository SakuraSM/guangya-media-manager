from dataclasses import dataclass
from pathlib import PurePosixPath

from app.domain import LibraryCategory, MediaType, RegionBucket

ANIMATION_GENRE_ID = 16
DOCUMENTARY_GENRE_ID = 99
VARIETY_GENRE_IDS = frozenset({10763, 10764, 10767})
CN_CODES = frozenset({"CN"})
HK_TW_CODES = frozenset({"HK", "TW", "MO"})
JP_KR_CODES = frozenset({"JP", "KR"})
EUROPE_US_CODES = frozenset(
    {
        "US", "GB", "CA", "AU", "NZ", "FR", "DE", "IT", "ES", "PT", "NL",
        "BE", "CH", "AT", "IE", "SE", "NO", "DK", "FI", "PL", "CZ",
    }
)


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    category: LibraryCategory
    region: RegionBucket
    reasons: tuple[dict[str, object], ...]


def classify_media(
    *,
    media_type: MediaType,
    title: str,
    metadata: dict[str, object] | None,
) -> ClassificationDecision:
    payload = metadata or {}
    nested = payload.get("metadata")
    if isinstance(nested, dict):
        payload = {**payload, **nested}
    genre_ids = _genre_ids(payload)
    countries = _country_codes(payload)
    language = str(payload.get("original_language") or "").casefold()
    normalized_title = title.casefold()

    if ANIMATION_GENRE_ID in genre_ids or any(
        token in normalized_title for token in ("anime", "动漫", "动画")
    ):
        category = LibraryCategory.ANIME
        category_reason = "动画类型或标题特征"
    elif DOCUMENTARY_GENRE_ID in genre_ids or "纪录片" in normalized_title:
        category = LibraryCategory.DOCUMENTARY
        category_reason = "纪录片类型"
    elif genre_ids & VARIETY_GENRE_IDS or any(
        token in normalized_title for token in ("综艺", "真人秀", "脱口秀")
    ):
        category = LibraryCategory.VARIETY
        category_reason = "综艺、真人秀或谈话节目类型"
    elif media_type == MediaType.TV:
        category = LibraryCategory.TV
        category_reason = "电视剧媒体类型"
    else:
        category = LibraryCategory.MOVIE
        category_reason = "电影媒体类型"

    region, region_reason = _region_for(countries, language)
    return ClassificationDecision(
        category=category,
        region=region,
        reasons=(
            {"code": "CATEGORY_CLASSIFIED", "message": category_reason, "origin": "TMDB_OR_RULE"},
            {"code": "REGION_CLASSIFIED", "message": region_reason, "origin": "TMDB_OR_RULE"},
        ),
    )


def apply_output_layout(
    target_path: str,
    *,
    category: LibraryCategory,
    region: RegionBucket,
    classified: bool,
    include_region: bool,
) -> str:
    if not classified or not target_path:
        return target_path
    path = PurePosixPath(target_path)
    parts = path.parts[1:] if path.parts and path.parts[0] in {"Movies", "TV"} else path.parts
    prefix = [_category_directory(category)]
    if include_region:
        prefix.append(_region_directory(region))
    return str(PurePosixPath(*prefix, *parts))


def _genre_ids(payload: dict[str, object]) -> set[int]:
    values = payload.get("genre_ids") or payload.get("genres") or []
    result: set[int] = set()
    if isinstance(values, list):
        for item in values:
            value = item.get("id") if isinstance(item, dict) else item
            if isinstance(value, int):
                result.add(value)
    return result


def _country_codes(payload: dict[str, object]) -> set[str]:
    values = payload.get("origin_country") or payload.get("production_countries") or []
    result: set[str] = set()
    if isinstance(values, list):
        for item in values:
            value = item.get("iso_3166_1") if isinstance(item, dict) else item
            if isinstance(value, str):
                result.add(value.upper())
    return result


def _region_for(countries: set[str], language: str) -> tuple[RegionBucket, str]:
    if countries & CN_CODES or (not countries and language == "zh"):
        return RegionBucket.CN, "原产地区或语言为中国大陆"
    if countries & HK_TW_CODES:
        return RegionBucket.HK_TW, "原产地区为港澳台"
    if countries & JP_KR_CODES or (not countries and language in {"ja", "ko"}):
        return RegionBucket.JP_KR, "原产地区或语言为日本、韩国"
    if countries & EUROPE_US_CODES or (
        not countries and language in {"en", "fr", "de", "es", "it"}
    ):
        return RegionBucket.EUROPE_US, "原产地区或语言为欧美"
    return RegionBucket.OTHER, "缺少明确地区信息或归入其他地区"


def _category_directory(category: LibraryCategory) -> str:
    return {
        LibraryCategory.MOVIE: "电影",
        LibraryCategory.TV: "电视剧",
        LibraryCategory.ANIME: "动漫",
        LibraryCategory.DOCUMENTARY: "纪录片",
        LibraryCategory.VARIETY: "综艺",
    }[category]


def _region_directory(region: RegionBucket) -> str:
    return {
        RegionBucket.CN: "中国大陆",
        RegionBucket.HK_TW: "港澳台",
        RegionBucket.JP_KR: "日韩",
        RegionBucket.EUROPE_US: "欧美",
        RegionBucket.OTHER: "其他",
    }[region]
