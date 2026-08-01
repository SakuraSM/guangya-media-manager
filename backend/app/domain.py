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


class MetadataSource(StrEnum):
    TMDB = "TMDB"
    LOCAL = "LOCAL"


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
