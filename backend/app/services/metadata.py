import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.domain import MediaType
from app.services.media_parser import ParsedMediaName

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
HTTP_TIMEOUT_SECONDS = 15
TMDB_SEASON_TIMEOUT_SECONDS = 8
TMDB_SEASON_MAX_ATTEMPTS = 2
TMDB_SEARCH_CONCURRENCY = 4
AI_RECOGNITION_CONCURRENCY = 2


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


@dataclass(frozen=True, slots=True)
class EpisodeMetadata:
    tmdb_id: int | None
    episode_number: int
    name: str
    overview: str
    air_date: date | None
    still_url: str | None
    snapshot: dict[str, object]


@dataclass(frozen=True, slots=True)
class SeasonMetadata:
    season_number: int
    name: str
    overview: str
    poster_url: str | None
    episodes: tuple[EpisodeMetadata, ...]
    snapshot: dict[str, object]


@dataclass(frozen=True, slots=True)
class MetadataResolutionRequest:
    filename: str
    parent_path: str
    parsed: ParsedMediaName


@dataclass(frozen=True, slots=True)
class MetadataResolution:
    parsed: ParsedMediaName
    candidates: tuple[MetadataCandidate, ...]
    requires_manual_confirmation: bool


class AiRecognition(BaseModel):
    media_type: MediaType
    title: str
    year: int | None = None
    season: int | None = None
    episodes: list[int] = Field(default_factory=list)
    edition: str | None = ""
    confidence: float


class MetadataServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        reason_code: str = "METADATA_FAILED",
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.http_status = http_status


AI_RESPONSE_FENCE = re.compile(
    r"^\s*```(?:json)?\s*(?P<payload>.*?)\s*```\s*$",
    re.IGNORECASE | re.DOTALL,
)
MAX_METADATA_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 0.25


def parse_ai_recognition(content: str) -> AiRecognition:
    fence_match = AI_RESPONSE_FENCE.match(content)
    normalized_content = fence_match.group("payload") if fence_match else content.strip()
    try:
        payload = json.loads(normalized_content)
    except json.JSONDecodeError as error:
        raise MetadataServiceError("AI returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise MetadataServiceError("AI returned a non-object response")
    media_type = payload.get("media_type")
    if isinstance(media_type, str):
        payload["media_type"] = media_type.upper()
    if payload.get("edition") is None:
        payload["edition"] = ""
    if payload.get("episodes") is None:
        payload["episodes"] = []
    try:
        return AiRecognition.model_validate(payload)
    except ValidationError as error:
        raise MetadataServiceError("AI returned an invalid recognition schema") from error


class TmdbService:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.tmdb_api_token.strip()
        self._is_demo_mode = settings.demo_mode

    def configure(self, token: str) -> None:
        self._token = token.strip()

    async def search(self, parsed: ParsedMediaName) -> list[MetadataCandidate]:
        if not self._token:
            return demo_candidates_for(parsed) if self._is_demo_mode else []
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
        payload = await self._get_json(endpoint, parameters)
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise MetadataServiceError("TMDB returned an invalid result list")
        return [
            candidate
            for item in results[:5]
            if isinstance(item, dict)
            and (candidate := _to_metadata_candidate(item, parsed)) is not None
        ]

    async def get_tv_season(
        self, series_id: int, season_number: int
    ) -> SeasonMetadata | None:
        if not self._token:
            return None
        payload = await self._get_json(
            f"tv/{series_id}/season/{season_number}",
            {"language": "zh-CN"},
            timeout_seconds=TMDB_SEASON_TIMEOUT_SECONDS,
            max_attempts=TMDB_SEASON_MAX_ATTEMPTS,
        )
        episodes_value = payload.get("episodes", [])
        if not isinstance(episodes_value, list):
            raise MetadataServiceError("TMDB returned invalid season episodes")
        episodes = tuple(
            episode
            for item in episodes_value
            if isinstance(item, dict)
            and (episode := _to_episode_metadata(item)) is not None
        )
        return SeasonMetadata(
            season_number=_int_value(payload.get("season_number"), season_number),
            name=_string_value(payload.get("name")),
            overview=_string_value(payload.get("overview")),
            poster_url=_image_url(payload.get("poster_path")),
            episodes=episodes,
            snapshot=_object_snapshot(payload),
        )

    async def get_media_details(
        self,
        *,
        tmdb_id: int,
        media_type: MediaType,
        language: str,
    ) -> dict[str, object]:
        if self._is_demo_mode or not self._token:
            return {}
        endpoint_type = "tv" if media_type == MediaType.TV else "movie"
        return await self._get_json(
            f"{endpoint_type}/{tmdb_id}",
            {
                "language": language,
                "append_to_response": (
                    "credits,external_ids,release_dates,content_ratings"
                ),
            },
        )

    async def _get_json(
        self,
        endpoint: str,
        parameters: dict[str, str | int],
        *,
        timeout_seconds: int = HTTP_TIMEOUT_SECONDS,
        max_attempts: int = MAX_METADATA_ATTEMPTS,
    ) -> dict[str, object]:
        request_parameters = dict(parameters)
        headers: dict[str, str] = {}
        if _is_tmdb_v3_api_key(self._token):
            request_parameters["api_key"] = self._token
        else:
            headers["Authorization"] = f"Bearer {self._token}"
        last_error: httpx.HTTPError | None = None
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.get(
                        f"{TMDB_API_BASE_URL}/{endpoint}",
                        params=request_parameters,
                        headers=headers,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise MetadataServiceError("TMDB returned a non-object response")
                    return {str(key): value for key, value in payload.items()}
                except httpx.HTTPStatusError as error:
                    if error.response.status_code in {401, 403}:
                        raise MetadataServiceError(
                            "TMDB authentication failed",
                            reason_code="TMDB_AUTH_FAILED",
                            http_status=error.response.status_code,
                        ) from error
                    last_error = error
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * 2**attempt)
                except json.JSONDecodeError as error:
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * 2**attempt)
                        continue
                    raise MetadataServiceError(
                        "TMDB returned invalid JSON",
                        reason_code="TMDB_INVALID_RESPONSE",
                    ) from error
                except httpx.HTTPError as error:
                    last_error = error
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * 2**attempt)
        raise _tmdb_request_error(last_error)


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
        if not self._api_key:
            return _append_reason_codes(parsed, "AI_FALLBACK", "AI_NOT_CONFIGURED")
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
        failure_reason = "AI_REQUEST_FAILED"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            for attempt in range(MAX_METADATA_ATTEMPTS):
                try:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=request_payload,
                    )
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    if not isinstance(content, str):
                        raise MetadataServiceError("AI returned non-text content")
                    recognition = parse_ai_recognition(content)
                    return _merge_ai_recognition(parsed, recognition)
                except (
                    httpx.HTTPError,
                    KeyError,
                    IndexError,
                    json.JSONDecodeError,
                    TypeError,
                    MetadataServiceError,
                ) as error:
                    failure_reason = _ai_failure_reason(error)
                    if attempt + 1 < MAX_METADATA_ATTEMPTS:
                        await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * 2**attempt)
        return _append_reason_codes(parsed, "AI_FALLBACK", failure_reason)


class MetadataResolver:
    def __init__(
        self,
        *,
        tmdb_service: TmdbService,
        ai_service: AiRecognitionService,
    ) -> None:
        self._tmdb_service = tmdb_service
        self._ai_service = ai_service
        self._tmdb_semaphore = asyncio.Semaphore(TMDB_SEARCH_CONCURRENCY)
        self._ai_semaphore = asyncio.Semaphore(AI_RECOGNITION_CONCURRENCY)

    async def resolve(
        self, request: MetadataResolutionRequest
    ) -> MetadataResolution:
        parsed, primary_candidates = await self._search_tmdb(
            request.parsed,
            success_reason="TMDB_PRIMARY_MATCH",
            empty_reason="TMDB_NO_RESULTS",
            failure_reason="TMDB_FAILED",
        )
        if primary_candidates:
            return MetadataResolution(
                parsed=parsed,
                candidates=primary_candidates,
                requires_manual_confirmation=False,
            )

        async with self._ai_semaphore:
            recognized = await self._ai_service.recognize(
                filename=request.filename,
                parent_path=request.parent_path,
                parsed=parsed,
            )
        if "AI_RECOGNIZED" not in recognized.reason_codes:
            return MetadataResolution(
                parsed=recognized,
                candidates=(),
                requires_manual_confirmation=False,
            )

        recognized = _append_reason_codes(
            recognized,
            "AI_MANUAL_CONFIRMATION_REQUIRED",
        )
        recognized, fallback_candidates = await self._search_tmdb(
            recognized,
            success_reason="TMDB_AI_QUERY_MATCHED",
            empty_reason="TMDB_AI_QUERY_NO_RESULTS",
            failure_reason="TMDB_AI_QUERY_FAILED",
        )
        return MetadataResolution(
            parsed=recognized,
            candidates=fallback_candidates,
            requires_manual_confirmation=True,
        )

    async def _search_tmdb(
        self,
        parsed: ParsedMediaName,
        *,
        success_reason: str,
        empty_reason: str,
        failure_reason: str,
    ) -> tuple[ParsedMediaName, tuple[MetadataCandidate, ...]]:
        async with self._tmdb_semaphore:
            try:
                candidates = tuple(await self._tmdb_service.search(parsed))
            except MetadataServiceError as error:
                resolved_reason = (
                    error.reason_code
                    if error.reason_code.startswith("TMDB_")
                    else failure_reason
                )
                return _append_reason_codes(parsed, resolved_reason), ()
        reason = success_reason if candidates else empty_reason
        return _append_reason_codes(parsed, reason), candidates


def _merge_ai_recognition(
    parsed: ParsedMediaName, recognition: AiRecognition
) -> ParsedMediaName:
    return replace(
        parsed,
        media_type=recognition.media_type,
        title=recognition.title,
        year=recognition.year,
        season_number=recognition.season,
        episode_numbers=tuple(recognition.episodes),
        edition=recognition.edition or "",
        confidence=max(parsed.confidence, recognition.confidence),
        reason_codes=(*parsed.reason_codes, "AI_RECOGNIZED"),
    )


def _append_reason_codes(
    parsed: ParsedMediaName, *reason_codes: str
) -> ParsedMediaName:
    return replace(
        parsed,
        reason_codes=tuple(
            dict.fromkeys((*parsed.reason_codes, *reason_codes))
        ),
    )


def _ai_failure_reason(error: BaseException) -> str:
    if isinstance(error, json.JSONDecodeError) or (
        isinstance(error, MetadataServiceError)
        and (
            "invalid" in str(error).casefold()
            or "non-object" in str(error).casefold()
            or "non-text" in str(error).casefold()
        )
    ):
        return "AI_INVALID_RESPONSE"
    return "AI_REQUEST_FAILED"


def _is_tmdb_v3_api_key(token: str) -> bool:
    return len(token) == 32 and all(
        character in "0123456789abcdefABCDEF" for character in token
    )


def _tmdb_request_error(
    error: httpx.HTTPError | None,
) -> MetadataServiceError:
    if isinstance(error, httpx.TimeoutException):
        return MetadataServiceError(
            "TMDB request timed out",
            reason_code="TMDB_TIMEOUT",
        )
    if isinstance(error, httpx.ConnectError):
        return MetadataServiceError(
            "TMDB connection failed",
            reason_code="TMDB_CONNECTION_FAILED",
        )
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        reason_code = (
            "TMDB_RATE_LIMITED"
            if status_code == 429
            else "TMDB_HTTP_FAILED"
        )
        return MetadataServiceError(
            "TMDB HTTP request failed",
            reason_code=reason_code,
            http_status=status_code,
        )
    return MetadataServiceError(
        "TMDB request failed",
        reason_code="TMDB_FAILED",
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


def _to_episode_metadata(item: dict[str, object]) -> EpisodeMetadata | None:
    episode_number = item.get("episode_number")
    if not isinstance(episode_number, int):
        return None
    tmdb_id = item.get("id")
    return EpisodeMetadata(
        tmdb_id=tmdb_id if isinstance(tmdb_id, int) else None,
        episode_number=episode_number,
        name=_string_value(item.get("name")),
        overview=_string_value(item.get("overview")),
        air_date=_parse_date(item.get("air_date")),
        still_url=_image_url(item.get("still_path")),
        snapshot=_object_snapshot(item),
    )


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int_value(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _object_snapshot(payload: Mapping[str, object]) -> dict[str, object]:
    return dict(payload)


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
