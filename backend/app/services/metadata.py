import json
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.domain import MediaType
from app.services.media_parser import ParsedMediaName

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
HTTP_TIMEOUT_SECONDS = 15


@dataclass(frozen=True, slots=True)
class MetadataCandidate:
    tmdb_id: int
    title: str
    original_title: str
    year: int | None
    media_type: MediaType
    score: float
    poster_url: str | None
    backdrop_url: str | None
    overview: str


class AiRecognition(BaseModel):
    media_type: MediaType
    title: str
    year: int | None = None
    season: int | None = None
    episodes: list[int] = Field(default_factory=list)
    edition: str = ""
    confidence: float


class MetadataServiceError(RuntimeError):
    pass


class TmdbService:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.tmdb_api_token

    def configure(self, token: str) -> None:
        self._token = token

    async def search(self, parsed: ParsedMediaName) -> list[MetadataCandidate]:
        if not self._token:
            return demo_candidates_for(parsed)
        endpoint = "search/tv" if parsed.media_type == MediaType.TV else "search/movie"
        parameters: dict[str, str | int] = {
            "query": parsed.title,
            "language": "zh-CN",
            "include_adult": "false",
        }
        if parsed.year:
            parameters["first_air_date_year" if parsed.media_type == MediaType.TV else "year"] = (
                parsed.year
            )
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{TMDB_API_BASE_URL}/{endpoint}",
                    params=parameters,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise MetadataServiceError("TMDB search failed") from error
        payload = response.json()
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise MetadataServiceError("TMDB returned an invalid result list")
        return [
            candidate
            for item in results[:5]
            if isinstance(item, dict)
            and (candidate := _to_metadata_candidate(item, parsed)) is not None
        ]


class AiRecognitionService:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.ai_api_key
        self._base_url = settings.ai_base_url.rstrip("/")
        self._model = settings.ai_model

    def configure(self, *, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def recognize(
        self, *, filename: str, parent_path: str, parsed: ParsedMediaName
    ) -> ParsedMediaName:
        if not self._api_key or parsed.confidence >= 0.75:
            return parsed
        request_payload = {
            "model": self._model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "识别影视文件名，只返回 JSON。字段为 media_type、title、year、"
                        "season、episodes、edition、confidence。"
                        "media_type 只能为 MOVIE/TV/UNKNOWN。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"filename": filename, "parent_path": parent_path},
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=request_payload,
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            recognition = AiRecognition.model_validate_json(content)
        except (httpx.HTTPError, KeyError, IndexError, ValidationError, TypeError) as error:
            raise MetadataServiceError("AI recognition failed") from error
        return ParsedMediaName(
            media_type=recognition.media_type,
            title=recognition.title,
            year=recognition.year,
            season_number=recognition.season,
            episode_numbers=tuple(recognition.episodes),
            edition=recognition.edition,
            confidence=max(parsed.confidence, recognition.confidence),
            reason_codes=(*parsed.reason_codes, "AI_RECOGNIZED"),
            is_ignored=parsed.is_ignored,
        )


def demo_candidates_for(parsed: ParsedMediaName) -> list[MetadataCandidate]:
    normalized_title = parsed.title.lower()
    if "interstellar" in normalized_title:
        return [_demo_candidate(157336, "星际穿越", "Interstellar", 2014, MediaType.MOVIE, 0.98)]
    if "inception" in normalized_title:
        return [_demo_candidate(27205, "盗梦空间", "Inception", 2010, MediaType.MOVIE, 0.97)]
    if "breaking bad" in normalized_title:
        return [_demo_candidate(1396, "绝命毒师", "Breaking Bad", 2008, MediaType.TV, 0.95)]
    if "三体" in normalized_title or "three body" in normalized_title:
        return [
            _demo_candidate(204541, "三体", "Three-Body", 2023, MediaType.TV, 0.61),
            _demo_candidate(108545, "三体", "3 Body Problem", 2024, MediaType.TV, 0.38),
            _demo_candidate(3, "三体：锋刃", "Three Body: Swordholder", 2023, MediaType.TV, 0.22),
        ]
    return []


def _demo_candidate(
    tmdb_id: int,
    title: str,
    original_title: str,
    year: int,
    media_type: MediaType,
    score: float,
) -> MetadataCandidate:
    return MetadataCandidate(
        tmdb_id=tmdb_id,
        title=title,
        original_title=original_title,
        year=year,
        media_type=media_type,
        score=score,
        poster_url=f"https://image.tmdb.org/t/p/w500/demo-{tmdb_id}.jpg",
        backdrop_url=None,
        overview="演示元数据。配置 TMDB Token 后将获取真实简介与图片。",
    )


def _to_metadata_candidate(
    item: dict[str, object], parsed: ParsedMediaName
) -> MetadataCandidate | None:
    tmdb_id = item.get("id")
    if not isinstance(tmdb_id, int):
        return None
    title_value = item.get("title") or item.get("name")
    if not isinstance(title_value, str):
        return None
    original_value = item.get("original_title") or item.get("original_name") or ""
    date_value = item.get("release_date") or item.get("first_air_date") or ""
    year = _parse_year(date_value)
    poster_path = item.get("poster_path")
    backdrop_path = item.get("backdrop_path")
    score = _score_candidate(
        query_title=parsed.title,
        candidate_title=title_value,
        query_year=parsed.year,
        candidate_year=year,
    )
    return MetadataCandidate(
        tmdb_id=tmdb_id,
        title=title_value,
        original_title=str(original_value),
        year=year,
        media_type=parsed.media_type,
        score=score,
        poster_url=_image_url(poster_path),
        backdrop_url=_image_url(backdrop_path),
        overview=str(item.get("overview") or ""),
    )


def _parse_year(value: object) -> int | None:
    if not isinstance(value, str) or len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def _score_candidate(
    *, query_title: str, candidate_title: str, query_year: int | None, candidate_year: int | None
) -> float:
    query_tokens = set(query_title.casefold().split())
    candidate_tokens = set(candidate_title.casefold().split())
    union = query_tokens | candidate_tokens
    title_score = len(query_tokens & candidate_tokens) / len(union) if union else 0
    year_score = 0.15 if query_year and query_year == candidate_year else 0
    return min(0.8 * title_score + year_score + 0.05, 0.99)


def _image_url(path_value: object) -> str | None:
    return f"{TMDB_IMAGE_BASE_URL}{path_value}" if isinstance(path_value, str) else None
