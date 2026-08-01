import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ErrorNotice } from '../components/ErrorNotice'
import { LoadingScreen } from '../components/LoadingScreen'
import { ReviewPageHeader } from '../components/ReviewPageHeader'
import { ReviewWorkspace } from '../components/ReviewWorkspace'
import { ScanSummaryPanel } from '../components/ScanSummaryPanel'
import { useBatchApproval } from '../hooks/useBatchApproval'
import { useReviewQueries } from '../hooks/useReviewQueries'
import {
  JOB_STATUS, MATCH_DECISION, REVIEW_FILTER, type ManualMatchInput,
  type MatchDecision, type MediaMatch, type ReviewFilter, type SourceAction,
} from '../types'
import { groupMediaMatches, isEditableJobStatus, isReviewDecision } from '../utils/reviewGrouping'
const DEFAULT_PAGE_SIZE = 20
export function ReviewPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>(
    REVIEW_FILTER.PENDING,
  )
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null)
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const {
    selectedJobId,
    jobsQuery,
    matchesQuery,
    jobQuery,
    sourceItemsQuery,
  } = useReviewQueries({
    page,
    pageSize,
    reviewFilter,
  })
  const selectedMatch = useMemo(() => {
    const pageMatches = matchesQuery.data?.items ?? []
    return (
      pageMatches.find((item) => item.id === selectedMatchId) ??
      pageMatches.find((item) => isReviewDecision(item.decision)) ??
      pageMatches[0] ??
      null
    )
  }, [matchesQuery.data?.items, selectedMatchId])
  const effectiveCandidateId =
    selectedCandidateId ??
    selectedMatch?.selected_tmdb_id ??
    selectedMatch?.candidates[0]?.tmdb_id ??
    null
  const refreshReviewData = async () => {
    await queryClient.invalidateQueries({ queryKey: ['matches', selectedJobId] })
    await queryClient.invalidateQueries({ queryKey: ['job', selectedJobId] })
    await queryClient.invalidateQueries({ queryKey: ['jobs'] })
    await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }
  const batchApproval = useBatchApproval({
    jobId: selectedJobId,
    pageMatches: matchesQuery.data?.items ?? [],
    activeMatchId: selectedMatch?.id ?? null,
    activeCandidateId: effectiveCandidateId,
    onApproved: async (updatedItems) => {
      setActionMessage(`已批量批准 ${updatedItems} 条匹配记录。`)
      await refreshReviewData()
    },
  })
  const updateMutation = useMutation({
    mutationFn: ({
      match,
      decision,
      candidateId,
    }: {
      match: MediaMatch
      decision: MatchDecision
      candidateId?: number
    }) =>
      api.updateMatch({
        jobId: selectedJobId,
        matchId: match.id,
        decision,
        candidateTmdbId: candidateId,
      }),
    onSuccess: async (updatedMatch) => {
      setActionMessage(
        updatedMatch.decision === MATCH_DECISION.IGNORED
          ? '已忽略当前文件，并自动定位下一条待审核项。'
          : '匹配结果已保存。',
      )
      setSelectedMatchId(null)
      setSelectedCandidateId(null)
      await refreshReviewData()
    },
  })
  const retryMutation = useMutation({
    mutationFn: (matchId: string) =>
      api.retryMatch({ jobId: selectedJobId, matchId }),
    onSuccess: async (updatedMatch) => {
      setSelectedMatchId(updatedMatch.id)
      setSelectedCandidateId(
        updatedMatch.selected_tmdb_id ?? updatedMatch.candidates[0]?.tmdb_id ?? null,
      )
      setActionMessage(
        updatedMatch.candidates.length
          ? '当前文件重试完成，请检查新的候选结果。'
          : '重试完成但仍未找到候选，可使用手动匹配。',
      )
      await refreshReviewData()
    },
  })
  const groupRetryMutation = useMutation({
    mutationFn: (groupKey: string) =>
      api.retryMediaGroup(selectedJobId, groupKey),
    onSuccess: async (result) => {
      setActionMessage(`影视分组重试完成，共更新 ${result.updated_items} 条记录。`)
      setSelectedCandidateId(null)
      await refreshReviewData()
    },
  })
  const manualMatchMutation = useMutation({
    mutationFn: ({ matchId, match }: { matchId: string; match: ManualMatchInput }) =>
      api.assignManualMatch({ jobId: selectedJobId, matchId, match }),
    onSuccess: async () => {
      setActionMessage('手动匹配已保存并采用。')
      setSelectedMatchId(null)
      setSelectedCandidateId(null)
      await refreshReviewData()
    },
  })
  const manualGroupMatchMutation = useMutation({
    mutationFn: ({ matchId, match }: { matchId: string; match: ManualMatchInput }) =>
      api.assignManualGroupMatch({ jobId: selectedJobId, matchId, match }),
    onSuccess: async (result) => {
      setActionMessage(
        `剧名和 TMDB 匹配已应用到整个剧集，共更新 ${result.updated_items} 条记录。`,
      )
      setSelectedMatchId(null)
      setSelectedCandidateId(null)
      await refreshReviewData()
    },
  })
  const executeMutation = useMutation({
    mutationFn: () => api.executeJob(selectedJobId),
    onSuccess: async (job) => {
      setActionMessage(
        job.status === JOB_STATUS.PARTIAL_FAILED
          ? '已提交整批重试，将自动跳过已完成文件。'
          : '审核计划已冻结，整批复制任务已提交。',
      )
      await refreshReviewData()
    },
  })
  const cancelMutation = useMutation({
    mutationFn: () => api.cancelJob(selectedJobId),
    onSuccess: async (job) => {
      setActionMessage(
        job.status === JOB_STATUS.CANCELED
          ? '任务已取消，未执行后续操作。'
          : '已请求安全取消，当前文件处理结束后停止。',
      )
      await refreshReviewData()
    },
  })
  const aiReviewMutation = useMutation({
    mutationFn: () => api.startAiReview(selectedJobId),
    onSuccess: async () => {
      setActionMessage(
        'AI 作品级审核已开始；只核对目录、文件名与影视名称和类型，不判断单集序号。',
      )
      await refreshReviewData()
    },
  })
  const groupUpdateMutation = useMutation({
    mutationFn: () => {
      if (!selectedMatch || effectiveCandidateId === null) {
        throw new Error('当前分组没有可批准的 TMDB 候选')
      }
      return api.updateMediaGroup({
        jobId: selectedJobId,
        groupKey: selectedMatch.group_key,
        decision: MATCH_DECISION.APPROVED,
        candidateTmdbId: effectiveCandidateId,
      })
    },
    onSuccess: async () => {
      setActionMessage('当前影视分组已批量批准。')
      await refreshReviewData()
    },
  })
  const sourceItemMutation = useMutation({
    mutationFn: ({ itemId, action }: { itemId: string; action: SourceAction }) =>
      api.updateSourceItem({ jobId: selectedJobId, itemId, action }),
    onSuccess: async () => {
      setActionMessage('扫描项处理策略已更新，任务正在重新扫描。')
      await queryClient.invalidateQueries({
        queryKey: ['source-items', selectedJobId],
      })
    },
  })
  if (
    jobsQuery.isPending ||
    matchesQuery.isPending ||
    jobQuery.isPending ||
    sourceItemsQuery.isPending
  ) {
    return <LoadingScreen label="正在加载匹配审核" />
  }
  const queryError =
    jobsQuery.error ?? matchesQuery.error ?? jobQuery.error ?? sourceItemsQuery.error
  if (queryError) return <ErrorNotice message={queryError.message} />
  if (
    !jobsQuery.data ||
    !matchesQuery.data ||
    !jobQuery.data ||
    !sourceItemsQuery.data
  ) {
    return <ErrorNotice message="审核数据不完整，请刷新后重试" />
  }

  const job = jobQuery.data
  const matchPage = matchesQuery.data
  const matchGroups = groupMediaMatches(matchPage.items)
  const isJobEditable = isEditableJobStatus(job.status) && !job.ai_review_running
  const mutationError = [
    updateMutation.error,
    retryMutation.error,
    groupRetryMutation.error,
    manualMatchMutation.error,
    manualGroupMatchMutation.error,
    executeMutation.error,
    cancelMutation.error,
    aiReviewMutation.error,
    groupUpdateMutation.error,
    sourceItemMutation.error,
    batchApproval.error,
  ].find((error) => error !== null)

  const handleSelectMatch = (mediaMatch: MediaMatch) => {
    setSelectedMatchId(mediaMatch.id)
    setSelectedCandidateId(
      mediaMatch.selected_tmdb_id ?? mediaMatch.candidates[0]?.tmdb_id ?? null,
    )
  }
  const handlePageChange = (nextPage: number) => {
    setPage(nextPage)
    batchApproval.clearSelection()
    setSelectedMatchId(null)
    setSelectedCandidateId(null)
  }
  const handlePageSizeChange = (nextPageSize: number) => {
    setPageSize(nextPageSize)
    handlePageChange(1)
  }
  const handleReviewFilterChange = (nextFilter: ReviewFilter) => {
    setReviewFilter(nextFilter)
    handlePageChange(1)
  }
  const handleApprove = () => {
    if (!selectedMatch || effectiveCandidateId === null) return
    updateMutation.mutate({
      match: selectedMatch,
      decision: MATCH_DECISION.APPROVED,
      candidateId: effectiveCandidateId,
    })
  }
  const handleToggleIgnore = () => {
    if (!selectedMatch) return
    updateMutation.mutate({
      match: selectedMatch,
      decision:
        selectedMatch.decision === MATCH_DECISION.IGNORED
          ? MATCH_DECISION.REVIEW
          : MATCH_DECISION.IGNORED,
    })
  }
  const handleRetry = () => {
    if (selectedMatch) retryMutation.mutate(selectedMatch.id)
  }
  const handleRetryGroup = () => {
    if (selectedMatch) groupRetryMutation.mutate(selectedMatch.group_key)
  }
  const handleManualMatch = (match: ManualMatchInput) => {
    if (selectedMatch) {
      manualMatchMutation.mutate({ matchId: selectedMatch.id, match })
    }
  }
  const handleManualGroupMatch = (match: ManualMatchInput) => {
    if (selectedMatch) {
      manualGroupMatchMutation.mutate({ matchId: selectedMatch.id, match })
    }
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 lg:h-[calc(100svh-7rem)] lg:overflow-hidden">
      <ReviewPageHeader
        jobs={jobsQuery.data}
        job={job}
        selectedJobId={selectedJobId}
        canApproveGroup={
          isJobEditable &&
          Boolean(selectedMatch?.group_key) &&
          effectiveCandidateId !== null
        }
        canApproveSelection={
          isJobEditable && batchApproval.selectedCount > 0
        }
        selectedCount={batchApproval.selectedCount}
        isApprovingGroup={groupUpdateMutation.isPending}
        isApprovingSelection={batchApproval.isPending}
        isExecuting={executeMutation.isPending}
        isCancelling={cancelMutation.isPending}
        canStartAiReview={isJobEditable && job.review_items > 0}
        isStartingAiReview={aiReviewMutation.isPending || job.ai_review_running}
        actionMessage={actionMessage}
        onApproveGroup={() => groupUpdateMutation.mutate()}
        onApproveSelection={batchApproval.approveSelected}
        onExecute={() => executeMutation.mutate()}
        onCancel={() => cancelMutation.mutate()}
        onStartAiReview={() => aiReviewMutation.mutate()}
      />
      <ScanSummaryPanel
        items={sourceItemsQuery.data}
        isSaving={sourceItemMutation.isPending || !isJobEditable}
        onChangeAction={(itemId, action) =>
          sourceItemMutation.mutate({ itemId, action })
        }
      />
      {mutationError ? <ErrorNotice message={mutationError.message} /> : null}
      <ReviewWorkspace
        jobId={selectedJobId}
        matchGroups={matchGroups}
        matchPage={matchPage}
        selectedMatch={selectedMatch}
        selectedMatchIds={batchApproval.selectedMatchIds}
        isSelectionEnabled={isJobEditable && !batchApproval.isPending}
        reviewFilter={reviewFilter}
        selectedCandidateId={effectiveCandidateId}
        isFetching={matchesQuery.isFetching}
        isSaving={
          updateMutation.isPending ||
          manualMatchMutation.isPending ||
          manualGroupMatchMutation.isPending ||
          batchApproval.isPending ||
          !isJobEditable
        }
        isRetrying={retryMutation.isPending}
        isRetryingGroup={groupRetryMutation.isPending}
        onSelectMatch={handleSelectMatch}
        onToggleMatchSelection={batchApproval.toggleMatchSelection}
        onTogglePageSelection={batchApproval.togglePageSelection}
        onReviewFilterChange={handleReviewFilterChange}
        onSelectCandidate={setSelectedCandidateId}
        onApprove={handleApprove}
        onToggleIgnore={handleToggleIgnore}
        onRetry={handleRetry}
        onRetryGroup={handleRetryGroup}
        onManualMatch={handleManualMatch}
        onManualGroupMatch={handleManualGroupMatch}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  )
}
