from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain import (
    AccountStatus,
    JobStatus,
    MatchDecision,
    MediaType,
    SourceAction,
    SourceClassification,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SessionLoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class SessionState(ApiModel):
    is_authenticated: bool


class CloudAccountView(ApiModel):
    id: str
    display_name: str
    status: AccountStatus
    capacity_bytes: int
    used_bytes: int


class CloudLoginStart(ApiModel):
    login_id: str
    verification_uri: str
    expires_in_seconds: int
    poll_interval_seconds: int


class CloudLoginStatus(ApiModel):
    login_id: str
    status: str
    account: CloudAccountView | None = None
    error_message: str | None = None


class CloudDirectory(ApiModel):
    id: str
    parent_id: str
    name: str
    path: str
    item_count: int = 0


class JobConfig(BaseModel):
    generate_nfo: bool = True
    download_poster: bool = True
    download_fanart: bool = True
    download_backdrop_alias: bool = True
    download_season_poster: bool = True
    download_episode_thumb: bool = True
    season_artwork_compat: bool = True
    scrape_metadata_language: Literal["zh-CN", "en-US", "ja-JP", "ko-KR"] = "zh-CN"
    scrape_image_quality: Literal["STANDARD", "ORIGINAL"] = "STANDARD"
    rename_subtitles: bool = True
    auto_approve_threshold: float = Field(default=0.9, ge=0.5, le=1)
    review_threshold: float = Field(default=0.65, ge=0, le=0.9)
    naming_profile: str = Field(default="UNIVERSAL_ENHANCED", max_length=32)
    extras_policy: str = Field(default="EXCLUDE_REVIEWABLE", max_length=32)
    sample_max_mb: int = Field(default=300, ge=1, le=10_000)
    exclude_globs: list[str] = Field(default_factory=list, max_length=50)
    include_paths: list[str] = Field(default_factory=list, max_length=500)


class CreateJobRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    source_directory_id: str = Field(min_length=1, max_length=128)
    source_directory_path: str = Field(min_length=1, max_length=512)
    target_directory_id: str = Field(min_length=1, max_length=128)
    target_directory_path: str = Field(min_length=1, max_length=512)
    config: JobConfig = Field(default_factory=JobConfig)


class JobView(ApiModel):
    id: str
    name: str
    source_directory_path: str
    target_directory_path: str
    status: JobStatus
    progress: float
    current_stage: str
    total_items: int
    approved_items: int
    review_items: int
    failed_items: int
    copied_bytes: int
    error_message: str | None
    is_cancel_requested: bool
    created_at: datetime
    updated_at: datetime


class MatchCandidate(BaseModel):
    tmdb_id: int
    title: str
    original_title: str = ""
    year: int | None = None
    media_type: MediaType
    score: float = Field(ge=0, le=1)
    poster_url: str | None = None
    backdrop_url: str | None = None
    overview: str = ""


class MediaMatchView(ApiModel):
    id: str
    source_item_id: str
    filename: str
    source_path: str
    size_bytes: int
    media_type: MediaType
    parsed_title: str
    parsed_year: int | None
    season_number: int | None
    episode_numbers: list[int]
    edition: str
    confidence: float
    decision: MatchDecision
    selected_tmdb_id: int | None
    candidates: list[MatchCandidate]
    target_path: str
    reason_codes: list[str]
    group_key: str
    episode_title: str
    episode_date: str | None
    release_info: dict[str, object]


class MediaMatchPage(BaseModel):
    items: list[MediaMatchView]
    total: int
    page: int
    page_size: int
    pages: int


class SourceItemView(ApiModel):
    id: str
    filename: str
    source_path: str
    relative_path: str
    size_bytes: int
    classification: SourceClassification
    filter_reason: str
    user_action: SourceAction
    group_key: str
    is_reviewable: bool


class UpdateSourceItemRequest(BaseModel):
    action: SourceAction


class UpdateMediaGroupRequest(BaseModel):
    decision: MatchDecision
    candidate_tmdb_id: int | None = None


class MediaGroupUpdateResult(BaseModel):
    group_key: str
    updated_items: int


class UpdateMatchRequest(BaseModel):
    decision: MatchDecision
    candidate_tmdb_id: int | None = None


class BatchMatchApprovalItem(BaseModel):
    match_id: str = Field(min_length=1, max_length=64)
    candidate_tmdb_id: int = Field(gt=0)


class BatchApproveMatchesRequest(BaseModel):
    items: list[BatchMatchApprovalItem] = Field(
        min_length=1,
        max_length=100,
    )


class BatchApproveMatchesResult(BaseModel):
    updated_items: int


class ManualMatchRequest(BaseModel):
    tmdb_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=256)
    original_title: str = Field(default="", max_length=256)
    year: int | None = Field(default=None, ge=1870, le=2100)
    media_type: MediaType


class DashboardMetrics(BaseModel):
    pending_review: int
    completed_today: int
    failed: int
    copied_bytes: int


class AuditEventView(ApiModel):
    id: str
    event_type: str
    message: str
    severity: str
    created_at: datetime


class DashboardView(BaseModel):
    account: CloudAccountView | None
    metrics: DashboardMetrics
    active_job: JobView | None
    recent_jobs: list[JobView]
    recent_events: list[AuditEventView]


class LibraryItem(BaseModel):
    id: str
    title: str
    year: int | None
    media_type: MediaType
    poster_url: str | None
    target_path: str
    source_filename: str
    completed_at: datetime


class SettingsView(BaseModel):
    demo_mode: bool
    tmdb_configured: bool
    ai_configured: bool
    ai_base_url: str
    ai_model: str
    auto_approve_threshold: float
    review_threshold: float


class UpdateSettingsRequest(BaseModel):
    tmdb_api_token: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
