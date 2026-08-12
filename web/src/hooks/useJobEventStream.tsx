import { useEffect, useState, type ReactNode } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import {
  MATCH_DECISION,
  REVIEW_FILTER,
  type Dashboard,
  type Job,
  type JobPage,
  type JobProgressEvent,
  type MatchDecision,
  type MediaMatch,
  type MediaMatchPage,
  type OperationStatus,
  type ReviewFilter,
} from '@/types'

import {
  JobEventStreamContext,
  type EventStreamState,
  type JobEventStreamValue,
} from './jobEventStreamContext'

export type { EventStreamState } from './jobEventStreamContext'

export function JobEventStreamProvider({ children }: { children: ReactNode }) {
  const eventStream = useJobEventStreamConnection()
  return (
    <JobEventStreamContext.Provider value={eventStream}>
      {children}
    </JobEventStreamContext.Provider>
  )
}

function useJobEventStreamConnection(): JobEventStreamValue {
  const queryClient = useQueryClient()
  const [connectionState, setConnectionState] = useState<EventStreamState>('CONNECTING')
  const [latestEvent, setLatestEvent] = useState<JobProgressEvent | null>(null)

  useEffect(() => {
    const eventSource = new EventSource('/api/events/jobs', { withCredentials: true })
    eventSource.onopen = () => setConnectionState('CONNECTED')
    eventSource.addEventListener('sync', () => {
      setConnectionState('CONNECTED')
      void refreshRealtimeQueries(queryClient)
    })
    eventSource.addEventListener('progress', (message) => {
      const progressEvent = parseProgressEvent(message)
      if (!progressEvent) return
      setConnectionState('CONNECTED')
      setLatestEvent(progressEvent)
      applyProgressEvent(queryClient, progressEvent)
    })
    eventSource.onerror = () => setConnectionState('DISCONNECTED')
    return () => {
      eventSource.close()
    }
  }, [queryClient])

  return { connectionState, latestEvent }
}

function parseProgressEvent(message: Event): JobProgressEvent | null {
  if (!(message instanceof MessageEvent) || typeof message.data !== 'string') return null
  try {
    const value: unknown = JSON.parse(message.data)
    if (!isProgressEvent(value)) return null
    return value
  } catch {
    return null
  }
}

function isProgressEvent(value: unknown): value is JobProgressEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    'event_id' in value &&
    'type' in value &&
    'job_id' in value &&
    'job' in value
  )
}

function applyProgressEvent(queryClient: QueryClient, event: JobProgressEvent): void {
  queryClient.setQueryData<Job>(['job', event.job_id], event.job)
  queryClient.setQueriesData<Job[]>({ queryKey: ['jobs'], exact: true }, (jobs) =>
    jobs?.map((job) => (job.id === event.job_id ? event.job : job)),
  )
  queryClient.setQueriesData<JobPage>({ queryKey: ['jobs', 'page'] }, (page) =>
    page
      ? { ...page, items: page.items.map((job) => (job.id === event.job_id ? event.job : job)) }
      : page,
  )
  queryClient.setQueryData<Dashboard>(['dashboard'], (dashboard) => {
    if (!dashboard) return dashboard
    return {
      ...dashboard,
      active_job: dashboard.active_job?.id === event.job_id ? event.job : dashboard.active_job,
      metrics: {
        ...dashboard.metrics,
        pending_review: event.job.review_items,
      },
      recent_jobs: dashboard.recent_jobs.map((job) =>
        job.id === event.job_id ? event.job : job,
      ),
    }
  })
  if (event.type === 'match.updated') {
    const didPatchMatch = patchMatchQueries(queryClient, event)
    if (!didPatchMatch) {
      void queryClient.invalidateQueries({ queryKey: ['matches', event.job_id] })
    }
  }
  if (event.type === 'file-operation.updated') {
    const didPatchOperation = patchOperationQueries(queryClient, event)
    if (!didPatchOperation) {
      void queryClient.invalidateQueries({ queryKey: ['matches', event.job_id] })
    }
  }
}

function patchMatchQueries(queryClient: QueryClient, event: JobProgressEvent): boolean {
  if (!event.match_id) return false
  const decision = readMatchDecision(event.payload.decision)
  let didPatch = false
  for (const [queryKey, matchPage] of queryClient.getQueriesData<MediaMatchPage>({
    queryKey: ['matches', event.job_id],
  })) {
    if (!matchPage) continue
    const reviewFilter = readReviewFilter(queryKey[4])
    const currentMatch = matchPage.items.find((item) => item.id === event.match_id)
    if (!currentMatch) continue
    didPatch = true
    const updatedMatch: MediaMatch = {
      ...currentMatch,
      decision: decision ?? currentMatch.decision,
      confidence: readNumber(event.payload.confidence) ?? currentMatch.confidence,
      reason_codes: readStringArray(event.payload.reason_codes) ?? currentMatch.reason_codes,
      match_origin: readMatchOrigin(event.payload.match_origin) ?? currentMatch.match_origin,
    }
    const shouldRemain = matchesReviewFilter(updatedMatch.decision, reviewFilter)
    const items = shouldRemain
      ? matchPage.items.map((item) => (item.id === updatedMatch.id ? updatedMatch : item))
      : matchPage.items.filter((item) => item.id !== updatedMatch.id)
    const total = shouldRemain ? matchPage.total : Math.max(0, matchPage.total - 1)
    queryClient.setQueryData<MediaMatchPage>(queryKey, {
      ...matchPage,
      items,
      total,
      pages: Math.ceil(total / matchPage.page_size),
    })
  }
  return didPatch
}

function patchOperationQueries(queryClient: QueryClient, event: JobProgressEvent): boolean {
  const sourceItemId = readString(event.payload.source_item_id)
  const executionStatus = readOperationStatus(event.payload.status)
  if (!sourceItemId || !executionStatus) return false
  let didPatch = false
  for (const [queryKey, matchPage] of queryClient.getQueriesData<MediaMatchPage>({
    queryKey: ['matches', event.job_id],
  })) {
    if (!matchPage?.items.some((item) => item.source_item_id === sourceItemId)) continue
    didPatch = true
    queryClient.setQueryData<MediaMatchPage>(queryKey, {
      ...matchPage,
      items: matchPage.items.map((item) =>
        item.source_item_id === sourceItemId
          ? {
              ...item,
              execution_status: executionStatus,
              execution_error: readString(event.payload.error_message),
            }
          : item,
      ),
    })
  }
  return didPatch
}

function readReviewFilter(value: unknown): ReviewFilter {
  return value === REVIEW_FILTER.PENDING || value === REVIEW_FILTER.REVIEWED
    ? value
    : REVIEW_FILTER.ALL
}

function matchesReviewFilter(decision: MatchDecision, reviewFilter: ReviewFilter): boolean {
  const isPending = decision === MATCH_DECISION.REVIEW || decision === MATCH_DECISION.UNRESOLVED
  if (reviewFilter === REVIEW_FILTER.PENDING) return isPending
  if (reviewFilter === REVIEW_FILTER.REVIEWED) return !isPending
  return true
}

function readMatchDecision(value: unknown): MatchDecision | null {
  return Object.values(MATCH_DECISION).includes(value as MatchDecision)
    ? (value as MatchDecision)
    : null
}

function readOperationStatus(value: unknown): OperationStatus | null {
  return value === 'PENDING' || value === 'RUNNING' || value === 'COMPLETED' ||
    value === 'SKIPPED' || value === 'FAILED'
    ? value
    : null
}

function readMatchOrigin(value: unknown): MediaMatch['match_origin'] | null {
  return value === 'RULE' || value === 'PATH_ID' || value === 'NFO' ||
    value === 'TMDB' || value === 'AI' || value === 'LOCAL' ||
    value === 'MANUAL'
    ? value
    : null
}

function readString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function readNumber(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

function readStringArray(value: unknown): string[] | null {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
    ? value
    : null
}

async function refreshRealtimeQueries(
  queryClient: QueryClient,
): Promise<void> {
  const refreshes = [
    queryClient.invalidateQueries({ queryKey: ['jobs'] }),
    queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
  ]
  await Promise.all(refreshes)
}
