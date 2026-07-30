from app.database import SessionFactory, engine
from app.domain import JobStatus
from app.models import Base, OrganizeJob
from app.worker import recover_interrupted_scans


async def test_marks_interrupted_scan_as_failed_after_worker_restart() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionFactory() as session:
        job = OrganizeJob(
            name="中断恢复测试",
            source_directory_id="source",
            source_directory_path="/光鸭云盘/未整理",
            target_directory_id="target",
            target_directory_path="/光鸭云盘/电影与剧集",
            status=JobStatus.IDENTIFYING,
        )
        session.add(job)
        await session.commit()
        job_id = job.id

        await recover_interrupted_scans(session)
        await session.refresh(job)

    assert job.id == job_id
    assert job.status == JobStatus.FAILED
    assert job.error_message == "扫描因 Worker 重启中断，请重新扫描"
