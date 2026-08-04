import asyncio
from collections import defaultdict
from dataclasses import replace
from uuid import uuid4

from app.providers.base import CloudNode, LoginChallenge, LoginTokens, ProviderTask

DEMO_CAPACITY_BYTES = 28 * 1024**4
DEMO_USED_BYTES = int(18.72 * 1024**4)


class DemoGuangyaProvider:
    def __init__(self) -> None:
        self._poll_counts: defaultdict[str, int] = defaultdict(int)
        self._nodes = _build_demo_nodes()
        self._task_outputs: dict[str, list[str]] = {}
        self._file_contents: dict[str, bytes] = {}

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        return None

    async def start_login(self) -> LoginChallenge:
        device_code = str(uuid4())
        return LoginChallenge(
            device_code=device_code,
            verification_uri=f"https://www.guangyapan.com/device?code={device_code[:8]}",
            expires_in_seconds=600,
            poll_interval_seconds=2,
        )

    async def poll_login(self, device_code: str) -> LoginTokens | None:
        self._poll_counts[device_code] += 1
        if self._poll_counts[device_code] < 2:
            return None
        return LoginTokens(
            access_token=f"demo-access-{device_code}",
            refresh_token=f"demo-refresh-{device_code}",
        )

    async def refresh_tokens(self, refresh_token: str) -> LoginTokens:
        return LoginTokens(
            access_token=f"refreshed-{refresh_token}",
            refresh_token=refresh_token,
        )

    async def get_storage_usage(self) -> tuple[int, int]:
        return DEMO_CAPACITY_BYTES, DEMO_USED_BYTES

    async def list_directory(self, parent_id: str, parent_path: str) -> list[CloudNode]:
        await asyncio.sleep(0.05)
        return [node for node in self._nodes if node.parent_id == parent_id]

    async def copy_items(self, file_ids: list[str], target_parent_id: str) -> ProviderTask:
        await asyncio.sleep(0.05)
        task_id = f"copy-{uuid4()}"
        parent = self._find_node(target_parent_id)
        copied_ids: list[str] = []
        for file_id in file_ids:
            source = self._find_node(file_id)
            copied = replace(
                source,
                id=str(uuid4()),
                parent_id=target_parent_id,
                path=f"{parent.path.rstrip('/')}/{source.name}",
            )
            self._nodes.append(copied)
            copied_ids.append(copied.id)
        self._task_outputs[task_id] = copied_ids
        return ProviderTask(task_id=task_id)

    async def task_is_complete(self, task_id: str) -> bool:
        await asyncio.sleep(0.05)
        return True

    async def resolve_task_nodes(self, task_id: str, parent_path: str) -> list[CloudNode]:
        output_ids = self._task_outputs.get(task_id, [])
        return [self._find_node(node_id) for node_id in output_ids]

    async def create_directory(self, name: str, parent_id: str) -> CloudNode:
        parent_path = self._find_node(parent_id).path if parent_id else "/光鸭云盘"
        node = CloudNode(
            id=str(uuid4()),
            parent_id=parent_id,
            name=name,
            path=f"{parent_path.rstrip('/')}/{name}",
            is_directory=True,
        )
        self._nodes.append(node)
        return node

    async def move_items(self, file_ids: list[str], target_parent_id: str) -> ProviderTask:
        await asyncio.sleep(0.05)
        task_id = f"move-{uuid4()}"
        parent = self._find_node(target_parent_id)
        moved_ids: list[str] = []
        for file_id in file_ids:
            node = self._find_node(file_id)
            moved = replace(
                node,
                parent_id=target_parent_id,
                path=f"{parent.path.rstrip('/')}/{node.name}",
            )
            self._replace_node(moved)
            moved_ids.append(file_id)
        self._task_outputs[task_id] = moved_ids
        return ProviderTask(task_id=task_id)

    async def rename_item(self, file_id: str, new_name: str) -> None:
        await asyncio.sleep(0.02)
        node = self._find_node(file_id)
        parent_path = self._find_node(node.parent_id).path
        self._replace_node(
            replace(node, name=new_name, path=f"{parent_path.rstrip('/')}/{new_name}")
        )

    async def upload_bytes(self, filename: str, content: bytes, parent_id: str) -> CloudNode:
        await asyncio.sleep(0.03)
        parent = self._find_node(parent_id)
        node = CloudNode(
            id=str(uuid4()),
            parent_id=parent_id,
            name=filename,
            path=f"{parent.path.rstrip('/')}/{filename}",
            is_directory=False,
            size_bytes=len(content),
        )
        self._nodes.append(node)
        self._file_contents[node.id] = content
        return node

    async def read_bytes(self, file_id: str, *, max_bytes: int) -> bytes:
        content = self._file_contents.get(file_id)
        if content is None:
            raise RuntimeError("Demo cloud file content is unavailable")
        if len(content) > max_bytes:
            raise RuntimeError("Demo cloud file exceeds the safe read limit")
        return content

    def _find_node(self, node_id: str) -> CloudNode:
        node = next((item for item in self._nodes if item.id == node_id), None)
        if node is None:
            raise RuntimeError("Demo cloud node not found")
        return node

    def _replace_node(self, replacement: CloudNode) -> None:
        self._nodes = [replacement if node.id == replacement.id else node for node in self._nodes]


def _build_demo_nodes() -> list[CloudNode]:
    gibibyte = 1024**3
    return [
        CloudNode("source", "", "未整理", "/光鸭云盘/未整理", True),
        CloudNode("target", "", "电影与剧集", "/光鸭云盘/电影与剧集", True),
        CloudNode("movies", "source", "电影", "/光鸭云盘/未整理/电影", True),
        CloudNode("shows", "source", "剧集", "/光鸭云盘/未整理/剧集", True),
        CloudNode(
            "interstellar",
            "movies",
            "Interstellar.2014.2160p.BluRay.REMUX.HEVC.mkv",
            "/光鸭云盘/未整理/电影/Interstellar.2014.2160p.BluRay.REMUX.HEVC.mkv",
            False,
            67 * gibibyte,
            "demo-interstellar",
        ),
        CloudNode(
            "inception",
            "movies",
            "Inception.2010.1080p.BluRay.x264.DTS-WiKi.mkv",
            "/光鸭云盘/未整理/电影/Inception.2010.1080p.BluRay.x264.mkv",
            False,
            19 * gibibyte,
            "demo-inception",
        ),
        CloudNode(
            "three-body",
            "shows",
            "三体.Three.Body.2023.E03.2160p.WEB-DL.mkv",
            "/光鸭云盘/未整理/剧集/三体.Three.Body.2023.E03.2160p.WEB-DL.mkv",
            False,
            8 * gibibyte,
            "demo-three-body",
        ),
        CloudNode(
            "breaking-bad",
            "shows",
            "Breaking.Bad.S01E03.1080p.WEB-DL.mkv",
            "/光鸭云盘/未整理/剧集/Breaking.Bad.S01E03.1080p.WEB-DL.mkv",
            False,
            3 * gibibyte,
            "demo-breaking-bad",
        ),
        CloudNode(
            "breaking-bad-subtitle",
            "shows",
            "Breaking.Bad.S01E03.zh-CN.srt",
            "/光鸭云盘/未整理/剧集/Breaking.Bad.S01E03.zh-CN.srt",
            False,
            128 * 1024,
            "demo-breaking-bad-subtitle",
        ),
        CloudNode(
            "unknown",
            "movies",
            "Unknown.Title.2022.1080p.mkv",
            "/光鸭云盘/未整理/电影/Unknown.Title.2022.1080p.mkv",
            False,
            5 * gibibyte,
            "demo-unknown",
        ),
    ]
