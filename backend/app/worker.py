import asyncio
import json
import logging

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap import build_organizer_service, build_provider
from app.config import get_settings
from app.database import SessionFactory
from app.domain import JobStatus
from app.models import AuditEvent, OrganizeJob
from app.providers.base import CloudProvider
from app.security import TokenCipher
from app.services.login_manager import LoginManager
from app.services.organizer import OrganizerError
from app.services.queue import QUEUE_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
INTERRUPTED_SCAN_STATUSES = {
    JobStatus.SCANNING,
    JobStatus.IDENTIFYING,
}


async def run_worker() -> None:
    settings = get_settings()
    provider = build_provider()
    login_manager = LoginManager(provider, TokenCipher(settings))
    async with SessionFactory() as session:
        await login_manager.restore_session(session)
        await recover_interrupted_scans(session)
    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
    )
    logger.info("Worker started")
    try:
        while True:
            try:
                queue_item = await redis.brpop(QUEUE_NAME, timeout=2)
            except (RedisConnectionError, RedisTimeoutError):
                logger.warning("Redis queue temporarily unavailable; retrying")
                await asyncio.sleep(1)
                continue
            if queue_item is None:
                continue
            _, raw_payload = queue_item
            payload = json.loads(raw_payload)
            action = str(payload["action"])
            job_id = str(payload["job_id"])
            try:
                await run_queued_action(
                    action=action,
                    job_id=job_id,
                    provider=provider,
                    login_manager=login_manager,
                )
            except (OrganizerError, RuntimeError):
                logger.exception(
                    "Queued job action failed",
                    extra={"job_id": job_id, "action": action},
                )
    finally:
        await redis.aclose()


async def run_queued_action(
    *,
    action: str,
    job_id: str,
    provider: CloudProvider,
    login_manager: LoginManager,
) -> None:
    async with SessionFactory() as session:
        await login_manager.restore_session(session)
    organizer = await build_organizer_service(provider)
    await organizer.run_action(action, job_id)


async def recover_interrupted_scans(session: AsyncSession) -> None:
    interrupted_jobs = list(
        (
            await session.scalars(
                select(OrganizeJob).where(OrganizeJob.status.in_(INTERRUPTED_SCAN_STATUSES))
            )
        ).all()
    )
    for job in interrupted_jobs:
        job.status = JobStatus.CANCELED if job.is_cancel_requested else JobStatus.FAILED
        job.current_stage = "Worker 重启，扫描已停止"
        job.error_message = (
            None if job.is_cancel_requested else "扫描因 Worker 重启中断，请重新扫描"
        )
        session.add(
            AuditEvent(
                job_id=job.id,
                event_type="SCAN_INTERRUPTED",
                message="Worker 重启后已安全终止旧扫描，请重新扫描",
                severity="warning",
            )
        )
    if interrupted_jobs:
        await session.commit()


if __name__ == "__main__":
    asyncio.run(run_worker())
