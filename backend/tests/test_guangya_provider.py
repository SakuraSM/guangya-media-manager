from app.providers.guangya import _to_cloud_node


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
