import { useState } from 'react'
import {
  Check,
  ChevronDown,
  CircleAlert,
  CircleSlash,
  FolderOutput,
  RotateCcw,
  Undo2,
} from 'lucide-react'
import { Poster } from '@/components/Poster'
import { RecognitionNotice } from '@/components/RecognitionNotice'
import {
  MATCH_DECISION,
  type ManualMatchInput,
  type MatchCandidate,
  type MediaMatch,
  type MediaType,
} from '@/types'
import { formatConfidence } from '@/utils/format'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

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
      <aside className="grid h-full place-items-center bg-card">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <FolderOutput aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>选择一个待审核文件</EmptyTitle>
            <EmptyDescription>候选元数据和目标路径会显示在这里。</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </aside>
    )
  }

  const selectedCandidate =
    mediaMatch.candidates.find((candidate) => candidate.tmdb_id === selectedCandidateId) ??
    mediaMatch.candidates[0] ??
    null

  return (
    <aside className="flex h-full min-h-0 flex-col bg-card" aria-labelledby="inspector-title">
      <div className="shrink-0 border-b px-4 py-3">
        <span className="text-xs text-muted-foreground">待审核项详情</span>
        <h2 id="inspector-title" className="mt-1 truncate text-sm font-medium">
          {mediaMatch.filename}
        </h2>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-4 p-4">
          <RecognitionNotice mediaMatch={mediaMatch} />
          {mediaMatch.execution_error ? (
            <Alert variant="destructive">
              <CircleAlert aria-hidden="true" />
              <AlertTitle>执行失败</AlertTitle>
              <AlertDescription>{mediaMatch.execution_error}</AlertDescription>
            </Alert>
          ) : null}

          <Field>
            <FieldLabel>TMDB 候选匹配（{mediaMatch.candidates.length}）</FieldLabel>
            {mediaMatch.candidates.length ? (
              <RadioGroup
                value={selectedCandidate ? String(selectedCandidate.tmdb_id) : ''}
                onValueChange={(value) => onSelectCandidate(Number(value))}
                className="flex flex-col gap-2"
              >
                {mediaMatch.candidates.map((candidate) => (
                  <CandidateOption
                    candidate={candidate}
                    isSelected={candidate.tmdb_id === selectedCandidate?.tmdb_id}
                    key={candidate.tmdb_id}
                  />
                ))}
              </RadioGroup>
            ) : (
              <p className="rounded-lg border border-dashed p-3 text-xs leading-relaxed text-muted-foreground">
                自动识别没有返回候选。可重试当前文件，或在下方手动指定 TMDB 信息。
              </p>
            )}
          </Field>

          {selectedCandidate ? (
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-medium">元数据预览</h3>
              <dl className="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-2 text-xs">
                <dt className="text-muted-foreground">类型</dt>
                <dd>{selectedCandidate.media_type === 'TV' ? '剧集' : '电影'}</dd>
                <dt className="text-muted-foreground">标题</dt>
                <dd>{selectedCandidate.title}</dd>
                <dt className="text-muted-foreground">原名</dt>
                <dd>{selectedCandidate.original_title || '—'}</dd>
                <dt className="text-muted-foreground">年份</dt>
                <dd>{selectedCandidate.year ?? '—'}</dd>
              </dl>
              <h3 className="text-sm font-medium">目标路径预览</h3>
              <code className="break-all rounded-lg border bg-muted/40 p-3 text-[0.68rem] leading-relaxed">
                {mediaMatch.target_path || '选择候选后生成目标路径'}
              </code>
            </div>
          ) : null}

          <ManualMatchForm
            key={mediaMatch.id}
            mediaMatch={mediaMatch}
            isSaving={isSaving}
            onSubmit={onManualMatch}
          />
        </div>
      </ScrollArea>
      <div className="grid shrink-0 gap-2 border-t bg-card p-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
        <Button type="button" disabled={!selectedCandidate || isSaving} onClick={onApprove}>
          <Check data-icon="inline-start" aria-hidden="true" />
          采用此匹配
        </Button>
        <Button
          variant="outline"
          type="button"
          disabled={isSaving || isRetrying}
          onClick={onRetry}
        >
          <RotateCcw data-icon="inline-start" aria-hidden="true" />
          {isRetrying ? '正在重试' : '重试此文件'}
        </Button>
        <Button variant="outline" type="button" disabled={isSaving} onClick={onToggleIgnore}>
          {mediaMatch.decision === MATCH_DECISION.IGNORED ? (
            <Undo2 data-icon="inline-start" aria-hidden="true" />
          ) : (
            <CircleSlash data-icon="inline-start" aria-hidden="true" />
          )}
          {mediaMatch.decision === MATCH_DECISION.IGNORED ? '恢复审核' : '忽略此文件'}
        </Button>
      </div>
    </aside>
  )
}

function CandidateOption({
  candidate,
  isSelected,
}: {
  candidate: MatchCandidate
  isSelected: boolean
}) {
  return (
    <FieldLabel
      htmlFor={`candidate-${candidate.tmdb_id}`}
      className={cn(
        'grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2 rounded-lg border p-2',
        isSelected && 'border-primary/40 bg-primary/5',
      )}
    >
      <RadioGroupItem id={`candidate-${candidate.tmdb_id}`} value={String(candidate.tmdb_id)} />
      <Poster src={candidate.poster_url} title={candidate.title} size="medium" />
      <span className="min-w-0">
        <strong className="block truncate text-xs font-medium">{candidate.title}</strong>
        <small className="block truncate text-[0.68rem] text-muted-foreground">
          {candidate.original_title} · {candidate.year ?? '年份未知'}
        </small>
      </span>
      <strong className="text-xs tabular-nums text-warning">
        {formatConfidence(candidate.score)}
      </strong>
    </FieldLabel>
  )
}

function ManualMatchForm({
  mediaMatch,
  isSaving,
  onSubmit,
}: {
  mediaMatch: MediaMatch
  isSaving: boolean
  onSubmit: (match: ManualMatchInput) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [tmdbId, setTmdbId] = useState('')
  const [title, setTitle] = useState(mediaMatch.parsed_title)
  const [originalTitle, setOriginalTitle] = useState('')
  const [year, setYear] = useState(mediaMatch.parsed_year ? String(mediaMatch.parsed_year) : '')
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
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button variant="outline" type="button" className="w-full justify-between">
          手动指定 TMDB 匹配
          <ChevronDown
            data-icon="inline-end"
            className={cn('transition-transform', isOpen && 'rotate-180')}
            aria-hidden="true"
          />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <form className="mt-3 rounded-lg border p-3" onSubmit={handleSubmit}>
          <FieldGroup className="grid gap-3 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="manual-tmdb-id">TMDB ID</FieldLabel>
              <Input
                id="manual-tmdb-id"
                type="number"
                min="1"
                value={tmdbId}
                onChange={(event) => setTmdbId(event.target.value)}
                required
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="manual-media-type">类型</FieldLabel>
              <Select
                value={mediaType}
                onValueChange={(value) => {
                  if (value === 'MOVIE' || value === 'TV') setMediaType(value)
                }}
              >
                <SelectTrigger id="manual-media-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="MOVIE">电影</SelectItem>
                    <SelectItem value="TV">电视剧</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="manual-title">标题</FieldLabel>
              <Input
                id="manual-title"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                required
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="manual-original-title">原始标题</FieldLabel>
              <Input
                id="manual-original-title"
                type="text"
                value={originalTitle}
                onChange={(event) => setOriginalTitle(event.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="manual-year">年份</FieldLabel>
              <Input
                id="manual-year"
                type="number"
                min="1870"
                max="2100"
                value={year}
                onChange={(event) => setYear(event.target.value)}
              />
            </Field>
            {validationMessage ? (
              <FieldError className="sm:col-span-2">{validationMessage}</FieldError>
            ) : null}
            <Button className="sm:col-span-2" type="submit" disabled={isSaving}>
              <Check data-icon="inline-start" aria-hidden="true" />
              保存并采用手动匹配
            </Button>
          </FieldGroup>
        </form>
      </CollapsibleContent>
    </Collapsible>
  )
}
