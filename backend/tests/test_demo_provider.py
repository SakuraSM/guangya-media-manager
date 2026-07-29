from app.providers.demo import DemoGuangyaProvider


async def test_demo_provider_copy_resolve_rename_and_move() -> None:
    provider = DemoGuangyaProvider()
    staging = await provider.create_directory("staging", "target")
    destination = await provider.create_directory("destination", "target")

    copy_task = await provider.copy_items(["interstellar"], staging.id)
    assert await provider.task_is_complete(copy_task.task_id)
    copied_nodes = await provider.resolve_task_nodes(copy_task.task_id, staging.path)
    assert len(copied_nodes) == 1

    copied = copied_nodes[0]
    await provider.rename_item(copied.id, "星际穿越 (2014).mkv")
    move_task = await provider.move_items([copied.id], destination.id)
    assert await provider.task_is_complete(move_task.task_id)
    destination_nodes = await provider.list_directory(
        destination.id, destination.path
    )

    assert [node.name for node in destination_nodes] == ["星际穿越 (2014).mkv"]
    assert destination_nodes[0].fingerprint == "demo-interstellar"
