import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.domain import JobStatus, JobTriggerType, RuleScheduleType
from app.models import OrganizeJob, OrganizeRule, utc_now
from app.schemas import CreateOrganizeRuleRequest, UpdateOrganizeRuleRequest
from app.services.queue import QUEUE_NAME

ACTIVE_RULE_JOB_STATUSES = {
    JobStatus.DRAFT,
    JobStatus.SCANNING,
    JobStatus.IDENTIFYING,
    JobStatus.COPYING,
    JobStatus.SCRAPING,
    JobStatus.FINALIZING,
}
RULE_LOCK_TTL_SECONDS = 6 * 60 * 60


class OrganizeRuleError(RuntimeError):
    pass


class OrganizeRuleService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        enqueue: Callable[[str, str], Awaitable[None]],
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._enqueue = enqueue

    async def create(
        self, request: CreateOrganizeRuleRequest, session: AsyncSession
    ) -> OrganizeRule:
        rule = OrganizeRule(
            **request.model_dump(exclude={"config", "run_immediately"}),
            config=request.config.model_dump(mode="json"),
        )
        rule.next_run_at = next_run_at(rule, utc_now())
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    async def update(
        self,
        rule: OrganizeRule,
        request: UpdateOrganizeRuleRequest,
        session: AsyncSession,
    ) -> OrganizeRule:
        values = request.model_dump(exclude={"config"})
        for key, value in values.items():
            setattr(rule, key, value)
        rule.config = request.config.model_dump(mode="json")
        rule.next_run_at = next_run_at(rule, utc_now())
        await session.commit()
        await session.refresh(rule)
        return rule

    async def run(
        self,
        rule: OrganizeRule,
        session: AsyncSession,
        *,
        trigger: JobTriggerType,
    ) -> tuple[OrganizeJob, bool]:
        active = await session.scalar(
            select(OrganizeJob)
            .where(
                OrganizeJob.rule_id == rule.id,
                OrganizeJob.status.in_(ACTIVE_RULE_JOB_STATUSES),
            )
            .order_by(OrganizeJob.created_at.desc())
        )
        if active is not None:
            active.config = {**active.config, "_dirty_retry_requested": True}
            await session.commit()
            await _mark_dirty(self._settings, rule.id)
            return active, True
        claimed = await _claim_rule(self._settings, rule.id)
        if not claimed:
            await _mark_dirty(self._settings, rule.id)
            fallback = await session.scalar(
                select(OrganizeJob)
                .where(OrganizeJob.rule_id == rule.id)
                .order_by(OrganizeJob.created_at.desc())
            )
            if fallback is None:
                raise OrganizeRuleError("整理规则正在由其他 Worker 领取")
            fallback.config = {**fallback.config, "_dirty_retry_requested": True}
            await session.commit()
            return fallback, True
        job = _job_from_rule(rule, trigger)
        session.add(job)
        await session.flush()
        rule.last_job_id = job.id
        rule.last_run_at = utc_now()
        rule.last_error = None
        rule.next_run_at = next_run_at(rule, rule.last_run_at)
        await session.commit()
        try:
            await self._enqueue("scan", job.id)
        except Exception as error:
            rule.last_error = type(error).__name__
            await session.commit()
            await _release_rule(self._settings, rule.id)
            raise
        return job, False

    async def run_due_rules(self) -> int:
        async with self._session_factory() as session:
            now = utc_now()
            rules = list(
                (
                    await session.scalars(
                        select(OrganizeRule).where(
                            OrganizeRule.enabled.is_(True),
                            OrganizeRule.schedule_type != RuleScheduleType.MANUAL,
                            OrganizeRule.next_run_at.is_not(None),
                            OrganizeRule.next_run_at <= now,
                        )
                    )
                ).all()
            )
            for rule in rules:
                try:
                    trigger = (
                        JobTriggerType.FAILED_RETRY
                        if rule.retry_count > 0 and rule.last_error
                        else JobTriggerType.SCHEDULED
                    )
                    await self.run(rule, session, trigger=trigger)
                except Exception as error:
                    rule.last_error = type(error).__name__
                    rule.next_run_at = now + timedelta(minutes=5)
                    await session.commit()
            return len(rules)


async def complete_rule_job(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    job_id: str,
) -> OrganizeJob | None:
    async with session_factory() as session:
        job = await session.get(OrganizeJob, job_id)
        if job is None or not job.rule_id:
            return None
        rule = await session.get(OrganizeRule, job.rule_id)
        if rule is None:
            return None
        if job.status in {JobStatus.FAILED, JobStatus.PARTIAL_FAILED}:
            rule.last_error = job.error_message or job.current_stage
            if rule.retry_count < rule.retry_limit:
                rule.retry_count += 1
                delay = rule.retry_backoff_minutes * 2 ** (rule.retry_count - 1)
                rule.next_run_at = utc_now() + timedelta(minutes=delay)
                await session.commit()
                await _release_rule(settings, rule.id)
                return None
        else:
            rule.retry_count = 0
            rule.last_error = None
            rule.next_run_at = next_run_at(rule, utc_now())
        await session.commit()
        dirty = bool(job.config.get("_dirty_retry_requested"))
        dirty = await _consume_dirty(settings, rule.id) or dirty
        await _release_rule(settings, rule.id)
        if not dirty:
            return None
        retry_job = _job_from_rule(rule, JobTriggerType.DIRTY_RETRY)
        session.add(retry_job)
        await session.flush()
        rule.last_job_id = retry_job.id
        rule.last_run_at = utc_now()
        await session.commit()
        return retry_job


async def enqueue_raw(settings: Settings, action: str, job_id: str) -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.lpush(QUEUE_NAME, json.dumps({"action": action, "job_id": job_id}))
    finally:
        await redis.aclose()


async def scheduler_loop(service: OrganizeRuleService) -> None:
    while True:
        with suppress(Exception):
            await service.run_due_rules()
        await asyncio.sleep(30)


def next_run_at(rule: OrganizeRule, after: datetime) -> datetime | None:
    if rule.enabled is False or rule.schedule_type == RuleScheduleType.MANUAL:
        return None
    if rule.schedule_type == RuleScheduleType.INTERVAL:
        return after + timedelta(minutes=rule.interval_minutes or 5)
    if not rule.cron_expression:
        return None
    try:
        timezone = ZoneInfo(rule.timezone)
    except ZoneInfoNotFoundError as error:
        raise OrganizeRuleError("无效的规则时区") from error
    local = _aware(after).astimezone(timezone).replace(second=0, microsecond=0)
    candidate = local + timedelta(minutes=1)
    for _ in range(527_040):
        if _cron_matches(rule.cron_expression, candidate):
            return candidate.astimezone(UTC)
        candidate += timedelta(minutes=1)
    raise OrganizeRuleError("Cron 表达式在一年内没有可执行时间")


def _job_from_rule(rule: OrganizeRule, trigger: JobTriggerType) -> OrganizeJob:
    return OrganizeJob(
        name=f"{rule.name} · {utc_now().astimezone().strftime('%m-%d %H:%M')}",
        source_directory_id=rule.source_directory_id,
        source_directory_path=rule.source_directory_path,
        target_directory_id=rule.target_directory_id,
        target_directory_path=rule.target_directory_path,
        config=dict(rule.config),
        rule_id=rule.id,
        trigger_type=trigger,
    )


def _cron_matches(expression: str, value: datetime) -> bool:
    minute, hour, day, month, weekday = expression.split()
    cron_weekday = (value.weekday() + 1) % 7
    return all(
        (
            _cron_field_matches(minute, value.minute, 0, 59),
            _cron_field_matches(hour, value.hour, 0, 23),
            _cron_field_matches(day, value.day, 1, 31),
            _cron_field_matches(month, value.month, 1, 12),
            _cron_field_matches(weekday, cron_weekday, 0, 6),
        )
    )


def _cron_field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    for part in field.split(","):
        if part == "*":
            return True
        if part.startswith("*/") and part[2:].isdigit():
            step = int(part[2:])
            return step > 0 and (value - minimum) % step == 0
        if "-" in part:
            start, end = part.split("-", 1)
            if start.isdigit() and end.isdigit() and int(start) <= value <= int(end):
                return True
        if part.isdigit() and minimum <= int(part) <= maximum and int(part) == value:
            return True
    return False


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _lock_key(rule_id: str) -> str:
    return f"organize-rule:{rule_id}:lock"


def _dirty_key(rule_id: str) -> str:
    return f"organize-rule:{rule_id}:dirty"


async def _claim_rule(settings: Settings, rule_id: str) -> bool:
    if settings.demo_mode:
        return True
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        return bool(await redis.set(_lock_key(rule_id), "1", ex=RULE_LOCK_TTL_SECONDS, nx=True))
    finally:
        await redis.aclose()


async def _release_rule(settings: Settings, rule_id: str) -> None:
    if settings.demo_mode:
        return
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.delete(_lock_key(rule_id))
    finally:
        await redis.aclose()


async def _mark_dirty(settings: Settings, rule_id: str) -> None:
    if settings.demo_mode:
        return
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.set(_dirty_key(rule_id), "1", ex=RULE_LOCK_TTL_SECONDS)
    finally:
        await redis.aclose()


async def _consume_dirty(settings: Settings, rule_id: str) -> bool:
    if settings.demo_mode:
        return False
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        return bool(await redis.getdel(_dirty_key(rule_id)))
    finally:
        await redis.aclose()
