from enum import StrEnum


class AccountStatus(StrEnum):
    CONNECTED = "CONNECTED"
    REFRESHING = "REFRESHING"
    EXPIRED = "EXPIRED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"


class JobStatus(StrEnum):
    DRAFT = "DRAFT"
    SCANNING = "SCANNING"
    IDENTIFYING = "IDENTIFYING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY = "READY"
    COPYING = "COPYING"
    SCRAPING = "SCRAPING"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class MediaType(StrEnum):
    MOVIE = "MOVIE"
    TV = "TV"
    UNKNOWN = "UNKNOWN"


class LibraryCategory(StrEnum):
    MOVIE = "MOVIE"
    TV = "TV"
    ANIME = "ANIME"
    DOCUMENTARY = "DOCUMENTARY"
    VARIETY = "VARIETY"


class RegionBucket(StrEnum):
    CN = "CN"
    HK_TW = "HK_TW"
    JP_KR = "JP_KR"
    EUROPE_US = "EUROPE_US"
    OTHER = "OTHER"


class OutputLayout(StrEnum):
    STANDARD = "STANDARD"
    CLASSIFIED = "CLASSIFIED"


class QualityProfile(StrEnum):
    QUALITY = "QUALITY"
    COMPATIBILITY = "COMPATIBILITY"
    SPACE_SAVING = "SPACE_SAVING"


class VersionRecommendationStatus(StrEnum):
    SINGLE = "SINGLE"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    NOT_SELECTED = "NOT_SELECTED"


class RuleScheduleType(StrEnum):
    MANUAL = "MANUAL"
    INTERVAL = "INTERVAL"
    CRON = "CRON"


class JobTriggerType(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    DIRTY_RETRY = "DIRTY_RETRY"
    FAILED_RETRY = "FAILED_RETRY"


class MetadataSource(StrEnum):
    TMDB = "TMDB"
    LOCAL = "LOCAL"


class MatchOrigin(StrEnum):
    RULE = "RULE"
    PATH_ID = "PATH_ID"
    NFO = "NFO"
    TMDB = "TMDB"
    AI = "AI"
    LOCAL = "LOCAL"
    MANUAL = "MANUAL"


class SourceClassification(StrEnum):
    MEDIA = "MEDIA"
    SUBTITLE = "SUBTITLE"
    EXTRA = "EXTRA"
    EXISTING_ASSET = "EXISTING_ASSET"
    IGNORED = "IGNORED"
    UNKNOWN = "UNKNOWN"


class SourceAction(StrEnum):
    DEFAULT = "DEFAULT"
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"


class MatchDecision(StrEnum):
    AUTO_APPROVED = "AUTO_APPROVED"
    APPROVED = "APPROVED"
    REVIEW = "REVIEW"
    IGNORED = "IGNORED"
    UNRESOLVED = "UNRESOLVED"


class MatchReviewState(StrEnum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"


class OperationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class OperationType(StrEnum):
    COPY = "COPY"
    MOVE = "MOVE"
    RENAME = "RENAME"
    UPLOAD = "UPLOAD"
    TRASH = "TRASH"


class ProgressStage(StrEnum):
    SCAN = "SCAN"
    IDENTIFY = "IDENTIFY"
    AUTO_APPROVE = "AUTO_APPROVE"
    AI_REVIEW = "AI_REVIEW"
    AUTO_EXECUTE = "AUTO_EXECUTE"
    COPY = "COPY"
    SCRAPE = "SCRAPE"
    CLEANUP = "CLEANUP"
    FINALIZE = "FINALIZE"


class ProgressState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_REVIEW = "WAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
