import {
  type MatchCandidate,
  type TmdbEpisodeSummary,
  type TmdbSeasonSummary,
} from '@/types'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface TmdbSearchResultsProps {
  mediaMatchId: string
  candidates: MatchCandidate[]
  disabled: boolean
  onCandidateSelect: (candidate: MatchCandidate) => void
}

export function TmdbSearchResults({
  mediaMatchId,
  candidates,
  disabled,
  onCandidateSelect,
}: TmdbSearchResultsProps) {
  if (candidates.length === 0) {
    return <p className="text-xs text-muted-foreground">没有找到 TMDB 候选。</p>
  }

  return (
    <div
      className="flex max-h-52 flex-col gap-2 overflow-y-auto"
      aria-label="TMDB 搜索结果"
    >
      {candidates.map((candidate) => (
        <Button
          type="button"
          variant="outline"
          key={candidate.tmdb_id}
          id={`manual-candidate-${mediaMatchId}-${candidate.tmdb_id}`}
          disabled={disabled}
          onClick={() => onCandidateSelect(candidate)}
          className="h-auto justify-start p-2 text-left"
        >
          <span className="min-w-0">
            <strong className="block truncate text-xs">{candidate.title}</strong>
            <small className="block truncate text-muted-foreground">
              TMDB {candidate.tmdb_id} · {candidate.year ?? '年份未知'} · 选择即确认
            </small>
          </span>
        </Button>
      ))}
    </div>
  )
}

interface TvEpisodeMappingFieldsProps {
  mediaMatchId: string
  seasonNumber: string
  episodeExpression: string
  seasons: TmdbSeasonSummary[]
  episodes: TmdbEpisodeSummary[]
  onSeasonNumberChange: (value: string) => void
  onEpisodeExpressionChange: (value: string) => void
}

export function TvEpisodeMappingFields({
  mediaMatchId,
  seasonNumber,
  episodeExpression,
  seasons,
  episodes,
  onSeasonNumberChange,
  onEpisodeExpressionChange,
}: TvEpisodeMappingFieldsProps) {
  return (
    <FieldGroup>
      <Field>
        <FieldLabel htmlFor={`manual-season-${mediaMatchId}`}>季号</FieldLabel>
        <Input
          id={`manual-season-${mediaMatchId}`}
          type="number"
          min="0"
          max="99"
          value={seasonNumber}
          onChange={(event) => onSeasonNumberChange(event.target.value)}
        />
        {seasons.length ? (
          <p className="text-xs text-muted-foreground">
            TMDB 可用季度：
            {seasons.map((season) => season.season_number).join('、')}
          </p>
        ) : null}
      </Field>
      <Field>
        <FieldLabel htmlFor={`manual-episodes-${mediaMatchId}`}>集号</FieldLabel>
        <Input
          id={`manual-episodes-${mediaMatchId}`}
          value={episodeExpression}
          onChange={(event) => onEpisodeExpressionChange(event.target.value)}
          placeholder="例如 1、1,2 或 1-3"
        />
        {episodes.length ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            本季共 {episodes.length} 集
          </p>
        ) : null}
      </Field>
    </FieldGroup>
  )
}
