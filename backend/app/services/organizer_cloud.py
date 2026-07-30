import asyncio
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.models import MediaMatch, OrganizeJob
from app.providers.base import CloudNode, CloudProvider
from app.services.organizer_support import OrganizerError

PROVIDER_POLL_INTERVAL_SECONDS = 0.5
MAX_PROVIDER_POLLS = 600
STAGING_DIRECTORY_NAME = "_整理中"


@dataclass(frozen=True, slots=True)
class MediaDirectories:
    leaf: CloudNode
    media_root: CloudNode


@dataclass(frozen=True, slots=True)
class CommittedMove:
    source_path: str
    target_path: str
    task_id: str


@dataclass(frozen=True, slots=True)
class CommitResult:
    conflicts: list[str]
    duplicates: list[str]
    moves: list[CommittedMove]


class CloudLayout:
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider
        self._directory_cache: dict[str, CloudNode] = {}

    async def prepare_staging(self, job: OrganizeJob) -> CloudNode:
        target_root = CloudNode(
            id=job.target_directory_id,
            parent_id="",
            name=PurePosixPath(job.target_directory_path).name,
            path=job.target_directory_path,
            is_directory=True,
        )
        staging_root = await self._get_or_create_child(target_root, STAGING_DIRECTORY_NAME)
        return await self._get_or_create_child(staging_root, job.id)

    async def prepare_media_directories(
        self, staging: CloudNode, media_matches: list[MediaMatch]
    ) -> dict[str, MediaDirectories]:
        result: dict[str, MediaDirectories] = {}
        for media_match in media_matches:
            path_parts = PurePosixPath(media_match.target_path).parts
            if len(path_parts) < 3:
                raise OrganizerError("Target media path is incomplete")
            nodes: list[CloudNode] = []
            parent = staging
            for path_part in path_parts[:-1]:
                parent = await self._get_or_create_child(parent, path_part)
                nodes.append(parent)
            result[media_match.id] = MediaDirectories(
                leaf=nodes[-1],
                media_root=nodes[1],
            )
        return result

    async def commit_staging(
        self, staging: CloudNode, target_id: str, target_path: str
    ) -> CommitResult:
        conflicts: list[str] = []
        duplicates: list[str] = []
        moves: list[CommittedMove] = []
        staged_categories = await self._provider.list_directory(staging.id, staging.path)
        target_entries = await self._provider.list_directory(target_id, target_path)
        target_by_name = {entry.name: entry for entry in target_entries}

        for category in [node for node in staged_categories if node.is_directory]:
            target_category = target_by_name.get(category.name)
            if target_category is None:
                await self._move_node(
                    category,
                    target_id,
                    f"{target_path.rstrip('/')}/{category.name}",
                    moves,
                )
                continue
            await self._merge_directory(
                category,
                target_category,
                conflicts,
                duplicates,
                moves,
            )
        return CommitResult(
            conflicts=conflicts,
            duplicates=duplicates,
            moves=moves,
        )

    async def _merge_directory(
        self,
        staged: CloudNode,
        target: CloudNode,
        conflicts: list[str],
        duplicates: list[str],
        moves: list[CommittedMove],
    ) -> None:
        staged_children = await self._provider.list_directory(staged.id, staged.path)
        target_children = await self._provider.list_directory(target.id, target.path)
        target_by_name = {node.name: node for node in target_children}
        for staged_child in staged_children:
            target_child = target_by_name.get(staged_child.name)
            target_child_path = f"{target.path.rstrip('/')}/{staged_child.name}"
            if target_child is None:
                await self._move_node(staged_child, target.id, target_child_path, moves)
                continue
            if staged_child.is_directory and target_child.is_directory:
                await self._merge_directory(
                    staged_child,
                    target_child,
                    conflicts,
                    duplicates,
                    moves,
                )
                continue
            if (
                not staged_child.is_directory
                and not target_child.is_directory
                and staged_child.fingerprint
                and staged_child.fingerprint == target_child.fingerprint
            ):
                duplicates.append(target_child_path)
                continue
            conflicts.append(target_child_path)

    async def _move_node(
        self,
        node: CloudNode,
        target_parent_id: str,
        target_path: str,
        moves: list[CommittedMove],
    ) -> None:
        task_id = await self._move_and_wait([node.id], target_parent_id)
        moves.append(
            CommittedMove(
                source_path=node.path,
                target_path=target_path,
                task_id=task_id,
            )
        )

    async def _get_or_create_child(self, parent: CloudNode, name: str) -> CloudNode:
        cache_key = f"{parent.id}/{name}"
        cached = self._directory_cache.get(cache_key)
        if cached is not None:
            return cached
        children = await self._provider.list_directory(parent.id, parent.path)
        existing = next((child for child in children if child.name == name), None)
        if existing is not None:
            if not existing.is_directory:
                raise OrganizerError(f"Path conflict: {existing.path}")
            self._directory_cache[cache_key] = existing
            return existing
        created = await self._provider.create_directory(name, parent.id)
        normalized = CloudNode(
            id=created.id,
            parent_id=parent.id,
            name=name,
            path=f"{parent.path.rstrip('/')}/{name}",
            is_directory=True,
        )
        self._directory_cache[cache_key] = normalized
        return normalized

    async def _move_and_wait(self, file_ids: list[str], target_parent_id: str) -> str:
        task = await self._provider.move_items(file_ids, target_parent_id)
        await wait_for_provider_task(self._provider, task.task_id)
        return task.task_id


async def wait_for_provider_task(provider: CloudProvider, task_id: str) -> None:
    if not task_id:
        raise OrganizerError("Cloud provider did not return a task id")
    for _ in range(MAX_PROVIDER_POLLS):
        if await provider.task_is_complete(task_id):
            return
        await asyncio.sleep(PROVIDER_POLL_INTERVAL_SECONDS)
    raise OrganizerError("Cloud provider task timed out")
