import { useState } from 'react'
import { Check, CircleSlash, FolderOutput, RotateCcw, Undo2 } from 'lucide-react'
import { Poster } from './Poster'
import { RecognitionNotice } from './RecognitionNotice'
import {
  MATCH_DECISION,
  type ManualMatchInput,
  type MatchCandidate,
  type MediaMatch,
  type MediaType,
} from '../types'
import { formatConfidence } from '../utils/format'

interface MatchInspectorProps {
  mediaMatch: MediaMatch | null
  selectedCandidateId: number | null
  isSaving: boolean
  isRetrying: boolean
  onSelectCandidate: (candidateId: number) => void
  onApprove: () => void
  onToggleIgnore: () => void
  onRetry: () => void
  onManualMatch: (match: ManualMatchInput) => void
}

export function MatchInspector({
  mediaMatch,
  selectedCandidateId,
  isSaving,
  isRetrying,
  onSelectCandidate,
  onApprove,
  onToggleIgnore,
  onRetry,
  onManualMatch,
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
      <RecognitionNotice mediaMatch={mediaMatch} />
      <fieldset className="candidate-list">
        <legend>TMDB 候选匹配（{mediaMatch.candidates.length}）</legend>
        {mediaMatch.candidates.length ? (
          mediaMatch.candidates.map((candidate) => (
            <CandidateOption
              candidate={candidate}
              isSelected={candidate.tmdb_id === selectedCandidate?.tmdb_id}
              onSelect={onSelectCandidate}
              key={candidate.tmdb_id}
            />
          ))
        ) : (
          <p className="empty-candidates">
            自动识别没有返回候选。可重试当前文件，或在下方手动指定 TMDB 信息。
          </p>
        )}
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
      <ManualMatchForm
        key={mediaMatch.id}
        mediaMatch={mediaMatch}
        isSaving={isSaving}
        onSubmit={onManualMatch}
      />
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
          disabled={isSaving || isRetrying}
          onClick={onRetry}
        >
          <RotateCcw size={16} aria-hidden="true" />
          {isRetrying ? '正在重试' : '重试此文件'}
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={isSaving}
          onClick={onToggleIgnore}
        >
          {mediaMatch.decision === MATCH_DECISION.IGNORED ? (
            <Undo2 size={16} aria-hidden="true" />
          ) : (
            <CircleSlash size={16} aria-hidden="true" />
          )}
          {mediaMatch.decision === MATCH_DECISION.IGNORED
            ? '恢复为待审核'
            : '忽略此文件'}
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

interface ManualMatchFormProps {
  mediaMatch: MediaMatch
  isSaving: boolean
  onSubmit: (match: ManualMatchInput) => void
}

function ManualMatchForm({
  mediaMatch,
  isSaving,
  onSubmit,
}: ManualMatchFormProps) {
  const [tmdbId, setTmdbId] = useState('')
  const [title, setTitle] = useState(mediaMatch.parsed_title)
  const [originalTitle, setOriginalTitle] = useState('')
  const [year, setYear] = useState(
    mediaMatch.parsed_year ? String(mediaMatch.parsed_year) : '',
  )
  const [mediaType, setMediaType] = useState<Exclude<MediaType, 'UNKNOWN'>>(
    mediaMatch.media_type === 'TV' ? 'TV' : 'MOVIE',
  )
  const [validationMessage, setValidationMessage] = useState('')

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const parsedTmdbId = Number(tmdbId)
    const parsedYear = year ? Number(year) : null
    if (!Number.isInteger(parsedTmdbId) || parsedTmdbId <= 0 || !title.trim()) {
      setValidationMessage('请填写有效的 TMDB ID 和标题。')
      return
    }
    if (parsedYear !== null && !Number.isInteger(parsedYear)) {
      setValidationMessage('年份必须是整数。')
      return
    }
    setValidationMessage('')
    onSubmit({
      tmdbId: parsedTmdbId,
      title: title.trim(),
      originalTitle: originalTitle.trim(),
      year: parsedYear,
      mediaType,
    })
  }

  return (
    <details className="manual-match-panel">
      <summary>手动指定 TMDB 匹配</summary>
      <form onSubmit={handleSubmit}>
        <label>
          TMDB ID
          <input
            type="number"
            min="1"
            value={tmdbId}
            onChange={(event) => setTmdbId(event.target.value)}
            required
          />
        </label>
        <label>
          标题
          <input
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
          />
        </label>
        <label>
          原始标题
          <input
            type="text"
            value={originalTitle}
            onChange={(event) => setOriginalTitle(event.target.value)}
          />
        </label>
        <label>
          年份
          <input
            type="number"
            min="1870"
            max="2100"
            value={year}
            onChange={(event) => setYear(event.target.value)}
          />
        </label>
        <label>
          类型
          <select
            value={mediaType}
            onChange={(event) => {
              if (event.target.value === 'MOVIE' || event.target.value === 'TV') {
                setMediaType(event.target.value)
              }
            }}
          >
            <option value="MOVIE">电影</option>
            <option value="TV">电视剧</option>
          </select>
        </label>
        {validationMessage ? (
          <p className="form-error" role="alert">
            {validationMessage}
          </p>
        ) : null}
        <button className="button button-primary" type="submit" disabled={isSaving}>
          <Check size={16} aria-hidden="true" />
          保存并采用手动匹配
        </button>
      </form>
    </details>
  )
}
