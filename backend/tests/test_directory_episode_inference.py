from app.providers.base import CloudNode
from app.services.directory_episode_inference import (
    infer_directory_episode_sequences,
)
from app.services.media_parser import parse_media_filename


def test_infers_first_season_from_three_ordered_numeric_files() -> None:
    nodes = [_episode_node(number) for number in (1, 2, 3)]

    inferences = infer_directory_episode_sequences(nodes)
    inference = inferences["/光鸭云盘/示例剧"]
    parsed = parse_media_filename(
        "02.mp4",
        parent_path="/光鸭云盘/示例剧",
        source_root="/光鸭云盘",
        inferred_season_number=inference.season_number,
    )

    assert parsed.title == "示例剧"
    assert parsed.season_number == 1
    assert parsed.episode_numbers == (2,)
    assert "DIRECTORY_SEQUENCE_INFERRED" in parsed.reason_codes


def test_does_not_infer_two_numeric_files() -> None:
    nodes = [_episode_node(number) for number in (1, 2)]

    assert infer_directory_episode_sequences(nodes) == {}


def test_does_not_infer_duplicate_or_sparse_episode_numbers() -> None:
    duplicate_nodes = [
        _episode_node(1, node_id="one-a"),
        _episode_node(1, node_id="one-b"),
        _episode_node(2),
    ]
    sparse_nodes = [_episode_node(number) for number in (1, 10, 20)]

    assert infer_directory_episode_sequences(duplicate_nodes) == {}
    assert infer_directory_episode_sequences(sparse_nodes) == {}


def test_requires_eighty_percent_numeric_files() -> None:
    nodes = [
        _episode_node(1),
        _episode_node(2),
        _episode_node(3),
        CloudNode(
            id="named-a",
            parent_id="show",
            name="幕后花絮.mp4",
            path="/光鸭云盘/示例剧/幕后花絮.mp4",
            is_directory=False,
        ),
        CloudNode(
            id="named-b",
            parent_id="show",
            name="预告片.mp4",
            path="/光鸭云盘/示例剧/预告片.mp4",
            is_directory=False,
        ),
    ]

    assert infer_directory_episode_sequences(nodes) == {}


def _episode_node(number: int, *, node_id: str | None = None) -> CloudNode:
    filename = f"{number:02d}.mp4"
    return CloudNode(
        id=node_id or f"episode-{number}",
        parent_id="show",
        name=filename,
        path=f"/光鸭云盘/示例剧/{filename}",
        is_directory=False,
    )
