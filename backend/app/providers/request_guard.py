import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

RATE_LIMIT_KEY = "guangya-media:cloud-api:request-gate"
MIN_REDIS_WAIT_SECONDS = 0.05


class RequestKind(StrEnum):
    READ = "read"
    WRITE = "write"
    POLL = "poll"
    AUTH = "auth"


@dataclass(frozen=True, slots=True)
class RequestGuardPolicy:
    read_interval_seconds: float
    write_interval_seconds: float
    poll_interval_seconds: float
    jitter_seconds: float

    def interval_for(self, kind: RequestKind) -> float:
        if kind is RequestKind.WRITE:
            return self.write_interval_seconds
        if kind is RequestKind.POLL:
            return self.poll_interval_seconds
        return self.read_interval_seconds


class RedisGateProtocol(Protocol):
    async def set(
        self,
        name: str,
        value: str,
        *,
        nx: bool,
        px: int,
    ) -> bool | None: ...

    async def pttl(self, name: str) -> int: ...

    async def aclose(self) -> None: ...


class CloudRequestGuard:
    """Space cloud requests across API and worker processes.

    Redis coordinates the two application processes. If Redis is temporarily
    unavailable, the local monotonic gate still prevents an in-process burst.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        policy: RequestGuardPolicy,
        redis_client: RedisGateProtocol | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._policy = policy
        self._sleep = sleep
        self._monotonic = monotonic
        self._random_uniform = random_uniform
        self._lock = asyncio.Lock()
        self._next_local_request_at = 0.0
        self._redis_warning_emitted = False
        self._redis: RedisGateProtocol | None = redis_client
        if self._redis is None and redis_url:
            self._redis = cast(
                RedisGateProtocol,
                Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                ),
            )

    async def wait(self, kind: RequestKind) -> None:
        interval = self._policy.interval_for(kind)
        async with self._lock:
            if self._redis is not None:
                try:
                    await self._wait_distributed(interval)
                    self._redis_warning_emitted = False
                    return
                except RedisError:
                    if not self._redis_warning_emitted:
                        logger.warning(
                            "Redis cloud API gate unavailable; using local rate limit"
                        )
                        self._redis_warning_emitted = True
            await self._wait_local(interval)

    async def _wait_distributed(self, interval: float) -> None:
        assert self._redis is not None
        interval_ms = max(1, round(interval * 1000))
        while True:
            acquired = await self._redis.set(
                RATE_LIMIT_KEY,
                "1",
                nx=True,
                px=interval_ms,
            )
            if acquired:
                jitter = self._random_uniform(0, self._policy.jitter_seconds)
                if jitter > 0:
                    await self._sleep(jitter)
                return
            remaining_ms = await self._redis.pttl(RATE_LIMIT_KEY)
            wait_seconds = max(
                MIN_REDIS_WAIT_SECONDS,
                remaining_ms / 1000 if remaining_ms > 0 else MIN_REDIS_WAIT_SECONDS,
            )
            await self._sleep(wait_seconds)

    async def _wait_local(self, interval: float) -> None:
        now = self._monotonic()
        delay = max(0.0, self._next_local_request_at - now)
        delay += self._random_uniform(0, self._policy.jitter_seconds)
        if delay > 0:
            await self._sleep(delay)
        self._next_local_request_at = self._monotonic() + interval

    async def aclose(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
