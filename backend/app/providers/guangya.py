import asyncio
from collections.abc import Mapping
from importlib import import_module
from io import BytesIO
from typing import Protocol

from app.providers.base import CloudNode, LoginChallenge, LoginTokens, ProviderTask

DEFAULT_CLIENT_ID = "aMe-8VSlkrbQXpUR"
DEFAULT_PAGE_SIZE = 1000
MAX_LIST_PAGES = 1000


class GuangyaProviderError(RuntimeError):
    pass


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

    def fs_rename(self, payload: object) -> object: ...

    def upload_file(
        self, file: BytesIO, *, file_name: str, parent_id: str
    ) -> object: ...


class GuangyaProvider:
    def __init__(self, access_token: str = "", refresh_token: str = "") -> None:
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

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        self._client.token = access_token
        self._client.refresh_token = refresh_token

    async def start_login(self) -> LoginChallenge:
        response = await asyncio.to_thread(self._client.auth_code, DEFAULT_CLIENT_ID)
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
            await asyncio.to_thread(self._client.auth_token, payload)
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
        response = _require_mapping(
            await asyncio.to_thread(self._client.refresh_access_token, refresh_token)
        )
        return LoginTokens(
            access_token=_require_string(response, "access_token"),
            refresh_token=_require_string(response, "refresh_token"),
        )

    async def get_storage_usage(self) -> tuple[int, int]:
        response = _require_mapping(
            await asyncio.to_thread(self._client.user_assets)
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
                await asyncio.to_thread(
                    self._client.fs_list,
                    {
                        "parentId": parent_id,
                        "page": page_number,
                        "pageSize": DEFAULT_PAGE_SIZE,
                    },
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
            await asyncio.to_thread(
                self._client.fs_copy,
                {"fileIds": file_ids, "parentId": target_parent_id},
            )
        )
        return ProviderTask(task_id=_extract_task_id(response))

    async def task_is_complete(self, task_id: str) -> bool:
        response = _require_mapping(
            await asyncio.to_thread(self._client.fs_task_status, task_id)
        )
        payload = _require_mapping(response.get("data", {}))
        status_value = str(payload.get("status", "")).lower()
        if status_value in {"failed", "failure", "error", "-1", "4"}:
            raise GuangyaProviderError("Guangya background task failed")
        return status_value in {"success", "completed", "2", "3"}

    async def resolve_task_nodes(
        self, task_id: str, parent_path: str
    ) -> list[CloudNode]:
        response = _require_mapping(
            await asyncio.to_thread(self._client.fs_info_by_task_id, task_id)
        )
        payload = response.get("data", {})
        if isinstance(payload, list):
            entries = [entry for entry in payload if isinstance(entry, Mapping)]
        elif isinstance(payload, Mapping):
            nested_entries = payload.get("list") or payload.get("files")
            if isinstance(nested_entries, list):
                entries = [
                    entry for entry in nested_entries if isinstance(entry, Mapping)
                ]
            else:
                entries = [payload]
        else:
            entries = []
        nodes = [_to_cloud_node(entry, parent_path) for entry in entries]
        return [node for node in nodes if node.id]

    async def create_directory(self, name: str, parent_id: str) -> CloudNode:
        response = _require_mapping(
            await asyncio.to_thread(
                self._client.fs_mkdir,
                {"dirName": name, "parentId": parent_id, "failIfNameExist": True},
            )
        )
        payload = _require_mapping(response.get("data", {}))
        return _to_cloud_node(payload, "")

    async def move_items(self, file_ids: list[str], target_parent_id: str) -> ProviderTask:
        response = _require_mapping(
            await asyncio.to_thread(
                self._client.fs_move,
                {"fileIds": file_ids, "parentId": target_parent_id},
            )
        )
        return ProviderTask(task_id=_extract_task_id(response))

    async def rename_item(self, file_id: str, new_name: str) -> None:
        await asyncio.to_thread(self._client.fs_rename, (file_id, new_name))

    async def upload_bytes(self, filename: str, content: bytes, parent_id: str) -> CloudNode:
        response = _require_mapping(
            await asyncio.to_thread(
                self._client.upload_file,
                BytesIO(content),
                file_name=filename,
                parent_id=parent_id,
            )
        )
        payload = _require_mapping(response.get("data", {}))
        return _to_cloud_node(payload, "")


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
        entry.get("isDir")
        or entry.get("fileType") == 0
        or _as_int(entry.get("resType")) == 2
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
