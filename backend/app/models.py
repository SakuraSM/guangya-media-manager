from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain import (
    AccountStatus,
    JobStatus,
    MatchDecision,
    MediaType,
    OperationStatus,
    OperationType,
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
    current_stage: Mapped[str] = mapped_column(String(64), default="等待开始")
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    total_items: Mapped[int] = mapped_column(default=0)
    approved_items: Mapped[int] = mapped_column(default=0)
    review_items: Mapped[int] = mapped_column(default=0)
    failed_items: Mapped[int] = mapped_column(default=0)
    copied_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    source_items: Mapped[list["SourceItem"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


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
    tmdb_id: Mapped[int] = mapped_column()
    media_type: Mapped[MediaType] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    original_title: Mapped[str] = mapped_column(String(256), default="")
    year: Mapped[int | None] = mapped_column(nullable=True)
    overview: Mapped[str] = mapped_column(Text, default="")
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


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
    decision: Mapped[MatchDecision] = mapped_column(
        String(32), default=MatchDecision.UNRESOLVED
    )
    candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    target_path: Mapped[str] = mapped_column(String(1024), default="")
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)

    source_item: Mapped[SourceItem] = relationship(back_populates="media_match")
    media_entity: Mapped[MediaEntity | None] = relationship()


class FileOperation(Base, TimestampMixin):
    __tablename__ = "file_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("organize_jobs.id", ondelete="CASCADE"))
    source_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True
    )
    operation_type: Mapped[OperationType] = mapped_column(String(24))
    status: Mapped[OperationStatus] = mapped_column(
        String(24), default=OperationStatus.PENDING
    )
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


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    encrypted_value: Mapped[str] = mapped_column(Text)
