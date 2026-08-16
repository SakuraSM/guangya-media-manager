import httpx
import pytest

from app.providers.guangya import (
    GuangyaProvider,
    GuangyaProviderError,
    GuangyaRetryPolicy,
    _to_cloud_node,
    _validate_download_url,
)
from app.providers.request_guard import RequestKind


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


class RecordingGuard:
    def __init__(self) -> None:
        self.kinds: list[RequestKind] = []

    async def wait(self, kind: RequestKind) -> None:
        self.kinds.append(kind)

    async def aclose(self) -> None:
        return None


class RateLimitedListClient:
    def __init__(self) -> None:
        self.call_count = 0

    def fs_list(self, payload: object) -> object:
        self.call_count += 1
        if self.call_count == 1:
            return {"code": 429, "message": "请求过于频繁"}
        return {"data": {"list": []}}


async def test_list_directory_retries_rate_limit_response() -> None:
    provider = object.__new__(GuangyaProvider)
    client = RateLimitedListClient()
    guard = RecordingGuard()
    provider._client = client  # type: ignore[assignment]
    provider._request_guard = guard
    provider._retry_policy = GuangyaRetryPolicy(1, 0, 0, 0)

    nodes = await provider.list_directory("root", "/光鸭云盘")

    assert nodes == []
    assert client.call_count == 2
    assert guard.kinds == [RequestKind.READ, RequestKind.READ]


class TimeoutCopyClient:
    def __init__(self) -> None:
        self.call_count = 0

    def fs_copy(self, payload: object) -> object:
        self.call_count += 1
        raise TimeoutError("request timed out")


async def test_ambiguous_write_timeout_is_not_retried() -> None:
    provider = object.__new__(GuangyaProvider)
    client = TimeoutCopyClient()
    provider._client = client  # type: ignore[assignment]
    provider._request_guard = RecordingGuard()
    provider._retry_policy = GuangyaRetryPolicy(3, 0, 0, 0)

    with pytest.raises(GuangyaProviderError, match="copy files request failed"):
        await provider.copy_items(["file-1"], "target")

    assert client.call_count == 1


class RecordingTrashClient:
    def __init__(self) -> None:
        self.payload: object = None

    def fs_delete(self, payload: object) -> object:
        self.payload = payload
        return {"data": {"taskId": "trash-task"}}


async def test_trash_uses_recoverable_delete_endpoint() -> None:
    provider = object.__new__(GuangyaProvider)
    client = RecordingTrashClient()
    provider._client = client  # type: ignore[assignment]
    provider._request_guard = RecordingGuard()
    provider._retry_policy = GuangyaRetryPolicy(0, 0, 0, 0)

    task = await provider.trash_items(["file-1", "file-2"])

    assert task.task_id == "trash-task"
    assert client.payload == {"fileIds": ["file-1", "file-2"]}


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
