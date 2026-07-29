import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis

from app.config import Settings

logger = logging.getLogger(__name__)
QUEUE_NAME = "guangya-media-jobs"


class JobQueue:
    def __init__(
        self,
        settings: Settings,
        inline_handler: Callable[[str, str], Awaitable[None]],
    ) -> None:
        self._settings = settings
        self._inline_handler = inline_handler

    async def enqueue(self, action: str, job_id: str) -> None:
        if self._settings.demo_mode:
            asyncio.create_task(self._run_inline(action, job_id))
            return
        redis = Redis.from_url(self._settings.redis_url, decode_responses=True)
        try:
            await redis.lpush(QUEUE_NAME, json.dumps({"action": action, "job_id": job_id}))
        finally:
            await redis.aclose()

    async def _run_inline(self, action: str, job_id: str) -> None:
        try:
            await self._inline_handler(action, job_id)
        except RuntimeError:
            logger.exception("Inline job failed", extra={"job_id": job_id, "action": action})
