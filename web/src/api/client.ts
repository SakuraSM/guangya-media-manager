import type {
  AppSettings,
  CloudDirectory,
  CloudLoginStart,
  CloudLoginStatus,
  CreateJobInput,
  Dashboard,
  Job,
  LibraryItem,
  MatchDecision,
  MediaMatch,
  SourceAction,
  SourceItem,
  SessionState,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface UpdateMatchInput {
  jobId: string
  matchId: string
  decision: MatchDecision
  candidateTmdbId?: number
}

interface UpdateSourceItemInput {
  jobId: string
  itemId: string
  action: SourceAction
}

interface UpdateMediaGroupInput {
  jobId: string
  groupKey: string
  decision: MatchDecision
  candidateTmdbId?: number
}

async function requestJson<ResponseBody>(
  path: string,
  requestInit?: RequestInit,
): Promise<ResponseBody> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...requestInit?.headers,
    },
    ...requestInit,
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const message =
      isErrorPayload(payload) && typeof payload.detail === 'string'
        ? payload.detail
        : `请求失败（${response.status}）`
    throw new ApiError(message, response.status)
  }
  return (await response.json()) as ResponseBody
}

function isErrorPayload(value: unknown): value is { detail: unknown } {
  return typeof value === 'object' && value !== null && 'detail' in value
}

export const api = {
  getSession: () => requestJson<SessionState>('/session'),
  login: (password: string) =>
    requestJson<SessionState>('/session/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
  logout: () => requestJson<SessionState>('/session/logout', { method: 'POST' }),
  getDashboard: () => requestJson<Dashboard>('/dashboard'),
  getJobs: () => requestJson<Job[]>('/jobs'),
  getJob: (jobId: string) => requestJson<Job>(`/jobs/${jobId}`),
  createJob: (input: CreateJobInput) =>
    requestJson<Job>('/jobs', { method: 'POST', body: JSON.stringify(input) }),
  scanJob: (jobId: string) =>
    requestJson<Job>(`/jobs/${jobId}/scan`, { method: 'POST' }),
  executeJob: (jobId: string) =>
    requestJson<Job>(`/jobs/${jobId}/execute`, { method: 'POST' }),
  cancelJob: (jobId: string) =>
    requestJson<Job>(`/jobs/${jobId}/cancel`, { method: 'POST' }),
  getMatches: (jobId: string) =>
    requestJson<MediaMatch[]>(`/jobs/${jobId}/matches`),
  getSourceItems: (jobId: string) =>
    requestJson<SourceItem[]>(`/jobs/${jobId}/items`),
  updateSourceItem: ({ jobId, itemId, action }: UpdateSourceItemInput) =>
    requestJson<SourceItem>(`/jobs/${jobId}/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify({ action }),
    }),
  updateMatch: ({
    jobId,
    matchId,
    decision,
    candidateTmdbId,
  }: UpdateMatchInput) =>
    requestJson<MediaMatch>(`/jobs/${jobId}/matches/${matchId}`, {
      method: 'PUT',
      body: JSON.stringify({
        decision,
        candidate_tmdb_id: candidateTmdbId ?? null,
      }),
    }),
  updateMediaGroup: ({
    jobId,
    groupKey,
    decision,
    candidateTmdbId,
  }: UpdateMediaGroupInput) =>
    requestJson<{ group_key: string; updated_items: number }>(
      `/jobs/${jobId}/groups/${encodeURIComponent(groupKey)}`,
      {
        method: 'PUT',
        body: JSON.stringify({
          decision,
          candidate_tmdb_id: candidateTmdbId ?? null,
        }),
      },
    ),
  getDirectories: (parentId = '', parentPath = '/光鸭云盘') => {
    const query = new URLSearchParams({ parent_id: parentId, parent_path: parentPath })
    return requestJson<CloudDirectory[]>(`/cloud/directories?${query.toString()}`)
  },
  startCloudLogin: () =>
    requestJson<CloudLoginStart>('/cloud/guangya/login/start', { method: 'POST' }),
  pollCloudLogin: (loginId: string) =>
    requestJson<CloudLoginStatus>(`/cloud/guangya/login/${loginId}`),
  getLibrary: () => requestJson<LibraryItem[]>('/library'),
  getSettings: () => requestJson<AppSettings>('/settings'),
  updateSettings: (input: Record<string, string>) =>
    requestJson<AppSettings>('/settings', {
      method: 'PUT',
      body: JSON.stringify(input),
    }),
}
