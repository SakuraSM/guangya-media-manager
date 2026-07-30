import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import type {
  BatchMatchApprovalInput,
  MediaMatch,
} from '../types'
import { isBatchApprovableMatch } from '../utils/reviewGrouping'

interface UseBatchApprovalInput {
  jobId: string
  pageMatches: MediaMatch[]
  activeMatchId: string | null
  activeCandidateId: number | null
  onApproved: (updatedItems: number) => Promise<void>
}

interface UseBatchApprovalResult {
  selectedMatchIds: ReadonlySet<string>
  selectedCount: number
  isPending: boolean
  error: Error | null
  approveSelected: () => void
  clearSelection: () => void
  toggleMatchSelection: (matchId: string) => void
  togglePageSelection: () => void
}

export function useBatchApproval({
  jobId,
  pageMatches,
  activeMatchId,
  activeCandidateId,
  onApproved,
}: UseBatchApprovalInput): UseBatchApprovalResult {
  const [selectedMatchIds, setSelectedMatchIds] = useState<Set<string>>(
    () => new Set(),
  )
  const approvableMatches = useMemo(
    () => pageMatches.filter(isBatchApprovableMatch),
    [pageMatches],
  )
  const selectedApprovals = useMemo(
    () =>
      buildSelectedApprovals({
        approvableMatches,
        selectedMatchIds,
        activeMatchId,
        activeCandidateId,
      }),
    [
      activeCandidateId,
      activeMatchId,
      approvableMatches,
      selectedMatchIds,
    ],
  )
  const mutation = useMutation({
    mutationFn: () =>
      api.batchApproveMatches({
        jobId,
        items: selectedApprovals,
      }),
    onSuccess: async (result) => {
      setSelectedMatchIds(new Set())
      await onApproved(result.updated_items)
    },
  })

  const clearSelection = () => setSelectedMatchIds(new Set())
  const toggleMatchSelection = (matchId: string) => {
    setSelectedMatchIds((currentIds) => {
      const nextIds = new Set(currentIds)
      if (nextIds.has(matchId)) nextIds.delete(matchId)
      else nextIds.add(matchId)
      return nextIds
    })
  }
  const togglePageSelection = () => {
    setSelectedMatchIds((currentIds) => {
      const approvableIds = approvableMatches.map((mediaMatch) => mediaMatch.id)
      const areAllSelected = approvableIds.every((matchId) =>
        currentIds.has(matchId),
      )
      return new Set(areAllSelected ? [] : approvableIds)
    })
  }

  return {
    selectedMatchIds,
    selectedCount: selectedApprovals.length,
    isPending: mutation.isPending,
    error: mutation.error,
    approveSelected: mutation.mutate,
    clearSelection,
    toggleMatchSelection,
    togglePageSelection,
  }
}

interface BuildSelectedApprovalsInput {
  approvableMatches: MediaMatch[]
  selectedMatchIds: ReadonlySet<string>
  activeMatchId: string | null
  activeCandidateId: number | null
}

function buildSelectedApprovals({
  approvableMatches,
  selectedMatchIds,
  activeMatchId,
  activeCandidateId,
}: BuildSelectedApprovalsInput): BatchMatchApprovalInput[] {
  return approvableMatches.flatMap((mediaMatch) => {
    if (!selectedMatchIds.has(mediaMatch.id)) return []
    const candidateTmdbId =
      mediaMatch.id === activeMatchId && activeCandidateId !== null
        ? activeCandidateId
        : mediaMatch.selected_tmdb_id ??
          mediaMatch.candidates[0]?.tmdb_id ??
          null
    return candidateTmdbId === null
      ? []
      : [{ matchId: mediaMatch.id, candidateTmdbId }]
  })
}
