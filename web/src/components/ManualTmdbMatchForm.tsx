import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Check, ChevronDown, Search } from 'lucide-react'
import { api } from '@/api/client'
import {
  TmdbSearchResults,
  TvEpisodeMappingFields,
} from '@/components/ManualTmdbMatchFields'
import { type ManualMatchInput, type MatchCandidate, type MediaMatch } from '@/types'
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
import {
  buildManualMatchInput,
  formatEpisodeMappingLabel,
  inferManualEpisodeMapping,
} from '@/utils/episodeExpression'

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
  const episodeMapping = inferManualEpisodeMapping({
    filename: mediaMatch.filename,
    sourcePath: mediaMatch.source_path,
    seasonNumber: mediaMatch.season_number,
    episodeNumbers: mediaMatch.episode_numbers,
  })
  const hasNoCandidates = mediaMatch.candidates.length === 0
  const [isOpen, setIsOpen] = useState(hasNoCandidates)
  const [query, setQuery] = useState(mediaMatch.parsed_title)
  const [mediaType, setMediaType] = useState<'MOVIE' | 'TV'>(
    mediaMatch.media_type === 'MOVIE' ? 'MOVIE' : 'TV',
  )
  const [selectedCandidate, setSelectedCandidate] = useState<MatchCandidate | null>(null)
  const [seasonNumber, setSeasonNumber] = useState(
    String(episodeMapping?.seasonNumber ?? 1),
  )
  const [episodeExpression, setEpisodeExpression] = useState(
    episodeMapping?.episodeNumbers.join(',') ?? '',
  )
  const [isMappingEdited, setIsMappingEdited] = useState(false)
  const [needsMappingConfirmation, setNeedsMappingConfirmation] = useState(false)
  const [validationMessage, setValidationMessage] = useState('')
  const searchMutation = useMutation({
    mutationFn: () =>
      api.searchTmdb({
        jobId,
        query: query.trim(),
        mediaType,
        year: mediaMatch.parsed_year,
      }),
    onSuccess: (candidates) => {
      setSelectedCandidate(null)
      setNeedsMappingConfirmation(false)
      if (candidates.length === 0) {
        setValidationMessage('没有找到 TMDB 候选，请调整关键字后重试。')
      }
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
  const handleCandidateSelect = (candidate: MatchCandidate) => {
    setSelectedCandidate(candidate)
    const input = buildManualMatchInput({
      candidate,
      seasonNumber,
      episodeExpression,
    })
    if (!input) {
      setNeedsMappingConfirmation(true)
      setValidationMessage('已选择该剧集，请补充有效的季号和集号后确认。')
      return
    }
    setNeedsMappingConfirmation(false)
    setValidationMessage('')
    if (candidate.media_type === 'TV') onSubmitGroup(input)
    else onSubmitCurrent(input)
  }
  const handleMappingChange = (
    setter: React.Dispatch<React.SetStateAction<string>>,
    value: string,
  ) => {
    setter(value)
    setIsMappingEdited(true)
  }
  const handleFallbackSubmit = () => {
    if (!currentInput) {
      setValidationMessage('请填写有效的季号和集号。')
      return
    }
    setValidationMessage('')
    if (currentInput.mediaType === 'TV') onSubmitGroup(currentInput)
    else onSubmitCurrent(currentInput)
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
                    setNeedsMappingConfirmation(false)
                    searchMutation.reset()
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
              disabled={isSaving}
              onCandidateSelect={handleCandidateSelect}
            />
          ) : null}

          {selectedCandidate?.media_type === 'TV' ? (
            <div className="flex flex-col gap-2">
              {episodeMapping && !isMappingEdited ? (
                <p className="text-xs text-muted-foreground" role="status">
                  已从原文件自动识别：{formatEpisodeMappingLabel(episodeMapping)}
                </p>
              ) : null}
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
            </div>
          ) : null}

          {validationMessage ? <FieldError>{validationMessage}</FieldError> : null}
          {selectedCandidate && needsMappingConfirmation ? (
            <Button
              type="button"
              disabled={isSaving || !currentInput}
              onClick={handleFallbackSubmit}
            >
              <Check data-icon="inline-start" aria-hidden="true" />
              填写季集后确认并应用到整个剧集
            </Button>
          ) : null}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
