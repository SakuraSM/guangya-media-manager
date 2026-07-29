import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleSlash, Play, Search, TriangleAlert } from 'lucide-react'
import { api } from '../api/client'
import { ErrorNotice } from '../components/ErrorNotice'
import { GroupedMatchTable } from '../components/GroupedMatchTable'
import { LoadingScreen } from '../components/LoadingScreen'
import { MatchInspector } from '../components/MatchInspector'
import { ScanSummaryPanel } from '../components/ScanSummaryPanel'
import {
  JOB_STATUS,
  MATCH_DECISION,
  type MatchDecision,
  type MediaMatch,
} from '../types'
import { formatBytes } from '../utils/format'
import { episodeLabel, groupMediaMatches } from '../utils/reviewGrouping'

export function ReviewPage() {
  const searchParams = new URLSearchParams(window.location.search)
  const queryClient = useQueryClient()
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null)
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null)
  const jobsQuery = useQuery({ queryKey: ['jobs'], queryFn: api.getJobs })
  const selectedJobId = searchParams.get('job') ?? jobsQuery.data?.[0]?.id ?? ''
  const matchesQuery = useQuery({
    queryKey: ['matches', selectedJobId],
    queryFn: () => api.getMatches(selectedJobId),
    enabled: Boolean(selectedJobId),
    refetchInterval: 4_000,
  })
  const jobQuery = useQuery({
    queryKey: ['job', selectedJobId],
    queryFn: () => api.getJob(selectedJobId),
    enabled: Boolean(selectedJobId),
    refetchInterval: 4_000,
  })
  const sourceItemsQuery = useQuery({
    queryKey: ['source-items', selectedJobId],
    queryFn: () => api.getSourceItems(selectedJobId),
    enabled: Boolean(selectedJobId),
    refetchInterval: 4_000,
  })
  const selectedMatch = useMemo(
    () =>
      matchesQuery.data?.find((item) => item.id === selectedMatchId) ??
      matchesQuery.data?.find((item) => isReviewDecision(item.decision)) ??
      matchesQuery.data?.[0] ??
      null,
    [matchesQuery.data, selectedMatchId],
  )
  const effectiveCandidateId =
    selectedCandidateId ??
    selectedMatch?.selected_tmdb_id ??
    selectedMatch?.candidates[0]?.tmdb_id ??
    null

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
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['matches', selectedJobId] })
      await queryClient.invalidateQueries({ queryKey: ['job', selectedJobId] })
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const executeMutation = useMutation({
    mutationFn: () => api.executeJob(selectedJobId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['job', selectedJobId] })
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
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
      await queryClient.invalidateQueries({ queryKey: ['matches', selectedJobId] })
      await queryClient.invalidateQueries({ queryKey: ['job', selectedJobId] })
    },
  })
  const sourceItemMutation = useMutation({
    mutationFn: ({
      itemId,
      action,
    }: {
      itemId: string
      action: 'DEFAULT' | 'INCLUDE' | 'EXCLUDE'
    }) => api.updateSourceItem({ jobId: selectedJobId, itemId, action }),
    onSuccess: async () => {
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
  if (
    jobsQuery.isError ||
    matchesQuery.isError ||
    jobQuery.isError ||
    sourceItemsQuery.isError
  ) {
    const error =
      jobsQuery.error ?? matchesQuery.error ?? jobQuery.error ?? sourceItemsQuery.error
    return <ErrorNotice message={error?.message ?? '审核数据加载失败'} />
  }

  const matches = matchesQuery.data ?? []
  const matchGroups = groupMediaMatches(matches)
  const job = jobQuery.data
  const reviewCount = matches.filter((item) => isReviewDecision(item.decision)).length

  const handleJobChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    window.location.assign(`/review?job=${encodeURIComponent(event.target.value)}`)
  }
  const handleSelectMatch = (mediaMatch: MediaMatch) => {
    setSelectedMatchId(mediaMatch.id)
    setSelectedCandidateId(
      mediaMatch.selected_tmdb_id ?? mediaMatch.candidates[0]?.tmdb_id ?? null,
    )
  }
  const handleApprove = () => {
    if (!selectedMatch || effectiveCandidateId === null) return
    updateMutation.mutate({
      match: selectedMatch,
      decision: MATCH_DECISION.APPROVED,
      candidateId: effectiveCandidateId,
    })
  }
  const handleIgnore = () => {
    if (!selectedMatch) return
    updateMutation.mutate({
      match: selectedMatch,
      decision: MATCH_DECISION.IGNORED,
    })
  }

  return (
    <div className="review-page">
      <section className="review-command-bar">
        <div>
          <span>当前任务</span>
          <select
            value={selectedJobId}
            onChange={handleJobChange}
            aria-label="选择审核任务"
          >
            {jobsQuery.data?.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className="review-summary">
          <span>
            <CheckCircle2 size={15} /> {job.approved_items} 已通过
          </span>
          <span>
            <TriangleAlert size={15} /> {reviewCount} 需要审核
          </span>
          <span>
            <CircleSlash size={15} /> {job.failed_items} 未识别
          </span>
        </div>
        <button
          className="button button-secondary"
          type="button"
          disabled={
            !selectedMatch?.group_key ||
            effectiveCandidateId === null ||
            groupUpdateMutation.isPending
          }
          onClick={() => groupUpdateMutation.mutate()}
        >
          <CheckCircle2 size={16} aria-hidden="true" />
          批准当前整组
        </button>
        <button
          className="button button-primary"
          type="button"
          disabled={job.status !== JOB_STATUS.READY || executeMutation.isPending}
          onClick={() => executeMutation.mutate()}
        >
          <Play size={16} aria-hidden="true" />
          确认并执行
        </button>
      </section>

      <ScanSummaryPanel
        items={sourceItemsQuery.data ?? []}
        isSaving={sourceItemMutation.isPending}
        onChangeAction={(itemId, action) =>
          sourceItemMutation.mutate({ itemId, action })
        }
      />

      <div className="review-workspace">
        <aside className="source-browser">
          <div className="panel-title">
            <h2>源文件</h2>
            <span>{matches.length}</span>
          </div>
          <div className="source-search">
            <Search size={15} aria-hidden="true" />
            <span>{job.source_directory_path}</span>
          </div>
          <ul className="source-list">
            {matchGroups.map((group) => (
              <li className="source-group" key={group.key}>
                <h3>{group.label}</h3>
                <ul>
                  {group.items.map((mediaMatch) => (
                    <li key={mediaMatch.id}>
                      <button
                        type="button"
                        className={
                          mediaMatch.id === selectedMatch?.id ? 'source-selected' : ''
                        }
                        onClick={() => handleSelectMatch(mediaMatch)}
                      >
                        <span className="file-icon" aria-hidden="true">
                          ▷
                        </span>
                        <span>
                          <strong>{episodeLabel(mediaMatch)}</strong>
                          <small>
                            {mediaMatch.filename} · {formatBytes(mediaMatch.size_bytes)}
                          </small>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </aside>

        <GroupedMatchTable
          groups={matchGroups}
          selectedMatchId={selectedMatch?.id ?? null}
          onSelectMatch={handleSelectMatch}
        />

        <MatchInspector
          mediaMatch={selectedMatch}
          selectedCandidateId={effectiveCandidateId}
          isSaving={updateMutation.isPending}
          onSelectCandidate={setSelectedCandidateId}
          onApprove={handleApprove}
          onIgnore={handleIgnore}
        />
      </div>
      {updateMutation.isError ? <ErrorNotice message={updateMutation.error.message} /> : null}
      {executeMutation.isError ? <ErrorNotice message={executeMutation.error.message} /> : null}
      {sourceItemMutation.isError ? (
        <ErrorNotice message={sourceItemMutation.error.message} />
      ) : null}
      {groupUpdateMutation.isError ? (
        <ErrorNotice message={groupUpdateMutation.error.message} />
      ) : null}
    </div>
  )
}

function isReviewDecision(decision: MatchDecision): boolean {
  return decision === MATCH_DECISION.REVIEW || decision === MATCH_DECISION.UNRESOLVED
}
