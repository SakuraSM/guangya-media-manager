from app.providers.request_guard import (
    RATE_LIMIT_KEY,
    CloudRequestGuard,
    RequestGuardPolicy,
    RequestKind,
)


class FakeRedisGate:
    def __init__(self) -> None:
        self.set_calls: list[tuple[str, int]] = []
        self._attempt = 0
        self.closed = False

    async def set(
        self,
        name: str,
        value: str,
        *,
        nx: bool,
        px: int,
    ) -> bool | None:
        assert value == "1"
        assert nx is True
        self.set_calls.append((name, px))
        self._attempt += 1
        return self._attempt > 1

    async def pttl(self, name: str) -> int:
        assert name == RATE_LIMIT_KEY
        return 250

    async def aclose(self) -> None:
        self.closed = True


async def test_distributed_guard_waits_for_existing_request_window() -> None:
    redis = FakeRedisGate()
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    guard = CloudRequestGuard(
        redis_url="",
        policy=RequestGuardPolicy(0.35, 1.2, 1.0, 0),
        redis_client=redis,
        sleep=sleep,
    )

    await guard.wait(RequestKind.WRITE)
    await guard.aclose()

    assert redis.set_calls == [(RATE_LIMIT_KEY, 1200), (RATE_LIMIT_KEY, 1200)]
    assert sleeps == [0.25]
    assert redis.closed is True


async def test_local_guard_spaces_requests_when_redis_is_disabled() -> None:
    current_time = 10.0
    sleeps: list[float] = []

    def monotonic() -> float:
        return current_time

    async def sleep(delay: float) -> None:
        nonlocal current_time
        sleeps.append(delay)
        current_time += delay

    guard = CloudRequestGuard(
        redis_url="",
        policy=RequestGuardPolicy(1.0, 2.0, 1.5, 0),
        sleep=sleep,
        monotonic=monotonic,
    )

    await guard.wait(RequestKind.READ)
    await guard.wait(RequestKind.READ)

    assert sleeps == [1.0]
