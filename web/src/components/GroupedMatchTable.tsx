import { AUTO_APPROVE_THRESHOLD, REVIEW_THRESHOLD } from '../constants'
import { LoaderCircle } from 'lucide-react'
import type { MediaMatch } from '../types'
import { formatConfidence } from '../utils/format'
import {
  isMetadataPending,
  matchRecognitionMessages,
} from '../utils/matchFailureReasons'
import {
  episodeLabel,
  isBatchApprovableMatch,
  type MediaMatchGroup,
} from '../utils/reviewGrouping'
import { Poster } from './Poster'
import { StatusBadge } from './StatusBadge'

interface GroupedMatchTableProps {
  groups: MediaMatchGroup[]
  selectedMatchId: string | null
  selectedMatchIds: ReadonlySet<string>
  isSelectionEnabled: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
  onToggleSelection: (matchId: string) => void
  onTogglePageSelection: () => void
}

export function GroupedMatchTable({
  groups,
  selectedMatchId,
  selectedMatchIds,
  isSelectionEnabled,
  onSelectMatch,
  onToggleSelection,
  onTogglePageSelection,
}: GroupedMatchTableProps) {
  const approvableMatches = groups
    .flatMap((group) => group.items)
    .filter(isBatchApprovableMatch)
  const areAllApprovableSelected =
    approvableMatches.length > 0 &&
    approvableMatches.every((mediaMatch) =>
      selectedMatchIds.has(mediaMatch.id),
    )
  return (
    <section className="match-table-panel" aria-labelledby="match-table-title">
      <div className="panel-title">
        <h2 id="match-table-title">TMDB 优先识别</h2>
        <label className="page-selection">
          <input
            type="checkbox"
            checked={areAllApprovableSelected}
            disabled={!isSelectionEnabled || approvableMatches.length === 0}
            onChange={onTogglePageSelection}
          />
          选择本页可批准项
        </label>
      </div>
      <div className="match-rows">
        {groups.map((group) => (
          <section className="match-group" key={group.key}>
            <h3>{group.label}</h3>
            {group.items.map((mediaMatch) => (
              <MatchRow
                key={mediaMatch.id}
                mediaMatch={mediaMatch}
                isSelected={mediaMatch.id === selectedMatchId}
                isChecked={selectedMatchIds.has(mediaMatch.id)}
                isSelectionEnabled={isSelectionEnabled}
                onSelectMatch={onSelectMatch}
                onToggleSelection={onToggleSelection}
              />
            ))}
          </section>
        ))}
      </div>
    </section>
  )
}

interface MatchRowProps {
  mediaMatch: MediaMatch
  isSelected: boolean
  isChecked: boolean
  isSelectionEnabled: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
  onToggleSelection: (matchId: string) => void
}

function MatchRow({
  mediaMatch,
  isSelected,
  isChecked,
  isSelectionEnabled,
  onSelectMatch,
  onToggleSelection,
}: MatchRowProps) {
  const selectedCandidate =
    mediaMatch.candidates.find(
      (candidate) => candidate.tmdb_id === mediaMatch.selected_tmdb_id,
    ) ?? mediaMatch.candidates[0]
  const recognitionMessage = matchRecognitionMessages(mediaMatch)[0]
  const isPending = isMetadataPending(mediaMatch)
  const isApprovable = isBatchApprovableMatch(mediaMatch)
  const handleOpenMatch = () => onSelectMatch(mediaMatch)
  const handleToggleSelection = () => onToggleSelection(mediaMatch.id)
  return (
    <div
      className={`match-row${isSelected ? ' match-row-selected' : ''}`}
    >
      <input
        className="match-selection"
        type="checkbox"
        aria-label={`选择 ${mediaMatch.filename}`}
        checked={isChecked}
        disabled={!isSelectionEnabled || !isApprovable}
        onChange={handleToggleSelection}
      />
      <button
        className="match-row-open"
        type="button"
        onClick={handleOpenMatch}
      >
        <Poster
          src={selectedCandidate?.poster_url ?? null}
          title={selectedCandidate?.title ?? mediaMatch.parsed_title}
        />
        <span className="match-source">
          <strong>{episodeLabel(mediaMatch)}</strong>
          <small>{mediaMatch.filename}</small>
        </span>
        <span className="match-result">
          <strong>{selectedCandidate?.title ?? '未找到候选'}</strong>
          <small
            className={
              recognitionMessage
                ? isPending
                  ? 'match-pending-reason'
                  : 'match-failure-reason'
                : undefined
            }
          >
            {recognitionMessage ??
              selectedCandidate?.original_title ??
              mediaMatch.parsed_title}
          </small>
        </span>
        <strong className={`confidence confidence-${confidenceTone(mediaMatch.confidence)}`}>
          {formatConfidence(mediaMatch.confidence)}
        </strong>
        {isPending ? (
          <span className="status-badge status-info">
            <LoaderCircle size={14} aria-hidden="true" />
            识别中
          </span>
        ) : (
          <StatusBadge status={mediaMatch.decision} />
        )}
      </button>
    </div>
  )
}

function confidenceTone(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= AUTO_APPROVE_THRESHOLD) return 'high'
  if (confidence >= REVIEW_THRESHOLD) return 'medium'
  return 'low'
}
