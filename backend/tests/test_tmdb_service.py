import json
from typing import Self

import httpx
import pytest

from app.config import Settings
from app.services.media_parser import parse_media_filename
from app.services.metadata import MetadataServiceError, TmdbService


async def test_production_without_token_does_not_return_demo_candidates() -> None:
    service = TmdbService(Settings(tmdb_api_token="", demo_mode=False))

    candidates = await service.search(
        parse_media_filename("Inception.2010.mkv")
    )

    assert candidates == []


async def test_uses_v3_api_key_as_query_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeAsyncClient()
    monkeypatch.setattr(
        "app.services.metadata.httpx.AsyncClient",
        lambda **_: fake_client,
    )
    service = TmdbService(Settings(tmdb_api_token="a" * 32, demo_mode=False))

    await service.search(parse_media_filename("Inception.2010.mkv"))

    assert fake_client.parameters["api_key"] == "a" * 32
    assert "Authorization" not in fake_client.headers


async def test_reports_tmdb_timeout_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.metadata.httpx.AsyncClient",
        lambda **_: TimeoutAsyncClient(),
    )
    service = TmdbService(Settings(tmdb_api_token="a" * 32, demo_mode=False))

    with pytest.raises(MetadataServiceError) as captured_error:
        await service.search(parse_media_filename("Inception.2010.mkv"))

    assert captured_error.value.reason_code == "TMDB_TIMEOUT"


async def test_reports_invalid_tmdb_json_without_crashing_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.metadata.httpx.AsyncClient",
        lambda **_: InvalidJsonAsyncClient(),
    )
    service = TmdbService(Settings(tmdb_api_token="a" * 32, demo_mode=False))

    with pytest.raises(MetadataServiceError) as captured_error:
        await service.search(parse_media_filename("Inception.2010.mkv"))

    assert captured_error.value.reason_code == "TMDB_INVALID_RESPONSE"


async def test_requests_localized_tmdb_details_with_related_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeAsyncClient()
    monkeypatch.setattr(
        "app.services.metadata.httpx.AsyncClient",
        lambda **_: fake_client,
    )
    service = TmdbService(Settings(tmdb_api_token="a" * 32, demo_mode=False))

    await service.get_media_details(
        tmdb_id=1396,
        media_type=parse_media_filename("Breaking.Bad.S01E01.mkv").media_type,
        language="zh-CN",
    )

    assert fake_client.url.endswith("/tv/1396")
    assert fake_client.parameters["language"] == "zh-CN"
    assert fake_client.parameters["append_to_response"] == (
        "credits,external_ids,release_dates,content_ratings"
    )


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"results": []}


class FakeAsyncClient:
    def __init__(self) -> None:
        self.url = ""
        self.parameters: dict[str, str | int] = {}
        self.headers: dict[str, str] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        return None

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int],
        headers: dict[str, str],
    ) -> FakeResponse:
        self.url = url
        self.parameters = params
        self.headers = headers
        return FakeResponse()


class TimeoutAsyncClient(FakeAsyncClient):
    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int],
        headers: dict[str, str],
    ) -> FakeResponse:
        raise httpx.ConnectTimeout("TMDB timeout")


class InvalidJsonResponse(FakeResponse):
    def json(self) -> dict[str, object]:
        raise json.JSONDecodeError("invalid", "not-json", 0)


class InvalidJsonAsyncClient(FakeAsyncClient):
    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int],
        headers: dict[str, str],
    ) -> FakeResponse:
        return InvalidJsonResponse()
