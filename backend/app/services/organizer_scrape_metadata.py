from datetime import date

from app.models import MediaEntity
from app.services.metadata import TMDB_IMAGE_BASE_URL, TmdbService

DEFAULT_METADATA_LANGUAGE = "zh-CN"
ORIGINAL_IMAGE_QUALITY = "ORIGINAL"
TMDB_STANDARD_IMAGE_SEGMENT = "/t/p/w500/"
TMDB_ORIGINAL_IMAGE_SEGMENT = "/t/p/original/"


async def refresh_entity_metadata(
    tmdb_service: TmdbService,
    entity: MediaEntity,
    language: str,
) -> bool:
    if entity.tmdb_id is None:
        return False
    payload = await tmdb_service.get_media_details(
        tmdb_id=entity.tmdb_id,
        media_type=entity.media_type,
        language=language or DEFAULT_METADATA_LANGUAGE,
    )
    if not payload:
        return False
    entity.title = _first_text(
        payload,
        "title",
        "name",
        default=entity.title,
    )
    entity.original_title = _first_text(
        payload,
        "original_title",
        "original_name",
        default=entity.original_title,
    )
    entity.year = _payload_year(payload) or entity.year
    entity.overview = _first_text(
        payload,
        "overview",
        default=entity.overview,
    )
    entity.poster_url = _image_url(payload.get("poster_path")) or entity.poster_url
    entity.backdrop_url = _image_url(payload.get("backdrop_path")) or entity.backdrop_url
    entity.metadata_snapshot = payload
    return True


def image_url_for_quality(url: str, image_quality: str) -> str:
    if image_quality != ORIGINAL_IMAGE_QUALITY:
        return url
    return url.replace(
        TMDB_STANDARD_IMAGE_SEGMENT,
        TMDB_ORIGINAL_IMAGE_SEGMENT,
    )


def _payload_year(payload: dict[str, object]) -> int | None:
    date_text = _first_text(payload, "release_date", "first_air_date")
    if not date_text:
        return None
    try:
        return date.fromisoformat(date_text).year
    except ValueError:
        return None


def _first_text(
    payload: dict[str, object],
    *keys: str,
    default: str = "",
) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return default


def _image_url(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    return f"{TMDB_IMAGE_BASE_URL}/{value.lstrip('/')}"
