import asyncio
import ipaddress
import logging
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from io import BytesIO
from typing import Protocol

import httpx

from app.config import Settings, get_settings
from app.providers.base import CloudNode, LoginChallenge, LoginTokens, ProviderTask
from app.providers.request_guard import (
    CloudRequestGuard,
    RequestGuardPolicy,
    RequestKind,
)

DEFAULT_CLIENT_ID = "aMe-8VSlkrbQXpUR"
DEFAULT_PAGE_SIZE = 1000
MAX_LIST_PAGES = 1000
DOWNLOAD_TIMEOUT_SECONDS = 10
RATE_LIMIT_MARKERS = (
    "429",
    "rate limit",
    "too many request",
    "request too frequent",
    "请求频繁",
    "请求过于频繁",
    "操作频繁",
    "访问频繁",
    "稍后再试",
    "限流",
    "风控",
)
TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "connection aborted",
    "temporarily unavailable",
    "service unavailable",
    "系统繁忙",
    "服务繁忙",
)

logger = logging.getLogger(__name__)


class GuangyaProviderError(RuntimeError):
    pass


class GuangyaRateLimitError(GuangyaProviderError):
    pass


@dataclass(frozen=True, slots=True)
class GuangyaRetryPolicy:
    max_retries: int
    backoff_base_seconds: float
    backoff_max_seconds: float
    jitter_seconds: float


class GuangyaClientProtocol(Protocol):
    token: str
    refresh_token: str

    def auth_code(self, client_id: str) -> object: ...

    def auth_token(self, payload: object) -> object: ...

    def refresh_access_token(self, refresh_token: str) -> object: ...

    def user_assets(self) -> object: ...

    def fs_list(self, payload: object) -> object: ...

    def fs_copy(self, payload: object) -> object: ...

    def fs_task_status(self, payload: object) -> object: ...

    def fs_info_by_task_id(self, payload: object) -> object: ...

    def fs_mkdir(self, payload: object) -> object: ...

    def fs_move(self, payload: object) -> object: ...

    def fs_delete(self, payload: object) -> object: ...

    def fs_rename(self, payload: object) -> object: ...

    def download_url(self, file_id: str) -> object: ...

    def upload_file(self, file: BytesIO, *, file_name: str, parent_id: str) -> object: ...


class GuangyaProvider:
    def __init__(
        self,
        access_token: str = "",
        refresh_token: str = "",
        *,
        settings: Settings | None = None,
    ) -> None:
        active_settings = settings or get_settings()
        try:
            guangyapan_module = import_module("guangyapan")
        except ModuleNotFoundError as error:
            raise GuangyaProviderError("guangyapan package is not installed") from error
        client_class = getattr(guangyapan_module, "GuangyaPanClient", None)
        if client_class is None:
            raise GuangyaProviderError("guangyapan client class is unavailable")
        self._client: GuangyaClientProtocol = client_class(
            access_token, refresh_token=refresh_token
        )
        self._retry_policy = GuangyaRetryPolicy(
            max_retries=active_settings.guangya_api_max_retries,
            backoff_base_seconds=active_settings.guangya_api_backoff_base_seconds,
            backoff_max_seconds=active_settings.guangya_api_backoff_max_seconds,
            jitter_seconds=active_settings.guangya_api_jitter_seconds,
        )
        self._request_guard = CloudRequestGuard(
            redis_url=active_settings.redis_url,
            policy=RequestGuardPolicy(
                read_interval_seconds=active_settings.guangya_api_read_interval_seconds,
                write_interval_seconds=active_settings.guangya_api_write_interval_seconds,
                poll_interval_seconds=active_settings.guangya_api_poll_interval_seconds,
                jitter_seconds=active_settings.guangya_api_jitter_seconds,
            ),
        )

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        self._client.token = access_token
        self._client.refresh_token = refresh_token

    async def start_login(self) -> LoginChallenge:
        response = await self._call_client(
            "start login",
            self._client.auth_code,
            DEFAULT_CLIENT_ID,
            kind=RequestKind.AUTH,
        )
        response_map = _require_mapping(response)
        return LoginChallenge(
            device_code=_require_string(response_map, "device_code"),
            verification_uri=_require_string(response_map, "verification_uri_complete"),
            expires_in_seconds=_as_int(response_map.get("expires_in"), 600),
            poll_interval_seconds=_as_int(response_map.get("interval"), 2),
        )

    async def poll_login(self, device_code: str) -> LoginTokens | None:
        payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": DEFAULT_CLIENT_ID,
        }
        response = _require_mapping(
            await self._call_client(
                "poll login",
                self._client.auth_token,
                payload,
                kind=RequestKind.POLL,
            )
        )
        if response.get("error") == "authorization_pending":
            return None
        if "error" in response:
            raise GuangyaProviderError(str(response["error"]))
        return LoginTokens(
            access_token=_require_string(response, "access_token"),
            refresh_token=_require_string(response, "refresh_token"),
        )

    async def refresh_tokens(self, refresh_token: str) -> LoginTokens:
        try:
            raw_response = await self._call_client(
                "refresh token",
                self._client.refresh_access_token,
                refresh_token,
                kind=RequestKind.AUTH,
            )
        except Exception as error:
            raise GuangyaProviderError("Guangya token refresh failed") from error
        response = _require_mapping(raw_response)
        return LoginTokens(
            access_token=_require_string(response, "access_token"),
            refresh_token=_require_string(response, "refresh_token"),
        )

    async def get_storage_usage(self) -> tuple[int, int]:
        response = _require_mapping(
            await self._call_client(
                "read storage usage",
                self._client.user_assets,
                kind=RequestKind.READ,
            )
        )
        payload = _require_mapping(response.get("data", {}))
        capacity_bytes = _as_int(payload.get("totalSpaceSize"))
        used_bytes = _as_int(payload.get("usedSpaceSize"))
        if capacity_bytes <= 0:
            raise GuangyaProviderError("Guangya response is missing storage capacity")
        return capacity_bytes, used_bytes

    async def list_directory(self, parent_id: str, parent_path: str) -> list[CloudNode]:
        entries: list[Mapping[str, object]] = []
        for page_number in range(MAX_LIST_PAGES):
            response = _require_mapping(
                await self._call_client(
                    "list directory",
                    self._client.fs_list,
                    {
                        "parentId": parent_id,
                        "page": page_number,
                        "pageSize": DEFAULT_PAGE_SIZE,
                    },
                    kind=RequestKind.READ,
                )
            )
            page_entries = _extract_file_list(response)
            entries.extend(page_entries)
            if len(page_entries) < DEFAULT_PAGE_SIZE:
                break
        else:
            raise GuangyaProviderError("Guangya directory pagination exceeded safe limit")
        return [_to_cloud_node(entry, parent_path) for entry in entries]

    async def copy_items(self, file_ids: list[str], target_parent_id: str) -> ProviderTask:
        response = _require_mapping(
            await self._call_client(
                "copy files",
                self._client.fs_copy,
                {"fileIds": file_ids, "parentId": target_parent_id},
                kind=RequestKind.WRITE,
            )
        )
        return ProviderTask(task_id=_extract_task_id(response))

    async def task_is_complete(self, task_id: str) -> bool:
        response = _require_mapping(
            await self._call_client(
                "poll file task",
                self._client.fs_task_status,
                task_id,
                kind=RequestKind.POLL,
            )
        )
        payload = _require_mapping(response.get("data", {}))
        status_value = str(payload.get("status", "")).lower()
        if status_value in {"failed", "failure", "error", "-1", "4"}:
            raise GuangyaProviderError("Guangya background task failed")
        return status_value in {"success", "completed", "2", "3"}

    async def resolve_task_nodes(self, task_id: str, parent_path: str) -> list[CloudNode]:
        response = _require_mapping(
            await self._call_client(
                "resolve file task",
                self._client.fs_info_by_task_id,
                task_id,
                kind=RequestKind.READ,
            )
        )
        payload = response.get("data", {})
        if isinstance(payload, list):
            entries = [entry for entry in payload if isinstance(entry, Mapping)]
        elif isinstance(payload, Mapping):
            nested_entries = payload.get("list") or payload.get("files")
            if isinstance(nested_entries, list):
                entries = [entry for entry in nested_entries if isinstance(entry, Mapping)]
            else:
                entries = [payload]
        else:
            entries = []
        nodes = [_to_cloud_node(entry, parent_path) for entry in entries]
        return [node for node in nodes if node.id]

    async def create_directory(self, name: str, parent_id: str) -> CloudNode:
        response = _require_mapping(
            await self._call_client(
                "create directory",
                self._client.fs_mkdir,
                {"dirName": name, "parentId": parent_id, "failIfNameExist": True},
                kind=RequestKind.WRITE,
            )
        )
        payload = _require_mapping(response.get("data", {}))
        return _to_cloud_node(payload, "")

    async def move_items(self, file_ids: list[str], target_parent_id: str) -> ProviderTask:
        response = _require_mapping(
            await self._call_client(
                "move files",
                self._client.fs_move,
                {"fileIds": file_ids, "parentId": target_parent_id},
                kind=RequestKind.WRITE,
            )
        )
        return ProviderTask(task_id=_extract_task_id(response))

    async def trash_items(self, file_ids: list[str]) -> ProviderTask:
        response = _require_mapping(
            await self._call_client(
                "move files to recycle bin",
                self._client.fs_delete,
                {"fileIds": file_ids},
                kind=RequestKind.WRITE,
            )
        )
        return ProviderTask(task_id=_extract_task_id(response))

    async def rename_item(self, file_id: str, new_name: str) -> None:
        await self._call_client(
            "rename file",
            self._client.fs_rename,
            (file_id, new_name),
            kind=RequestKind.WRITE,
        )

    async def upload_bytes(self, filename: str, content: bytes, parent_id: str) -> CloudNode:
        response = _require_mapping(
            await self._call_client(
                "upload file",
                self._client.upload_file,
                BytesIO(content),
                kind=RequestKind.WRITE,
                file_name=filename,
                parent_id=parent_id,
            )
        )
        payload = _require_mapping(response.get("data", {}))
        return _to_cloud_node(payload, "")

    async def read_bytes(self, file_id: str, *, max_bytes: int) -> bytes:
        try:
            signed_url = await self._call_client(
                "create download URL",
                self._client.download_url,
                file_id,
                kind=RequestKind.READ,
            )
            if not isinstance(signed_url, str):
                raise GuangyaProviderError("Guangya download URL is unavailable")
            _validate_download_url(httpx.URL(signed_url))

            async def validate_request(request: httpx.Request) -> None:
                _validate_download_url(request.url)

            chunks: list[bytes] = []
            total_bytes = 0
            async with httpx.AsyncClient(
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
                follow_redirects=True,
                event_hooks={"request": [validate_request]},
            ) as client, client.stream("GET", signed_url) as response:
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise GuangyaProviderError("Cloud file exceeds the safe read limit")
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise GuangyaProviderError("Cloud file exceeds the safe read limit")
                    chunks.append(chunk)
            return b"".join(chunks)
        except GuangyaProviderError:
            raise
        except Exception as error:
            raise GuangyaProviderError("Guangya small file read failed") from error

    async def aclose(self) -> None:
        request_guard = getattr(self, "_request_guard", None)
        if request_guard is not None:
            await request_guard.aclose()

    async def _call_client(
        self,
        operation: str,
        function: Callable[..., object],
        *args: object,
        kind: RequestKind,
        **kwargs: object,
    ) -> object:
        policy = getattr(
            self,
            "_retry_policy",
            GuangyaRetryPolicy(
                max_retries=0,
                backoff_base_seconds=2,
                backoff_max_seconds=30,
                jitter_seconds=0,
            ),
        )
        request_guard = getattr(self, "_request_guard", None)
        for attempt in range(policy.max_retries + 1):
            if request_guard is not None:
                await request_guard.wait(kind)
            try:
                response = await asyncio.to_thread(function, *args, **kwargs)
                rate_limit_message = _rate_limit_message(response)
                if rate_limit_message is not None:
                    raise GuangyaRateLimitError(rate_limit_message)
                return response
            except Exception as error:
                rate_limited = _is_rate_limited_error(error)
                retryable = rate_limited or (
                    kind is not RequestKind.WRITE and _is_transient_error(error)
                )
                if not retryable or attempt >= policy.max_retries:
                    if rate_limited:
                        raise GuangyaProviderError(
                            f"Guangya {operation} is rate limited; retry later"
                        ) from error
                    raise GuangyaProviderError(f"Guangya {operation} request failed") from error
                delay = _retry_delay_seconds(error, attempt, policy)
                logger.warning(
                    "Guangya request throttled; backing off",
                    extra={
                        "operation": operation,
                        "attempt": attempt + 1,
                        "delay_seconds": round(delay, 2),
                        "rate_limited": rate_limited,
                    },
                )
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")


def _validate_download_url(url: httpx.URL) -> None:
    hostname = (url.host or "").casefold()
    if (
        url.scheme != "https"
        or not hostname
        or hostname == "localhost"
        or hostname.endswith(".local")
    ):
        raise GuangyaProviderError("Guangya download URL is not allowed")
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return
    if not address.is_global:
        raise GuangyaProviderError("Guangya download URL is not allowed")


def _rate_limit_message(response: object) -> str | None:
    if not isinstance(response, Mapping):
        return None
    status_value = response.get("status") or response.get("statusCode") or response.get("code")
    if str(status_value) == "429":
        return "Guangya API rate limit response"
    for key in ("message", "msg", "error", "error_description"):
        value = response.get(key)
        if isinstance(value, str) and _contains_marker(value, RATE_LIMIT_MARKERS):
            return "Guangya API rate limit response"
    payload = response.get("data")
    if isinstance(payload, Mapping):
        return _rate_limit_message(payload)
    return None


def _is_rate_limited_error(error: Exception) -> bool:
    if isinstance(error, GuangyaRateLimitError):
        return True
    response = getattr(error, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    return _contains_marker(str(error), RATE_LIMIT_MARKERS)


def _is_transient_error(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, OSError, httpx.TimeoutException, httpx.NetworkError)):
        return True
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and (status_code == 408 or status_code >= 500):
        return True
    return _contains_marker(str(error), TRANSIENT_MARKERS)


def _retry_delay_seconds(
    error: Exception,
    attempt: int,
    policy: GuangyaRetryPolicy,
) -> float:
    retry_after = _retry_after_seconds(error)
    exponential_delay = min(
        policy.backoff_max_seconds,
        policy.backoff_base_seconds * 2**attempt,
    )
    base_delay = max(exponential_delay, retry_after or 0.0)
    return float(base_delay + random.uniform(0, policy.jitter_seconds))


def _retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    raw_value = headers.get("retry-after") or headers.get("Retry-After")
    if isinstance(raw_value, bool) or not isinstance(raw_value, (str, int, float)):
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(value, 300.0))


def _contains_marker(value: str, markers: tuple[str, ...]) -> bool:
    normalized = value.casefold()
    return any(marker in normalized for marker in markers)


def _require_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise GuangyaProviderError("Unexpected Guangya response")
    return value


def _require_string(value: Mapping[str, object], key: str) -> str:
    field_value = value.get(key)
    if not isinstance(field_value, str) or not field_value:
        raise GuangyaProviderError(f"Guangya response is missing {key}")
    return field_value


def _extract_file_list(response: Mapping[str, object]) -> list[Mapping[str, object]]:
    payload = _require_mapping(response.get("data", {}))
    for key in ("list", "files", "fileList"):
        entries = payload.get(key)
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, Mapping)]
    return []


def _to_cloud_node(entry: Mapping[str, object], parent_path: str) -> CloudNode:
    node_id = str(entry.get("fileId") or entry.get("id") or "")
    name = str(entry.get("fileName") or entry.get("name") or "未命名")
    is_directory = bool(
        entry.get("isDir") or entry.get("fileType") == 0 or _as_int(entry.get("resType")) == 2
    )
    return CloudNode(
        id=node_id,
        parent_id=str(entry.get("parentId") or ""),
        name=name,
        path=f"{parent_path.rstrip('/')}/{name}",
        is_directory=is_directory,
        size_bytes=_as_int(entry.get("fileSize") or entry.get("size")),
        fingerprint=str(entry.get("gcid") or entry.get("md5") or "") or None,
    )


def _extract_task_id(response: Mapping[str, object]) -> str:
    payload = _require_mapping(response.get("data", {}))
    return str(payload.get("taskId") or payload.get("id") or "")


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default
