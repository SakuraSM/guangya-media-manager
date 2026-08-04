from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CloudNode:
    id: str
    parent_id: str
    name: str
    path: str
    is_directory: bool
    size_bytes: int = 0
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class LoginChallenge:
    device_code: str
    verification_uri: str
    expires_in_seconds: int
    poll_interval_seconds: int


@dataclass(frozen=True, slots=True)
class LoginTokens:
    access_token: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class ProviderTask:
    task_id: str


class CloudProvider(Protocol):
    def set_tokens(self, access_token: str, refresh_token: str) -> None: ...

    async def start_login(self) -> LoginChallenge: ...

    async def poll_login(self, device_code: str) -> LoginTokens | None: ...

    async def refresh_tokens(self, refresh_token: str) -> LoginTokens: ...

    async def get_storage_usage(self) -> tuple[int, int]: ...

    async def list_directory(self, parent_id: str, parent_path: str) -> list[CloudNode]: ...

    async def copy_items(self, file_ids: list[str], target_parent_id: str) -> ProviderTask: ...

    async def task_is_complete(self, task_id: str) -> bool: ...

    async def resolve_task_nodes(self, task_id: str, parent_path: str) -> list[CloudNode]: ...

    async def create_directory(self, name: str, parent_id: str) -> CloudNode: ...

    async def move_items(self, file_ids: list[str], target_parent_id: str) -> ProviderTask: ...

    async def rename_item(self, file_id: str, new_name: str) -> None: ...

    async def upload_bytes(self, filename: str, content: bytes, parent_id: str) -> CloudNode: ...

    async def read_bytes(self, file_id: str, *, max_bytes: int) -> bytes: ...
