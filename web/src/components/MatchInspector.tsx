import { Check, CircleSlash, FolderOutput } from 'lucide-react'
import { Poster } from './Poster'
import type { MatchCandidate, MediaMatch } from '../types'
import { formatConfidence } from '../utils/format'

interface MatchInspectorProps {
  mediaMatch: MediaMatch | null
  selectedCandidateId: number | null
  isSaving: boolean
  onSelectCandidate: (candidateId: number) => void
  onApprove: () => void
  onIgnore: () => void
}

export function MatchInspector({
  mediaMatch,
  selectedCandidateId,
  isSaving,
  onSelectCandidate,
  onApprove,
  onIgnore,
}: MatchInspectorProps) {
  if (!mediaMatch) {
    return (
      <aside className="match-inspector empty-inspector">
        <FolderOutput size={28} aria-hidden="true" />
        <h2>选择一个待审核文件</h2>
        <p>候选元数据和目标路径会显示在这里。</p>
      </aside>
    )
  }

  const selectedCandidate =
    mediaMatch.candidates.find((candidate) => candidate.tmdb_id === selectedCandidateId) ??
    mediaMatch.candidates[0] ??
    null

  return (
    <aside className="match-inspector" aria-labelledby="inspector-title">
      <div className="inspector-heading">
        <span>待审核项详情</span>
        <h2 id="inspector-title">{mediaMatch.filename}</h2>
      </div>
      <fieldset className="candidate-list">
        <legend>AI 候选匹配（{mediaMatch.candidates.length}）</legend>
        {mediaMatch.candidates.map((candidate) => (
          <CandidateOption
            candidate={candidate}
            isSelected={candidate.tmdb_id === selectedCandidate?.tmdb_id}
            onSelect={onSelectCandidate}
            key={candidate.tmdb_id}
          />
        ))}
      </fieldset>
      {selectedCandidate ? (
        <div className="metadata-preview">
          <h3>元数据预览</h3>
          <dl>
            <div>
              <dt>类型</dt>
              <dd>{selectedCandidate.media_type === 'TV' ? '剧集' : '电影'}</dd>
            </div>
            <div>
              <dt>标题</dt>
              <dd>{selectedCandidate.title}</dd>
            </div>
            <div>
              <dt>原名</dt>
              <dd>{selectedCandidate.original_title || '—'}</dd>
            </div>
            <div>
              <dt>年份</dt>
              <dd>{selectedCandidate.year ?? '—'}</dd>
            </div>
          </dl>
          <h3>目标路径预览</h3>
          <code>{mediaMatch.target_path || '选择候选后生成目标路径'}</code>
        </div>
      ) : null}
      <div className="inspector-actions">
        <button
          className="button button-primary"
          type="button"
          disabled={!selectedCandidate || isSaving}
          onClick={onApprove}
        >
          <Check size={16} aria-hidden="true" />
          采用此匹配
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={isSaving}
          onClick={onIgnore}
        >
          <CircleSlash size={16} aria-hidden="true" />
          标记忽略
        </button>
      </div>
    </aside>
  )
}

interface CandidateOptionProps {
  candidate: MatchCandidate
  isSelected: boolean
  onSelect: (candidateId: number) => void
}

function CandidateOption({ candidate, isSelected, onSelect }: CandidateOptionProps) {
  const handleChange = () => {
    onSelect(candidate.tmdb_id)
  }

  return (
    <label className={`candidate-option${isSelected ? ' candidate-selected' : ''}`}>
      <input
        type="radio"
        name="candidate"
        checked={isSelected}
        onChange={handleChange}
      />
      <Poster src={candidate.poster_url} title={candidate.title} size="medium" />
      <span className="candidate-copy">
        <strong>{candidate.title}</strong>
        <small>
          {candidate.original_title} · {candidate.year ?? '年份未知'}
        </small>
      </span>
      <strong className="candidate-score">{formatConfidence(candidate.score)}</strong>
    </label>
  )
}
