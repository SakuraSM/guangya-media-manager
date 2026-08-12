from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DirectorySnapshot, OrganizeJob, RuleSourceItem, utc_now
from app.providers.base import CloudNode, CloudProvider
from app.services.organizer_support import OrganizerError

MAX_SCAN_DEPTH = 24


@dataclass(frozen=True, slots=True)
class IncrementalScanResult:
    nodes: list[CloudNode]
    scanned_directories: int
    skipped_directories: int
    changed_items: int


class IncrementalDirectoryScanner:
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider

    async def scan(self, session: AsyncSession, job: OrganizeJob) -> IncrementalScanResult:
        if not job.rule_id:
            nodes = await self._scan_all(job.source_directory_id, job.source_directory_path)
            file_count = len([node for node in nodes if not node.is_directory])
            return IncrementalScanResult(nodes, 0, 0, file_count)

        snapshots = {
            item.cloud_directory_id: item
            for item in (
                await session.scalars(
                    select(DirectorySnapshot).where(DirectorySnapshot.rule_id == job.rule_id)
                )
            ).all()
        }
        known_items = {
            item.cloud_file_id: item
            for item in (
                await session.scalars(
                    select(RuleSourceItem).where(RuleSourceItem.rule_id == job.rule_id)
                )
            ).all()
        }
        seen_file_ids: set[str] = set()
        selected_nodes: list[CloudNode] = []
        pending = [(job.source_directory_id, job.source_directory_path, 0)]
        scanned = 0
        skipped = 0
        changed = 0
        now = utc_now()
        while pending:
            directory_id, directory_path, depth = pending.pop()
            if depth > MAX_SCAN_DEPTH:
                raise OrganizerError("Directory nesting exceeds safe scan depth")
            children = await self._provider.list_directory(directory_id, directory_path)
            scanned += 1
            pending.extend(
                (node.id, node.path, depth + 1) for node in children if node.is_directory
            )
            signature = directory_signature(children)
            snapshot = snapshots.get(directory_id)
            directory_changed = snapshot is None or snapshot.child_signature != signature
            if not directory_changed:
                skipped += 1
            if snapshot is None:
                snapshot = DirectorySnapshot(
                    rule_id=job.rule_id,
                    cloud_directory_id=directory_id,
                    directory_path=directory_path,
                    child_signature=signature,
                    child_count=len(children),
                )
                session.add(snapshot)
            else:
                snapshot.directory_path = directory_path
                snapshot.child_signature = signature
                snapshot.child_count = len(children)
                snapshot.last_seen_at = now

            changed_files: list[CloudNode] = []
            contextual_files: list[CloudNode] = []
            for node in children:
                if node.is_directory:
                    continue
                seen_file_ids.add(node.id)
                existing = known_items.get(node.id)
                item_changed = (
                    existing is None
                    or existing.source_path != node.path
                    or existing.fingerprint != node.fingerprint
                    or existing.size_bytes != node.size_bytes
                    or existing.state != "ACTIVE"
                )
                if item_changed:
                    changed_files.append(node)
                    changed += 1
                else:
                    contextual_files.append(node)
                if existing is None:
                    existing = RuleSourceItem(
                        rule_id=job.rule_id,
                        cloud_file_id=node.id,
                        source_path=node.path,
                    )
                    session.add(existing)
                    known_items[node.id] = existing
                existing.source_path = node.path
                existing.fingerprint = node.fingerprint
                existing.size_bytes = node.size_bytes
                existing.state = "ACTIVE"
                existing.last_seen_at = now
            if changed_files:
                selected_nodes.extend(changed_files)
                selected_nodes.extend(
                    node
                    for node in contextual_files
                    if node.name.casefold().endswith((".nfo", ".srt", ".ass", ".ssa", ".vtt"))
                )

        for cloud_file_id, item in known_items.items():
            if cloud_file_id not in seen_file_ids and item.state == "ACTIVE":
                item.state = "MISSING"
                item.last_seen_at = now
        await session.flush()
        return IncrementalScanResult(selected_nodes, scanned, skipped, changed)

    async def _scan_all(self, root_id: str, root_path: str) -> list[CloudNode]:
        discovered: list[CloudNode] = []
        pending = [(root_id, root_path, 0)]
        while pending:
            parent_id, parent_path, depth = pending.pop()
            if depth > MAX_SCAN_DEPTH:
                raise OrganizerError("Directory nesting exceeds safe scan depth")
            nodes = await self._provider.list_directory(parent_id, parent_path)
            discovered.extend(nodes)
            pending.extend((node.id, node.path, depth + 1) for node in nodes if node.is_directory)
        return discovered


def directory_signature(nodes: list[CloudNode]) -> str:
    rows = sorted(
        "|".join(
            (
                node.id,
                node.name,
                "D" if node.is_directory else "F",
                str(node.size_bytes),
                node.fingerprint or "",
            )
        )
        for node in nodes
    )
    return sha256("\n".join(rows).encode()).hexdigest()
