import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain import (
    AccountStatus,
    JobStatus,
    JobTriggerType,
    LibraryCategory,
    MatchDecision,
    MediaType,
    MetadataSource,
    OperationStatus,
    OutputLayout,
    QualityProfile,
    RegionBucket,
    RuleScheduleType,
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
    item_count: int | None = None


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
    auto_approve_enabled: bool = True
    auto_execute_after_approval: bool = False
    naming_profile: str = Field(default="UNIVERSAL_ENHANCED", max_length=32)
    extras_policy: str = Field(default="EXCLUDE_REVIEWABLE", max_length=32)
    sample_max_mb: int = Field(default=300, ge=1, le=10_000)
    exclude_globs: list[str] = Field(default_factory=list, max_length=50)
    title_extraction_regex: str = Field(default="", max_length=256)
    include_paths: list[str] = Field(default_factory=list, max_length=500)
    output_layout: OutputLayout = OutputLayout.STANDARD
    include_region_directory: bool = True
    quality_profile: QualityProfile = QualityProfile.QUALITY

    @field_validator("title_extraction_regex")
    @classmethod
    def validate_title_extraction_regex(cls, value: str) -> str:
        pattern = value.strip()
        if not pattern:
            return ""
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"标题提取正则无效：{error.msg}") from error
        return pattern


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
    revision: int = 0
    progress_detail: dict[str, object] = Field(default_factory=dict)
    current_stage: str
    total_items: int
    approved_items: int
    executed_items: int = 0
    review_items: int
    failed_items: int
    copied_bytes: int
    error_message: str | None
    is_cancel_requested: bool
    auto_approve_enabled: bool
    auto_execute_after_approval: bool
    ai_review_running: bool
    rule_id: str | None = None
    trigger_type: JobTriggerType = JobTriggerType.MANUAL
    scanned_directories: int = 0
    skipped_directories: int = 0
    changed_items: int = 0
    created_at: datetime
    updated_at: datetime


class JobPage(BaseModel):
    items: list[JobView]
    total: int
    page: int
    page_size: int
    pages: int


class MatchCandidate(BaseModel):
    tmdb_id: int
    provider: MetadataSource = MetadataSource.TMDB
    provider_id: str | None = None
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
    metadata_source: MetadataSource | None = None
    metadata_provider: MetadataSource | None = None
    provider_id: str | None = None
    match_origin: str = "RULE"
    metadata_hint: dict[str, object] = Field(default_factory=dict)
    decision_reasons: list[dict[str, object]] = Field(default_factory=list)
    candidates: list[MatchCandidate]
    target_path: str
    reason_codes: list[str]
    group_key: str
    episode_title: str
    episode_date: str | None
    release_info: dict[str, object]
    library_category: LibraryCategory = LibraryCategory.MOVIE
    region_bucket: RegionBucket = RegionBucket.OTHER
    classification_reasons: list[dict[str, object]] = Field(default_factory=list)
    quality_profile: dict[str, object] = Field(default_factory=dict)
    version_group_key: str = ""
    version_score: float = 0
    version_recommendation: str = "SINGLE"
    execution_status: OperationStatus | None = None
    execution_error: str | None = None


class MediaMatchPage(BaseModel):
    items: list[MediaMatchView]
    total: int
    page: int
    page_size: int
    pages: int


class UpdateClassificationRequest(BaseModel):
    library_category: LibraryCategory
    region_bucket: RegionBucket


class UpdateVersionGroupRequest(BaseModel):
    selected_match_ids: list[str] = Field(min_length=1, max_length=100)


class VersionGroupUpdateResult(BaseModel):
    version_group_key: str
    updated_items: int


class OrganizeRuleBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    enabled: bool = True
    source_directory_id: str = Field(min_length=1, max_length=128)
    source_directory_path: str = Field(min_length=1, max_length=512)
    target_directory_id: str = Field(min_length=1, max_length=128)
    target_directory_path: str = Field(min_length=1, max_length=512)
    config: JobConfig = Field(default_factory=JobConfig)
    schedule_type: RuleScheduleType = RuleScheduleType.MANUAL
    interval_minutes: int | None = Field(default=None, ge=5, le=525_600)
    cron_expression: str | None = Field(default=None, max_length=64)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    retry_limit: int = Field(default=2, ge=0, le=10)
    retry_backoff_minutes: int = Field(default=5, ge=1, le=1_440)

    @model_validator(mode="after")
    def validate_schedule(self) -> "OrganizeRuleBase":
        if self.schedule_type == RuleScheduleType.INTERVAL and self.interval_minutes is None:
            raise ValueError("interval_minutes is required for interval schedules")
        if self.schedule_type == RuleScheduleType.CRON:
            fields = (self.cron_expression or "").split()
            if len(fields) != 5:
                raise ValueError("cron_expression must contain five fields")
        return self


class CreateOrganizeRuleRequest(OrganizeRuleBase):
    run_immediately: bool = True


class UpdateOrganizeRuleRequest(OrganizeRuleBase):
    pass


class OrganizeRuleView(ApiModel):
    id: str
    name: str
    enabled: bool
    source_directory_id: str
    source_directory_path: str
    target_directory_id: str
    target_directory_path: str
    config: dict[str, object]
    schedule_type: RuleScheduleType
    interval_minutes: int | None
    cron_expression: str | None
    timezone: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_job_id: str | None
    last_error: str | None
    retry_limit: int
    retry_count: int
    retry_backoff_minutes: int
    created_at: datetime
    updated_at: datetime


class OrganizeRuleRunResult(BaseModel):
    job: JobView
    coalesced: bool = False


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
    provider: MetadataSource | None = None
    provider_id: str | None = None


class MediaGroupUpdateResult(BaseModel):
    group_key: str
    updated_items: int


class UpdateMatchRequest(BaseModel):
    decision: MatchDecision
    candidate_tmdb_id: int | None = None
    provider: MetadataSource | None = None
    provider_id: str | None = None

    @model_validator(mode="after")
    def validate_provider_identity(self) -> "UpdateMatchRequest":
        if (self.provider is None) != (self.provider_id is None):
            raise ValueError("provider and provider_id must be provided together")
        if (
            self.candidate_tmdb_id is not None
            and self.provider is not None
            and (
                self.provider != MetadataSource.TMDB
                or self.provider_id != str(self.candidate_tmdb_id)
            )
        ):
            raise ValueError("legacy and generic candidate identities conflict")
        return self

    def resolved_tmdb_id(self) -> int | None:
        if self.candidate_tmdb_id is not None:
            return self.candidate_tmdb_id
        if self.provider == MetadataSource.TMDB and self.provider_id and self.provider_id.isdigit():
            return int(self.provider_id)
        return None


class MetadataProviderView(BaseModel):
    provider: MetadataSource
    display_name: str
    enabled: bool
    capabilities: dict[str, object]


class BatchMatchApprovalItem(BaseModel):
    match_id: str = Field(min_length=1, max_length=64)
    candidate_tmdb_id: int | None = Field(default=None, gt=0)
    provider: MetadataSource | None = None
    provider_id: str | None = None

    @model_validator(mode="after")
    def validate_candidate_identity(self) -> "BatchMatchApprovalItem":
        if self.candidate_tmdb_id is None and not (
            self.provider == MetadataSource.TMDB
            and self.provider_id
            and self.provider_id.isdigit()
        ):
            raise ValueError("a TMDB candidate identity is required")
        return self

    def resolved_tmdb_id(self) -> int:
        return self.candidate_tmdb_id or int(self.provider_id or "0")


class BatchApproveMatchesRequest(BaseModel):
    items: list[BatchMatchApprovalItem] = Field(
        min_length=1,
        max_length=100,
    )


class BatchApproveMatchesResult(BaseModel):
    updated_items: int


class ManualMatchRequest(BaseModel):
    tmdb_id: int = Field(gt=0)
    title: str = Field(default="", max_length=256)
    original_title: str = Field(default="", max_length=256)
    year: int | None = Field(default=None, ge=1870, le=2100)
    media_type: MediaType
    season_number: int | None = Field(default=None, ge=0, le=99)
    episode_numbers: list[int] = Field(
        default_factory=list,
        max_length=20,
    )


class LocalMetadataGroupRequest(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    year: int | None = Field(default=None, ge=1870, le=2100)
    season_number: int = Field(default=1, ge=0, le=99)


class TmdbSeasonSummary(BaseModel):
    season_number: int
    name: str
    episode_count: int
    poster_url: str | None


class TmdbEpisodeSummary(BaseModel):
    episode_number: int
    name: str
    overview: str
    air_date: date | None
    still_url: str | None


class ManualMatchPreview(BaseModel):
    tmdb_id: int
    title: str
    year: int | None
    media_type: MediaType
    season_number: int | None
    episode_numbers: list[int]
    missing_episode_numbers: list[int]
    target_path: str


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
    tmdb_id: int | None
    metadata_source: MetadataSource = MetadataSource.TMDB
    title: str
    year: int | None
    media_type: MediaType
    poster_url: str | None
    target_path: str
    completed_at: datetime
    file_count: int
    season_count: int
    episode_count: int


class LibraryEpisode(BaseModel):
    id: str
    episode_number: int
    title: str
    overview: str
    air_date: date | None
    still_url: str | None
    source_filename: str
    target_path: str


class LibrarySeason(BaseModel):
    id: str
    season_number: int
    name: str
    overview: str
    poster_url: str | None
    episode_count: int
    episodes: list[LibraryEpisode]


class LibraryItemDetail(LibraryItem):
    overview: str
    backdrop_url: str | None
    seasons: list[LibrarySeason]


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
