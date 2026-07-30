import json
from dataclasses import dataclass, replace
from typing import Self

import pytest

from app.config import Settings
from app.domain import MediaType
from app.services.media_parser import ParsedMediaName, parse_media_filename
from app.services.metadata import (
    AiRecognitionService,
    MetadataCandidate,
    MetadataResolutionRequest,
    MetadataResolver,
    TmdbService,
    parse_ai_recognition,
)


def test_parses_fenced_ai_json_and_nullable_optional_fields() -> None:
    recognition = parse_ai_recognition(
        """```json
        {
          "media_type": "tv",
          "title": "爱情公寓",
          "year": 2009,
          "season": 1,
          "episodes": [1],
          "edition": null,
          "confidence": 0.91
        }
        ```"""
    )

    assert recognition.media_type == MediaType.TV
    assert recognition.edition == ""
    assert recognition.episodes == [1]


async def test_ai_failure_retries_then_returns_rule_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeAsyncClient()
    monkeypatch.setattr(
        "app.services.metadata.httpx.AsyncClient",
        lambda **_: fake_client,
    )
    service = AiRecognitionService(
        Settings(
            ai_api_key="test-key",
            ai_base_url="https://example.invalid/v1",
            ai_model="test-model",
        )
    )
    parsed = parse_media_filename(
        "01.mp4",
        parent_path="/光鸭云盘/爱情公寓/第1季",
        source_root="/光鸭云盘",
    )
    parsed = replace(parsed, confidence=0.74)

    result = await service.recognize(
        filename="01.mp4",
        parent_path="爱情公寓/第1季",
        parsed=parsed,
    )

    assert fake_client.request_count == 3
    assert result.title == "爱情公寓"
    assert "AI_FALLBACK" in result.reason_codes
    assert "AI_INVALID_RESPONSE" in result.reason_codes


async def test_ai_invalid_http_json_returns_rule_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = InvalidJsonAsyncClient()
    monkeypatch.setattr(
        "app.services.metadata.httpx.AsyncClient",
        lambda **_: fake_client,
    )
    service = AiRecognitionService(
        Settings(
            ai_api_key="test-key",
            ai_base_url="https://example.invalid/v1",
            ai_model="test-model",
        )
    )
    parsed = parse_media_filename("unknown-title.mkv")

    result = await service.recognize(
        filename="unknown-title.mkv",
        parent_path="未整理",
        parsed=parsed,
    )

    assert fake_client.request_count == 3
    assert result.title == parsed.title
    assert "AI_FALLBACK" in result.reason_codes
    assert "AI_INVALID_RESPONSE" in result.reason_codes


async def test_metadata_resolver_uses_tmdb_before_ai() -> None:
    parsed = parse_media_filename("Inception.2010.mkv")
    candidate = metadata_candidate("盗梦空间")
    call_log = CallLog(events=[])
    resolver = MetadataResolver(
        tmdb_service=RecordingTmdbService(call_log, [[candidate]]),
        ai_service=RecordingAiService(call_log, parsed),
    )

    resolution = await resolver.resolve(
        MetadataResolutionRequest(
            filename="Inception.2010.mkv",
            parent_path="Movies",
            parsed=parsed,
        )
    )

    assert call_log.events == ["tmdb"]
    assert resolution.candidates == (candidate,)
    assert resolution.requires_manual_confirmation is False
    assert "TMDB_PRIMARY_MATCH" in resolution.parsed.reason_codes


async def test_metadata_resolver_requires_confirmation_after_ai_fallback() -> None:
    parsed = parse_media_filename("01.mp4", parent_path="第一季")
    recognized = replace(
        parsed,
        media_type=MediaType.TV,
        title="爱情公寓",
        reason_codes=(*parsed.reason_codes, "AI_RECOGNIZED"),
    )
    candidate = metadata_candidate("爱情公寓", media_type=MediaType.TV)
    call_log = CallLog(events=[])
    resolver = MetadataResolver(
        tmdb_service=RecordingTmdbService(call_log, [[], [candidate]]),
        ai_service=RecordingAiService(call_log, recognized),
    )

    resolution = await resolver.resolve(
        MetadataResolutionRequest(
            filename="01.mp4",
            parent_path="爱情公寓/第一季",
            parsed=parsed,
        )
    )

    assert call_log.events == ["tmdb", "ai", "tmdb"]
    assert resolution.candidates == (candidate,)
    assert resolution.requires_manual_confirmation is True
    assert "AI_MANUAL_CONFIRMATION_REQUIRED" in resolution.parsed.reason_codes


@dataclass
class CallLog:
    events: list[str]


class RecordingTmdbService(TmdbService):
    def __init__(
        self,
        call_log: CallLog,
        candidate_batches: list[list[MetadataCandidate]],
    ) -> None:
        super().__init__(Settings())
        self._call_log = call_log
        self._candidate_batches = candidate_batches

    async def search(self, parsed: ParsedMediaName) -> list[MetadataCandidate]:
        self._call_log.events.append("tmdb")
        return self._candidate_batches.pop(0)


class RecordingAiService(AiRecognitionService):
    def __init__(self, call_log: CallLog, result: ParsedMediaName) -> None:
        super().__init__(Settings())
        self._call_log = call_log
        self._result = result

    async def recognize(
        self,
        *,
        filename: str,
        parent_path: str,
        parsed: ParsedMediaName,
    ) -> ParsedMediaName:
        self._call_log.events.append("ai")
        return self._result


def metadata_candidate(
    title: str,
    *,
    media_type: MediaType = MediaType.MOVIE,
) -> MetadataCandidate:
    return MetadataCandidate(
        tmdb_id=1,
        title=title,
        original_title=title,
        year=2010,
        media_type=media_type,
        score=0.95,
        poster_url=None,
        backdrop_url=None,
        overview="",
    )


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": "not-json",
                    }
                }
            ]
        }


class FakeAsyncClient:
    def __init__(self) -> None:
        self.request_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        return None

    async def post(self, *_: object, **__: object) -> FakeResponse:
        self.request_count += 1
        return FakeResponse()


class InvalidJsonResponse(FakeResponse):
    def json(self) -> dict[str, object]:
        raise json.JSONDecodeError("invalid", "not-json", 0)


class InvalidJsonAsyncClient(FakeAsyncClient):
    async def post(self, *_: object, **__: object) -> FakeResponse:
        self.request_count += 1
        return InvalidJsonResponse()
