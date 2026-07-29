from app.domain import SourceClassification
from app.providers.base import CloudNode
from app.services.source_classifier import ClassificationPolicy, classify_source_node

MEBIBYTE = 1024**2


def make_node(name: str, *, size_bytes: int = 0, path: str | None = None) -> CloudNode:
    return CloudNode(
        id=name,
        parent_id="parent",
        name=name,
        path=path or f"/光鸭云盘/未整理/{name}",
        is_directory=False,
        size_bytes=size_bytes,
    )


def test_filters_small_sample_using_plex_threshold() -> None:
    result = classify_source_node(
        make_node("Movie.sample.mkv", size_bytes=299 * MEBIBYTE),
        ClassificationPolicy(source_root="/光鸭云盘/未整理"),
    )

    assert result.classification == SourceClassification.IGNORED
    assert result.reason_code == "SMALL_SAMPLE"


def test_keeps_large_movie_containing_sample_word_as_media() -> None:
    result = classify_source_node(
        make_node("The.Sample.2024.mkv", size_bytes=301 * MEBIBYTE),
        ClassificationPolicy(source_root="/光鸭云盘/未整理"),
    )

    assert result.classification == SourceClassification.MEDIA


def test_classifies_extra_directory_as_reviewable_extra() -> None:
    result = classify_source_node(
        make_node(
            "making-of.mkv",
            path="/光鸭云盘/未整理/Movie/extras/making-of.mkv",
        ),
        ClassificationPolicy(source_root="/光鸭云盘/未整理"),
    )

    assert result.classification == SourceClassification.EXTRA
    assert result.is_reviewable is True


def test_filters_system_and_archive_files() -> None:
    system_result = classify_source_node(
        make_node(".DS_Store"),
        ClassificationPolicy(source_root="/光鸭云盘/未整理"),
    )
    archive_result = classify_source_node(
        make_node("release.rar"),
        ClassificationPolicy(source_root="/光鸭云盘/未整理"),
    )

    assert system_result.classification == SourceClassification.IGNORED
    assert archive_result.classification == SourceClassification.IGNORED


def test_excludes_target_tree_when_nested_inside_source() -> None:
    result = classify_source_node(
        make_node(
            "Movie.mkv",
            path="/光鸭云盘/未整理/输出/Movies/Movie.mkv",
        ),
        ClassificationPolicy(
            source_root="/光鸭云盘/未整理",
            target_root="/光鸭云盘/未整理/输出",
        ),
    )

    assert result.classification == SourceClassification.IGNORED
    assert result.reason_code == "TARGET_TREE"


def test_applies_user_glob_to_relative_path() -> None:
    result = classify_source_node(
        make_node(
            "Episode01.mkv",
            path="/光鸭云盘/未整理/临时/Episode01.mkv",
        ),
        ClassificationPolicy(
            source_root="/光鸭云盘/未整理",
            exclude_globs=("临时/*",),
        ),
    )

    assert result.classification == SourceClassification.IGNORED
    assert result.reason_code == "CUSTOM_GLOB"
