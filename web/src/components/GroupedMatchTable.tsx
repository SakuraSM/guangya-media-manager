import { AUTO_APPROVE_THRESHOLD, REVIEW_THRESHOLD } from '../constants'
import type { MediaMatch } from '../types'
import { formatConfidence } from '../utils/format'
import { episodeLabel, type MediaMatchGroup } from '../utils/reviewGrouping'
import { Poster } from './Poster'
import { StatusBadge } from './StatusBadge'

interface GroupedMatchTableProps {
  groups: MediaMatchGroup[]
  selectedMatchId: string | null
  onSelectMatch: (mediaMatch: MediaMatch) => void
}

export function GroupedMatchTable({
  groups,
  selectedMatchId,
  onSelectMatch,
}: GroupedMatchTableProps) {
  return (
    <section className="match-table-panel" aria-labelledby="match-table-title">
      <div className="panel-title">
        <h2 id="match-table-title">AI 识别与 TMDB 匹配</h2>
        <span>自动通过阈值 90%</span>
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
                onSelectMatch={onSelectMatch}
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
  onSelectMatch: (mediaMatch: MediaMatch) => void
}

function MatchRow({ mediaMatch, isSelected, onSelectMatch }: MatchRowProps) {
  const selectedCandidate =
    mediaMatch.candidates.find(
      (candidate) => candidate.tmdb_id === mediaMatch.selected_tmdb_id,
    ) ?? mediaMatch.candidates[0]
  return (
    <button
      className={`match-row${isSelected ? ' match-row-selected' : ''}`}
      type="button"
      onClick={() => onSelectMatch(mediaMatch)}
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
        <small>{selectedCandidate?.original_title ?? mediaMatch.parsed_title}</small>
      </span>
      <strong className={`confidence confidence-${confidenceTone(mediaMatch.confidence)}`}>
        {formatConfidence(mediaMatch.confidence)}
      </strong>
      <StatusBadge status={mediaMatch.decision} />
    </button>
  )
}

function confidenceTone(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= AUTO_APPROVE_THRESHOLD) return 'high'
  if (confidence >= REVIEW_THRESHOLD) return 'medium'
  return 'low'
}
