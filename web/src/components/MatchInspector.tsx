import {
  Check,
  CircleAlert,
  CircleSlash,
  FolderOutput,
  RefreshCcw,
  RotateCcw,
  Undo2,
} from 'lucide-react'
import { Poster } from '@/components/Poster'
import { RecognitionNotice } from '@/components/RecognitionNotice'
import { ManualTmdbMatchForm } from '@/components/ManualTmdbMatchForm'
import {
  MATCH_DECISION,
  type ManualMatchInput,
  type MatchCandidate,
  type MediaMatch,
} from '@/types'
import { formatConfidence } from '@/utils/format'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { Field, FieldLabel } from '@/components/ui/field'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

interface MatchInspectorProps {
  jobId: string
  mediaMatch: MediaMatch | null
  selectedCandidateId: number | null
  isSaving: boolean
  isRetrying: boolean
  isRetryingGroup: boolean
  onSelectCandidate: (candidateId: number) => void
  onApprove: () => void
  onToggleIgnore: () => void
  onRetry: () => void
  onRetryGroup: () => void
  onManualMatch: (match: ManualMatchInput) => void
}

export function MatchInspector({
  jobId,
  mediaMatch,
  selectedCandidateId,
  isSaving,
  isRetrying,
  isRetryingGroup,
  onSelectCandidate,
  onApprove,
  onToggleIgnore,
  onRetry,
  onRetryGroup,
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

          <ManualTmdbMatchForm
            key={mediaMatch.id}
            jobId={jobId}
            mediaMatch={mediaMatch}
            isSaving={isSaving}
            onSubmit={onManualMatch}
          />
        </div>
      </ScrollArea>
      <div className="grid shrink-0 gap-2 border-t bg-card p-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
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
        <Button
          variant="outline"
          type="button"
          disabled={isSaving || isRetryingGroup}
          onClick={onRetryGroup}
        >
          <RefreshCcw data-icon="inline-start" aria-hidden="true" />
          {isRetryingGroup ? '正在重试整组' : '重试整个影视组'}
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
