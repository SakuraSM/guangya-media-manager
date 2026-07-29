import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleSlash, Play, Search, TriangleAlert } from 'lucide-react'
import { api } from '../api/client'
import { AUTO_APPROVE_THRESHOLD, REVIEW_THRESHOLD } from '../constants'
import { ErrorNotice } from '../components/ErrorNotice'
import { LoadingScreen } from '../components/LoadingScreen'
import { MatchInspector } from '../components/MatchInspector'
import { Poster } from '../components/Poster'
import { StatusBadge } from '../components/StatusBadge'
import {
  JOB_STATUS,
  MATCH_DECISION,
  type MatchDecision,
  type MediaMatch,
} from '../types'
import { formatBytes, formatConfidence } from '../utils/format'

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

  if (jobsQuery.isPending || matchesQuery.isPending || jobQuery.isPending) {
    return <LoadingScreen label="正在加载匹配审核" />
  }
  if (jobsQuery.isError || matchesQuery.isError || jobQuery.isError) {
    const error = jobsQuery.error ?? matchesQuery.error ?? jobQuery.error
    return <ErrorNotice message={error?.message ?? '审核数据加载失败'} />
  }

  const matches = matchesQuery.data ?? []
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
          className="button button-primary"
          type="button"
          disabled={job.status !== JOB_STATUS.READY || executeMutation.isPending}
          onClick={() => executeMutation.mutate()}
        >
          <Play size={16} aria-hidden="true" />
          确认并执行
        </button>
      </section>

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
            {matches.map((mediaMatch) => (
              <li key={mediaMatch.id}>
                <button
                  type="button"
                  className={mediaMatch.id === selectedMatch?.id ? 'source-selected' : ''}
                  onClick={() => handleSelectMatch(mediaMatch)}
                >
                  <span className="file-icon" aria-hidden="true">
                    ▷
                  </span>
                  <span>
                    <strong>{mediaMatch.filename}</strong>
                    <small>{formatBytes(mediaMatch.size_bytes)}</small>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="match-table-panel" aria-labelledby="match-table-title">
          <div className="panel-title">
            <h2 id="match-table-title">AI 识别与 TMDB 匹配</h2>
            <span>自动通过阈值 90%</span>
          </div>
          <div className="match-rows">
            {matches.map((mediaMatch) => {
              const selectedCandidate =
                mediaMatch.candidates.find(
                  (candidate) => candidate.tmdb_id === mediaMatch.selected_tmdb_id,
                ) ?? mediaMatch.candidates[0]
              return (
                <button
                  className={`match-row${mediaMatch.id === selectedMatch?.id ? ' match-row-selected' : ''}`}
                  type="button"
                  onClick={() => handleSelectMatch(mediaMatch)}
                  key={mediaMatch.id}
                >
                  <Poster
                    src={selectedCandidate?.poster_url ?? null}
                    title={selectedCandidate?.title ?? mediaMatch.parsed_title}
                  />
                  <span className="match-source">
                    <strong>{mediaMatch.filename}</strong>
                    <small>
                      {mediaMatch.media_type === 'TV' ? '剧集' : '电影'} ·{' '}
                      {mediaMatch.parsed_year ?? '年份未知'}
                    </small>
                  </span>
                  <span className="match-result">
                    <strong>{selectedCandidate?.title ?? '未找到候选'}</strong>
                    <small>
                      {selectedCandidate?.original_title ?? mediaMatch.parsed_title}
                    </small>
                  </span>
                  <strong className={`confidence confidence-${confidenceTone(mediaMatch.confidence)}`}>
                    {formatConfidence(mediaMatch.confidence)}
                  </strong>
                  <StatusBadge status={mediaMatch.decision} />
                </button>
              )
            })}
          </div>
        </section>

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
    </div>
  )
}

function confidenceTone(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= AUTO_APPROVE_THRESHOLD) return 'high'
  if (confidence >= REVIEW_THRESHOLD) return 'medium'
  return 'low'
}

function isReviewDecision(decision: MatchDecision): boolean {
  return decision === MATCH_DECISION.REVIEW || decision === MATCH_DECISION.UNRESOLVED
}
