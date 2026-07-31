from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.providers.base import CloudNode
from app.services.media_parser import parse_bare_episode_numbers

MIN_SEQUENCE_FILES = 3
MIN_NUMERIC_RATIO = 0.8
MAX_GAP_RATIO = 0.2
DEFAULT_INFERRED_SEASON = 1
GENERIC_DIRECTORY_NAMES = frozenset(
    {
        "download",
        "downloads",
        "temp",
        "tmp",
        "sample",
        "samples",
        "未整理",
        "下载",
        "临时",
    }
)


@dataclass(frozen=True, slots=True)
class DirectoryEpisodeInference:
    season_number: int
    episode_numbers_by_node_id: dict[str, tuple[int, ...]]


def infer_directory_episode_sequences(
    media_nodes: list[CloudNode],
) -> dict[str, DirectoryEpisodeInference]:
    nodes_by_parent: dict[str, list[CloudNode]] = defaultdict(list)
    for cloud_node in media_nodes:
        nodes_by_parent[str(PurePosixPath(cloud_node.path).parent)].append(cloud_node)

    return {
        parent_path: inference
        for parent_path, directory_nodes in nodes_by_parent.items()
        if (
            inference := _infer_directory_episode_sequence(
                parent_path,
                directory_nodes,
            )
        )
        is not None
    }


def _infer_directory_episode_sequence(
    parent_path: str,
    media_nodes: list[CloudNode],
) -> DirectoryEpisodeInference | None:
    if len(media_nodes) < MIN_SEQUENCE_FILES:
        return None
    if not _has_meaningful_directory_name(parent_path):
        return None

    parsed_numbers = {
        cloud_node.id: parse_bare_episode_numbers(cloud_node.name)
        for cloud_node in media_nodes
    }
    numeric_items = {
        node_id: episode_numbers
        for node_id, episode_numbers in parsed_numbers.items()
        if episode_numbers
    }
    if len(numeric_items) / len(media_nodes) < MIN_NUMERIC_RATIO:
        return None

    primary_numbers = [episode_numbers[0] for episode_numbers in numeric_items.values()]
    if len(primary_numbers) != len(set(primary_numbers)):
        return None
    if not _is_near_continuous(primary_numbers):
        return None

    return DirectoryEpisodeInference(
        season_number=DEFAULT_INFERRED_SEASON,
        episode_numbers_by_node_id=numeric_items,
    )


def _has_meaningful_directory_name(parent_path: str) -> bool:
    directory_name = PurePosixPath(parent_path).name.strip().casefold()
    return bool(directory_name) and directory_name not in GENERIC_DIRECTORY_NAMES


def _is_near_continuous(episode_numbers: list[int]) -> bool:
    ordered_numbers = sorted(episode_numbers)
    missing_count = ordered_numbers[-1] - ordered_numbers[0] + 1 - len(ordered_numbers)
    allowed_missing = max(1, int(len(ordered_numbers) * MAX_GAP_RATIO))
    return missing_count <= allowed_missing
