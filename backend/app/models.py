from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain import (
    AccountStatus,
    JobStatus,
    JobTriggerType,
    LibraryCategory,
    MatchDecision,
    MediaType,
    MetadataSource,
    OperationStatus,
    OperationType,
    RegionBucket,
    RuleScheduleType,
    SourceAction,
    SourceClassification,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CloudAccount(Base, TimestampMixin):
    __tablename__ = "cloud_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32), default="guangya")
    display_name: Mapped[str] = mapped_column(String(128), default="光鸭账号")
    status: Mapped[AccountStatus] = mapped_column(String(32), default=AccountStatus.REAUTH_REQUIRED)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)


class OrganizeJob(Base, TimestampMixin):
    __tablename__ = "organize_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    source_directory_id: Mapped[str] = mapped_column(String(128))
    source_directory_path: Mapped[str] = mapped_column(String(512))
    target_directory_id: Mapped[str] = mapped_column(String(128))
    target_directory_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[JobStatus] = mapped_column(String(32), default=JobStatus.DRAFT)
    progress: Mapped[float] = mapped_column(Float, default=0)
    revision: Mapped[int] = mapped_column(default=0)
    progress_detail: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    current_stage: Mapped[str] = mapped_column(String(64), default="等待开始")
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    total_items: Mapped[int] = mapped_column(default=0)
    approved_items: Mapped[int] = mapped_column(default=0)
    review_items: Mapped[int] = mapped_column(default=0)
    failed_items: Mapped[int] = mapped_column(default=0)
    copied_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("organize_rules.id", ondelete="SET NULL"), nullable=True
    )
    trigger_type: Mapped[JobTriggerType] = mapped_column(
        String(24), default=JobTriggerType.MANUAL
    )
    scanned_directories: Mapped[int] = mapped_column(default=0)
    skipped_directories: Mapped[int] = mapped_column(default=0)
    changed_items: Mapped[int] = mapped_column(default=0)

    source_items: Mapped[list["SourceItem"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def auto_approve_enabled(self) -> bool:
        return bool(self.config.get("auto_approve_enabled", True))

    @property
    def auto_execute_after_approval(self) -> bool:
        return bool(self.config.get("auto_execute_after_approval", False))

    @property
    def ai_review_running(self) -> bool:
        return bool(self.config.get("_ai_review_queued", False))


class SourceItem(Base, TimestampMixin):
    __tablename__ = "source_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("organize_jobs.id", ondelete="CASCADE"))
    cloud_file_id: Mapped[str] = mapped_column(String(128))
    parent_file_id: Mapped[str] = mapped_column(String(128), default="")
    source_path: Mapped[str] = mapped_column(String(1024))
    filename: Mapped[str] = mapped_column(String(512))
    extension: Mapped[str] = mapped_column(String(24), default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    relative_path: Mapped[str] = mapped_column(String(1024), default="")
    classification: Mapped[SourceClassification] = mapped_column(
        String(32), default=SourceClassification.UNKNOWN
    )
    filter_reason: Mapped[str] = mapped_column(String(64), default="")
    user_action: Mapped[SourceAction] = mapped_column(String(16), default=SourceAction.DEFAULT)
    group_key: Mapped[str] = mapped_column(String(512), default="")
    associated_media_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_items.id", ondelete="CASCADE"), nullable=True
    )
    is_directory: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ignored: Mapped[bool] = mapped_column(Boolean, default=False)

    job: Mapped[OrganizeJob] = relationship(back_populates="source_items")
    media_match: Mapped["MediaMatch | None"] = relationship(
        back_populates="source_item", cascade="all, delete-orphan", uselist=False
    )


class MediaEntity(Base, TimestampMixin):
    __tablename__ = "media_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tmdb_id: Mapped[int | None] = mapped_column(nullable=True)
    metadata_source: Mapped[MetadataSource] = mapped_column(
        String(16), default=MetadataSource.TMDB
    )
    provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    local_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    media_type: Mapped[MediaType] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    original_title: Mapped[str] = mapped_column(String(256), default="")
    year: Mapped[int | None] = mapped_column(nullable=True)
    overview: Mapped[str] = mapped_column(Text, default="")
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class MediaSeason(Base, TimestampMixin):
    __tablename__ = "media_seasons"
    __table_args__ = (UniqueConstraint("media_entity_id", "season_number", name="uq_media_season"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    media_entity_id: Mapped[str] = mapped_column(
        ForeignKey("media_entities.id", ondelete="CASCADE")
    )
    season_number: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String(256), default="")
    overview: Mapped[str] = mapped_column(Text, default="")
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    media_entity: Mapped[MediaEntity] = relationship()


class MediaEpisode(Base, TimestampMixin):
    __tablename__ = "media_episodes"
    __table_args__ = (
        UniqueConstraint("media_season_id", "episode_number", name="uq_media_episode"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    media_season_id: Mapped[str] = mapped_column(ForeignKey("media_seasons.id", ondelete="CASCADE"))
    tmdb_id: Mapped[int | None] = mapped_column(nullable=True)
    episode_number: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String(256), default="")
    overview: Mapped[str] = mapped_column(Text, default="")
    air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    still_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    media_season: Mapped[MediaSeason] = relationship()


class MediaMatch(Base, TimestampMixin):
    __tablename__ = "media_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_item_id: Mapped[str] = mapped_column(
        ForeignKey("source_items.id", ondelete="CASCADE"), unique=True
    )
    media_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_entities.id"), nullable=True
    )
    media_type: Mapped[MediaType] = mapped_column(String(16), default=MediaType.UNKNOWN)
    parsed_title: Mapped[str] = mapped_column(String(256), default="")
    parsed_year: Mapped[int | None] = mapped_column(nullable=True)
    season_number: Mapped[int | None] = mapped_column(nullable=True)
    episode_numbers: Mapped[list[int]] = mapped_column(JSON, default=list)
    edition: Mapped[str] = mapped_column(String(128), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    decision: Mapped[MatchDecision] = mapped_column(String(32), default=MatchDecision.UNRESOLVED)
    candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    target_path: Mapped[str] = mapped_column(String(1024), default="")
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    group_key: Mapped[str] = mapped_column(String(512), default="")
    episode_title: Mapped[str] = mapped_column(String(256), default="")
    episode_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    release_info: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    metadata_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    match_origin: Mapped[str] = mapped_column(String(32), default="RULE")
    metadata_hint: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    decision_reasons: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    library_category: Mapped[LibraryCategory] = mapped_column(
        String(24), default=LibraryCategory.MOVIE
    )
    region_bucket: Mapped[RegionBucket] = mapped_column(
        String(24), default=RegionBucket.OTHER
    )
    classification_reasons: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    quality_profile: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    version_group_key: Mapped[str] = mapped_column(String(512), default="")
    version_score: Mapped[float] = mapped_column(Float, default=0)
    version_recommendation: Mapped[str] = mapped_column(String(24), default="SINGLE")

    source_item: Mapped[SourceItem] = relationship(back_populates="media_match")
    media_entity: Mapped[MediaEntity | None] = relationship()


class MediaMatchEpisode(Base):
    __tablename__ = "media_match_episodes"

    media_match_id: Mapped[str] = mapped_column(
        ForeignKey("media_matches.id", ondelete="CASCADE"), primary_key=True
    )
    media_episode_id: Mapped[str] = mapped_column(
        ForeignKey("media_episodes.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(default=0)


class FileOperation(Base, TimestampMixin):
    __tablename__ = "file_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("organize_jobs.id", ondelete="CASCADE"))
    source_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True
    )
    operation_type: Mapped[OperationType] = mapped_column(String(24))
    status: Mapped[OperationStatus] = mapped_column(String(24), default=OperationStatus.PENDING)
    source_path: Mapped[str] = mapped_column(String(1024), default="")
    target_path: Mapped[str] = mapped_column(String(1024), default="")
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("organize_jobs.id", ondelete="CASCADE"))
    media_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_entities.id"), nullable=True
    )
    asset_type: Mapped[str] = mapped_column(String(32))
    cloud_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_path: Mapped[str] = mapped_column(String(1024))
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("organize_jobs.id", ondelete="CASCADE"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(512))
    severity: Mapped[str] = mapped_column(String(16), default="info")
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[OrganizeJob | None] = relationship(back_populates="audit_events")


class JobProgressEvent(Base):
    __tablename__ = "job_progress_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("organize_jobs.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(48))
    scope: Mapped[str] = mapped_column(String(24), default="JOB")
    match_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    group_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    encrypted_value: Mapped[str] = mapped_column(Text)


class OrganizeRule(Base, TimestampMixin):
    __tablename__ = "organize_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source_directory_id: Mapped[str] = mapped_column(String(128))
    source_directory_path: Mapped[str] = mapped_column(String(512))
    target_directory_id: Mapped[str] = mapped_column(String(128))
    target_directory_path: Mapped[str] = mapped_column(String(512))
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    schedule_type: Mapped[RuleScheduleType] = mapped_column(
        String(24), default=RuleScheduleType.MANUAL
    )
    interval_minutes: Mapped[int | None] = mapped_column(nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_limit: Mapped[int] = mapped_column(default=2)
    retry_count: Mapped[int] = mapped_column(default=0)
    retry_backoff_minutes: Mapped[int] = mapped_column(default=5)


class DirectorySnapshot(Base, TimestampMixin):
    __tablename__ = "directory_snapshots"
    __table_args__ = (
        UniqueConstraint("rule_id", "cloud_directory_id", name="uq_rule_directory_snapshot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("organize_rules.id", ondelete="CASCADE"), index=True
    )
    cloud_directory_id: Mapped[str] = mapped_column(String(128))
    directory_path: Mapped[str] = mapped_column(String(1024))
    child_signature: Mapped[str] = mapped_column(String(64))
    child_count: Mapped[int] = mapped_column(default=0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RuleSourceItem(Base, TimestampMixin):
    __tablename__ = "rule_source_items"
    __table_args__ = (
        UniqueConstraint("rule_id", "cloud_file_id", name="uq_rule_source_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("organize_rules.id", ondelete="CASCADE"), index=True
    )
    cloud_file_id: Mapped[str] = mapped_column(String(128))
    source_path: Mapped[str] = mapped_column(String(1024))
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    state: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
