import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Job, MediaMatchPage, SourceItem } from '../types'

const REVIEW_REFETCH_INTERVAL_MS = 4_000

interface UseReviewQueriesInput {
  page: number
  pageSize: number
}

interface UseReviewQueriesResult {
  selectedJobId: string
  jobsQuery: UseQueryResult<Job[], Error>
  matchesQuery: UseQueryResult<MediaMatchPage, Error>
  jobQuery: UseQueryResult<Job, Error>
  sourceItemsQuery: UseQueryResult<SourceItem[], Error>
}

export function useReviewQueries({
  page,
  pageSize,
}: UseReviewQueriesInput): UseReviewQueriesResult {
  const jobsQuery = useQuery({ queryKey: ['jobs'], queryFn: api.getJobs })
  const searchParams = new URLSearchParams(window.location.search)
  const selectedJobId =
    searchParams.get('job') ?? jobsQuery.data?.[0]?.id ?? ''
  const matchesQuery = useQuery({
    queryKey: ['matches', selectedJobId, page, pageSize],
    queryFn: () => api.getMatches({ jobId: selectedJobId, page, pageSize }),
    enabled: Boolean(selectedJobId),
    refetchInterval: REVIEW_REFETCH_INTERVAL_MS,
  })
  const jobQuery = useQuery({
    queryKey: ['job', selectedJobId],
    queryFn: () => api.getJob(selectedJobId),
    enabled: Boolean(selectedJobId),
    refetchInterval: REVIEW_REFETCH_INTERVAL_MS,
  })
  const sourceItemsQuery = useQuery({
    queryKey: ['source-items', selectedJobId, jobQuery.data?.status],
    queryFn: () => api.getSourceItems(selectedJobId),
    enabled: Boolean(selectedJobId) && jobQuery.isSuccess,
    placeholderData: (previousItems) => previousItems,
    staleTime: 30_000,
  })
  return {
    selectedJobId,
    jobsQuery,
    matchesQuery,
    jobQuery,
    sourceItemsQuery,
  }
}
