import asyncio
import json
import logging

from redis.asyncio import Redis

from app.bootstrap import build_organizer_service, build_provider
from app.config import get_settings
from app.database import SessionFactory
from app.security import TokenCipher
from app.services.login_manager import LoginManager
from app.services.queue import QUEUE_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    provider = build_provider()
    login_manager = LoginManager(provider, TokenCipher(settings))
    async with SessionFactory() as session:
        await login_manager.restore_session(session)
    organizer = await build_organizer_service(provider)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Worker started")
    try:
        while True:
            queue_item = await redis.brpop(QUEUE_NAME, timeout=5)
            if queue_item is None:
                continue
            _, raw_payload = queue_item
            payload = json.loads(raw_payload)
            async with SessionFactory() as session:
                await login_manager.restore_session(session)
            await organizer.run_action(str(payload["action"]), str(payload["job_id"]))
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run_worker())
