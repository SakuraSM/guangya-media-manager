import pytest

from app.providers.guangya import (
    GuangyaProvider,
    GuangyaProviderError,
    _to_cloud_node,
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
