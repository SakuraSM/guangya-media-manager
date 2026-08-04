import httpx
import pytest

from app.providers.guangya import (
    GuangyaProvider,
    GuangyaProviderError,
    _to_cloud_node,
    _validate_download_url,
)


def test_res_type_two_is_mapped_as_directory() -> None:
    node = _to_cloud_node(
        {
            "fileId": "real-directory-id",
            "fileName": "真实目录",
            "parentId": "",
            "resType": 2,
            "dirType": 1,
        },
        "/光鸭云盘",
    )

    assert node.is_directory is True
    assert node.path == "/光鸭云盘/真实目录"


class RefreshFailureClient:
    def refresh_access_token(self, refresh_token: str) -> object:
        raise KeyError("access_token")


async def test_refresh_converts_client_failure_to_provider_error() -> None:
    provider = object.__new__(GuangyaProvider)
    provider._client = RefreshFailureClient()  # type: ignore[assignment]

    with pytest.raises(GuangyaProviderError, match="token refresh failed"):
        await provider.refresh_tokens("expired-refresh-token")


@pytest.mark.parametrize(
    "url",
    (
        "http://cdn.example.com/file.nfo",
        "https://localhost/file.nfo",
        "https://127.0.0.1/file.nfo",
        "https://169.254.169.254/latest/meta-data",
    ),
)
def test_small_file_download_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(GuangyaProviderError, match="not allowed"):
        _validate_download_url(httpx.URL(url))
