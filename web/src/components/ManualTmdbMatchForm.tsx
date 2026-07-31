import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronDown, Search } from 'lucide-react'
import { api } from '@/api/client'
import { ManualMatchSubmitActions } from '@/components/ManualMatchSubmitActions'
import {
  TmdbSearchResults,
  TvEpisodeMappingFields,
} from '@/components/ManualTmdbMatchFields'
import {
  type ManualMatchInput,
  type MatchCandidate,
  type MediaMatch,
} from '@/types'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { buildManualMatchInput } from '@/utils/episodeExpression'

interface ManualTmdbMatchFormProps {
  jobId: string
  mediaMatch: MediaMatch
  isSaving: boolean
  onSubmitCurrent: (match: ManualMatchInput) => void
  onSubmitGroup: (match: ManualMatchInput) => void
}

export function ManualTmdbMatchForm({
  jobId,
  mediaMatch,
  isSaving,
  onSubmitCurrent,
  onSubmitGroup,
}: ManualTmdbMatchFormProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState(mediaMatch.parsed_title)
  const [mediaType, setMediaType] = useState<'MOVIE' | 'TV'>(
    mediaMatch.media_type === 'MOVIE' ? 'MOVIE' : 'TV',
  )
  const [selectedCandidate, setSelectedCandidate] = useState<MatchCandidate | null>(null)
  const [seasonNumber, setSeasonNumber] = useState(
    String(mediaMatch.season_number ?? 1),
  )
  const [episodeExpression, setEpisodeExpression] = useState(
    mediaMatch.episode_numbers.join(','),
  )
  const [validationMessage, setValidationMessage] = useState('')
  const previewMutation = useMutation({
    mutationFn: (input: ManualMatchInput) =>
      api.previewManualMatch({
        jobId,
        matchId: mediaMatch.id,
        match: input,
      }),
  })
  const searchMutation = useMutation({
    mutationFn: () =>
      api.searchTmdb({
        jobId,
        query: query.trim(),
        mediaType,
        year: mediaMatch.parsed_year,
      }),
    onSuccess: (candidates) => {
      setSelectedCandidate(candidates[0] ?? null)
      previewMutation.reset()
    },
  })
  const seasonsQuery = useQuery({
    queryKey: ['tmdb-seasons', jobId, selectedCandidate?.tmdb_id],
    queryFn: () => api.getTmdbSeasons(jobId, selectedCandidate?.tmdb_id ?? 0),
    enabled: selectedCandidate?.media_type === 'TV',
  })
  const parsedSeasonNumber = Number(seasonNumber)
  const episodesQuery = useQuery({
    queryKey: [
      'tmdb-episodes',
      jobId,
      selectedCandidate?.tmdb_id,
      parsedSeasonNumber,
    ],
    queryFn: () =>
      api.getTmdbEpisodes(
        jobId,
        selectedCandidate?.tmdb_id ?? 0,
        parsedSeasonNumber,
      ),
    enabled:
      selectedCandidate?.media_type === 'TV' &&
      Number.isInteger(parsedSeasonNumber) &&
      parsedSeasonNumber >= 0,
  })
  const currentInput = useMemo(
    () => buildManualMatchInput({
      candidate: selectedCandidate,
      seasonNumber,
      episodeExpression,
    }),
    [episodeExpression, seasonNumber, selectedCandidate],
  )
  const handleSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!query.trim()) {
      setValidationMessage('请输入 TMDB 搜索关键字。')
      return
    }
    setValidationMessage('')
    searchMutation.mutate()
  }
  const handlePreview = () => {
    if (!currentInput) {
      setValidationMessage(
        mediaType === 'TV'
          ? '请选择 TMDB 条目，并填写有效的季号和集号。'
          : '请选择一个 TMDB 条目。',
      )
      return
    }
    setValidationMessage('')
    previewMutation.mutate(currentInput)
  }
  const handleCandidateChange = (candidateId: string) => {
    const candidate =
      searchMutation.data?.find((item) => item.tmdb_id === Number(candidateId)) ??
      null
    setSelectedCandidate(candidate)
    previewMutation.reset()
  }
  const handleMappingChange = (
    setter: React.Dispatch<React.SetStateAction<string>>,
    value: string,
  ) => {
    setter(value)
    previewMutation.reset()
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button variant="outline" type="button" className="w-full justify-between">
          搜索并手动匹配 TMDB
          <ChevronDown
            data-icon="inline-end"
            className={cn('transition-transform', isOpen && 'rotate-180')}
            aria-hidden="true"
          />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-3 flex flex-col gap-3 rounded-lg border p-3">
          <form onSubmit={handleSearch}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor={`manual-search-${mediaMatch.id}`}>
                  TMDB 关键字
                </FieldLabel>
                <Input
                  id={`manual-search-${mediaMatch.id}`}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="输入影视名称"
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`manual-type-${mediaMatch.id}`}>类型</FieldLabel>
                <Select
                  value={mediaType}
                  onValueChange={(value) => {
                    if (value !== 'MOVIE' && value !== 'TV') return
                    setMediaType(value)
                    setSelectedCandidate(null)
                    searchMutation.reset()
                    previewMutation.reset()
                  }}
                >
                  <SelectTrigger id={`manual-type-${mediaMatch.id}`} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="TV">电视剧</SelectItem>
                      <SelectItem value="MOVIE">电影</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Button type="submit" disabled={searchMutation.isPending}>
                <Search data-icon="inline-start" aria-hidden="true" />
                {searchMutation.isPending ? '正在搜索' : '搜索 TMDB'}
              </Button>
            </FieldGroup>
          </form>

          {searchMutation.error ? (
            <FieldError>{searchMutation.error.message}</FieldError>
          ) : null}
          {searchMutation.data ? (
            <TmdbSearchResults
              mediaMatchId={mediaMatch.id}
              candidates={searchMutation.data}
              selectedCandidate={selectedCandidate}
              onCandidateChange={handleCandidateChange}
            />
          ) : null}

          {selectedCandidate?.media_type === 'TV' ? (
            <TvEpisodeMappingFields
              mediaMatchId={mediaMatch.id}
              seasonNumber={seasonNumber}
              episodeExpression={episodeExpression}
              seasons={seasonsQuery.data ?? []}
              episodes={episodesQuery.data ?? []}
              onSeasonNumberChange={(value) =>
                handleMappingChange(setSeasonNumber, value)
              }
              onEpisodeExpressionChange={(value) =>
                handleMappingChange(setEpisodeExpression, value)
              }
            />
          ) : null}

          {validationMessage ? <FieldError>{validationMessage}</FieldError> : null}
          {previewMutation.error ? (
            <FieldError>{previewMutation.error.message}</FieldError>
          ) : null}
          <Button
            type="button"
            variant="outline"
            disabled={!selectedCandidate || previewMutation.isPending}
            onClick={handlePreview}
          >
            生成整理路径预览
          </Button>
          {previewMutation.data ? (
            <Alert>
              <AlertTitle>整理路径预览</AlertTitle>
              <AlertDescription className="flex flex-col gap-2">
                <code className="break-all text-xs">
                  {previewMutation.data.target_path}
                </code>
                {previewMutation.data.missing_episode_numbers.length ? (
                  <span>
                    TMDB 中缺少集号：
                    {previewMutation.data.missing_episode_numbers.join('、')}，将使用基础元数据。
                  </span>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}
          <ManualMatchSubmitActions
            mediaType={selectedCandidate?.media_type ?? null}
            input={currentInput}
            isPreviewReady={Boolean(previewMutation.data)}
            isSaving={isSaving}
            onSubmitCurrent={onSubmitCurrent}
            onSubmitGroup={onSubmitGroup}
          />
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
