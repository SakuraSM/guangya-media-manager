export const ACCOUNT_STATUS = {
  CONNECTED: 'CONNECTED',
  REFRESHING: 'REFRESHING',
  EXPIRED: 'EXPIRED',
  REAUTH_REQUIRED: 'REAUTH_REQUIRED',
} as const

export type AccountStatus = (typeof ACCOUNT_STATUS)[keyof typeof ACCOUNT_STATUS]

export const JOB_STATUS = {
  DRAFT: 'DRAFT',
  SCANNING: 'SCANNING',
  IDENTIFYING: 'IDENTIFYING',
  REVIEW_REQUIRED: 'REVIEW_REQUIRED',
  READY: 'READY',
  COPYING: 'COPYING',
  SCRAPING: 'SCRAPING',
  FINALIZING: 'FINALIZING',
  COMPLETED: 'COMPLETED',
  PARTIAL_FAILED: 'PARTIAL_FAILED',
  FAILED: 'FAILED',
  CANCELED: 'CANCELED',
} as const

export type JobStatus = (typeof JOB_STATUS)[keyof typeof JOB_STATUS]

export const MATCH_DECISION = {
  AUTO_APPROVED: 'AUTO_APPROVED',
  APPROVED: 'APPROVED',
  REVIEW: 'REVIEW',
  IGNORED: 'IGNORED',
  UNRESOLVED: 'UNRESOLVED',
} as const

export type MatchDecision = (typeof MATCH_DECISION)[keyof typeof MATCH_DECISION]

export const REVIEW_FILTER = {
  PENDING: 'PENDING',
  REVIEWED: 'REVIEWED',
  ALL: 'ALL',
} as const

export type ReviewFilter = (typeof REVIEW_FILTER)[keyof typeof REVIEW_FILTER]
export type MediaType = 'MOVIE' | 'TV' | 'UNKNOWN'
export type MetadataSource = 'TMDB' | 'LOCAL'
export type LibraryCategory = 'MOVIE' | 'TV' | 'ANIME' | 'DOCUMENTARY' | 'VARIETY'
export type RegionBucket = 'CN' | 'HK_TW' | 'JP_KR' | 'EUROPE_US' | 'OTHER'
export type OutputLayout = 'STANDARD' | 'CLASSIFIED'
export type QualityProfile = 'QUALITY' | 'COMPATIBILITY' | 'SPACE_SAVING'
export type RuleScheduleType = 'MANUAL' | 'INTERVAL' | 'CRON'
export type JobTriggerType = 'MANUAL' | 'SCHEDULED' | 'DIRTY_RETRY' | 'FAILED_RETRY'

export const SOURCE_CLASSIFICATION = {
  MEDIA: 'MEDIA',
  SUBTITLE: 'SUBTITLE',
  EXTRA: 'EXTRA',
  EXISTING_ASSET: 'EXISTING_ASSET',
  IGNORED: 'IGNORED',
  UNKNOWN: 'UNKNOWN',
} as const

export type SourceClassification =
  (typeof SOURCE_CLASSIFICATION)[keyof typeof SOURCE_CLASSIFICATION]
export type SourceAction = 'DEFAULT' | 'INCLUDE' | 'EXCLUDE'
export type OperationStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'SKIPPED'
  | 'FAILED'
export type FileOperationType = 'COPY' | 'MOVE' | 'RENAME' | 'UPLOAD' | 'TRASH'

export type ProgressStage =
  | 'SCAN'
  | 'IDENTIFY'
  | 'AUTO_APPROVE'
  | 'AI_REVIEW'
  | 'AUTO_EXECUTE'
  | 'COPY'
  | 'SCRAPE'
  | 'CLEANUP'
  | 'FINALIZE'

export type ProgressState =
  | 'QUEUED'
  | 'RUNNING'
  | 'WAITING_REVIEW'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELED'

export interface FileOperationProgressSummary {
  state: ProgressState
  completed: number
  total: number
  succeeded: number
  failed: number
  skipped: number
  current_filename?: string
}

export interface JobProgressDetail {
  stage?: ProgressStage
  state?: ProgressState
  completed?: number
  total?: number
  succeeded?: number
  failed?: number
  skipped?: number
  current_group?: string
  current_match_id?: string
  current_operation_type?: FileOperationType
  current_filename?: string
  operations?: Partial<Record<FileOperationType, FileOperationProgressSummary>>
  message?: string
}

export interface JobProgressEvent {
  event_id: number
  type: 'job.updated' | 'match.updated' | 'group.progress' | 'file-operation.updated'
  job_id: string
  scope: 'JOB' | 'MATCH' | 'GROUP' | 'FILE_OPERATION'
  match_id: string | null
  group_key: string | null
  file_operation_id: string | null
  payload: Record<string, unknown>
  job: Job
  created_at: string
}

export interface SessionState {
  is_authenticated: boolean
}

export interface CloudAccount {
  id: string
  display_name: string
  status: AccountStatus
  capacity_bytes: number
  used_bytes: number
}

export interface CloudDirectory {
  id: string
  parent_id: string
  name: string
  path: string
  item_count: number | null
}

export interface CloudLoginStart {
  login_id: string
  verification_uri: string
  expires_in_seconds: number
  poll_interval_seconds: number
}

export interface CloudLoginStatus {
  login_id: string
  status: 'PENDING' | 'CONNECTED' | 'EXPIRED'
  account: CloudAccount | null
  error_message: string | null
}

export interface Job {
  id: string
  name: string
  source_directory_path: string
  target_directory_path: string
  status: JobStatus
  progress: number
  revision: number
  progress_detail: JobProgressDetail
  current_stage: string
  total_items: number
  approved_items: number
  executed_items: number
  review_items: number
  failed_items: number
  copied_bytes: number
  error_message: string | null
  is_cancel_requested: boolean
  auto_approve_enabled: boolean
  auto_execute_after_approval: boolean
  ai_review_running: boolean
  rule_id: string | null
  trigger_type: JobTriggerType
  scanned_directories: number
  skipped_directories: number
  changed_items: number
  created_at: string
  updated_at: string
}

export interface JobPage {
  items: Job[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface MatchCandidate {
  tmdb_id: number
  provider?: MetadataSource
  provider_id?: string | null
  title: string
  original_title: string
  year: number | null
  media_type: MediaType
  score: number
  poster_url: string | null
  backdrop_url: string | null
  overview: string
}

export interface MediaMatch {
  id: string
  source_item_id: string
  filename: string
  source_path: string
  size_bytes: number
  media_type: MediaType
  parsed_title: string
  parsed_year: number | null
  season_number: number | null
  episode_numbers: number[]
  edition: string
  confidence: number
  decision: MatchDecision
  selected_tmdb_id: number | null
  metadata_source?: MetadataSource | null
  metadata_provider?: MetadataSource | null
  provider_id?: string | null
  match_origin?: 'RULE' | 'PATH_ID' | 'NFO' | 'TMDB' | 'AI' | 'LOCAL' | 'MANUAL'
  metadata_hint?: Record<string, unknown>
  decision_reasons?: MatchDecisionReason[]
  candidates: MatchCandidate[]
  target_path: string
  reason_codes: string[]
  group_key: string
  episode_title: string
  episode_date: string | null
  release_info: {
    quality_tags?: string[]
    release_group?: string
    part_number?: number | null
  }
  library_category: LibraryCategory
  region_bucket: RegionBucket
  classification_reasons: Array<Record<string, unknown>>
  quality_profile: {
    resolution?: string
    source?: string
    hdr?: string
    codec?: string
    audio?: string
    size_bytes?: number
    preference?: QualityProfile
    recommended?: boolean
    selected?: boolean
    selection_mode?: 'SINGLE' | 'AUTO' | 'MANUAL_OVERRIDE'
    selection_rank?: number
    selection_keep_count?: number
    recommendation_reason?: string
    score_reason?: string
  }
  version_group_key: string
  version_score: number
  version_recommendation: 'SINGLE' | 'PENDING' | 'CONFIRMED' | 'NOT_SELECTED'
  execution_status?: OperationStatus | null
  execution_error?: string | null
  cleanup_status?: OperationStatus | null
  cleanup_error?: string | null
}

export interface MatchDecisionReason {
  code: string
  message: string
  severity: 'INFO' | 'WARNING' | 'BLOCKING'
  overridable: boolean
  origin: string
}

export interface MetadataProviderInfo {
  provider: MetadataSource
  display_name: string
  enabled: boolean
  capabilities: {
    search: boolean
    external_identity: boolean
    episode_details: boolean
    languages: string[]
  }
}

export interface MediaMatchPage {
  items: MediaMatch[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ManualMatchInput {
  tmdbId: number
  title: string
  originalTitle: string
  year: number | null
  mediaType: MediaType
  seasonNumber: number | null
  episodeNumbers: number[]
}

export interface LocalMetadataGroupInput {
  title: string
  year: number | null
  seasonNumber: number
}

export interface TmdbSeasonSummary {
  season_number: number
  name: string
  episode_count: number
  poster_url: string | null
}

export interface TmdbEpisodeSummary {
  episode_number: number
  name: string
  overview: string
  air_date: string | null
  still_url: string | null
}

export interface ManualMatchPreview {
  tmdb_id: number
  title: string
  year: number | null
  media_type: MediaType
  season_number: number | null
  episode_numbers: number[]
  missing_episode_numbers: number[]
  target_path: string
}

export interface BatchMatchApprovalInput {
  matchId: string
  candidateTmdbId: number
}

export interface BatchApprovalResult {
  updated_items: number
}

export interface SourceItem {
  id: string
  filename: string
  source_path: string
  relative_path: string
  size_bytes: number
  classification: SourceClassification
  filter_reason: string
  user_action: SourceAction
  group_key: string
  is_reviewable: boolean
}

export interface Dashboard {
  account: CloudAccount | null
  metrics: {
    pending_review: number
    completed_today: number
    failed: number
    copied_bytes: number
  }
  active_job: Job | null
  recent_jobs: Job[]
  recent_events: AuditEvent[]
}

export interface AuditEvent {
  id: string
  event_type: string
  message: string
  severity: string
  created_at: string
}

export interface LibraryItem {
  id: string
  tmdb_id: number | null
  metadata_source?: MetadataSource
  title: string
  year: number | null
  media_type: MediaType
  poster_url: string | null
  target_path: string
  completed_at: string
  file_count: number
  season_count: number
  episode_count: number
}

export interface LibraryEpisode {
  id: string
  episode_number: number
  title: string
  overview: string
  air_date: string | null
  still_url: string | null
  source_filename: string
  target_path: string
}

export interface LibrarySeason {
  id: string
  season_number: number
  name: string
  overview: string
  poster_url: string | null
  episode_count: number
  episodes: LibraryEpisode[]
}

export interface LibraryItemDetail extends LibraryItem {
  overview: string
  backdrop_url: string | null
  seasons: LibrarySeason[]
}

export interface AppSettings {
  demo_mode: boolean
  tmdb_configured: boolean
  ai_configured: boolean
  ai_base_url: string
  ai_model: string
  auto_approve_threshold: number
  review_threshold: number
}

export interface OrganizeConfig {
    generate_nfo: boolean
    download_poster: boolean
    download_fanart: boolean
    download_backdrop_alias: boolean
    download_season_poster: boolean
    download_episode_thumb: boolean
    season_artwork_compat: boolean
    scrape_metadata_language: 'zh-CN' | 'en-US' | 'ja-JP' | 'ko-KR'
    scrape_image_quality: 'STANDARD' | 'ORIGINAL'
    rename_subtitles: boolean
    auto_approve_threshold: number
    review_threshold: number
    auto_approve_enabled: boolean
    auto_execute_after_approval: boolean
    naming_profile: 'UNIVERSAL_ENHANCED'
    extras_policy: 'EXCLUDE_REVIEWABLE' | 'INCLUDE'
    sample_max_mb: number
    exclude_globs: string[]
    title_extraction_regex: string
    include_paths: string[]
    output_layout: OutputLayout
    include_region_directory: boolean
    quality_profile: QualityProfile
    version_keep_count: number
    trash_organized_source_files: boolean
    trash_ignored_source_files: boolean
}

export interface CreateJobInput {
  name: string
  source_directory_id: string
  source_directory_path: string
  target_directory_id: string
  target_directory_path: string
  config: OrganizeConfig
}

export interface OrganizeRule {
  id: string
  name: string
  enabled: boolean
  source_directory_id: string
  source_directory_path: string
  target_directory_id: string
  target_directory_path: string
  config: OrganizeConfig
  schedule_type: RuleScheduleType
  interval_minutes: number | null
  cron_expression: string | null
  timezone: string
  next_run_at: string | null
  last_run_at: string | null
  last_job_id: string | null
  last_error: string | null
  retry_limit: number
  retry_count: number
  retry_backoff_minutes: number
  created_at: string
  updated_at: string
}

export interface CreateOrganizeRuleInput {
  name: string
  enabled: boolean
  source_directory_id: string
  source_directory_path: string
  target_directory_id: string
  target_directory_path: string
  config: OrganizeConfig
  schedule_type: RuleScheduleType
  interval_minutes: number | null
  cron_expression: string | null
  timezone: string
  retry_limit: number
  retry_backoff_minutes: number
  run_immediately?: boolean
}
