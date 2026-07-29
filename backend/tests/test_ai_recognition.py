from dataclasses import replace
from typing import Self

import pytest

from app.config import Settings
from app.domain import MediaType
from app.services.media_parser import parse_media_filename
from app.services.metadata import AiRecognitionService, parse_ai_recognition


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
