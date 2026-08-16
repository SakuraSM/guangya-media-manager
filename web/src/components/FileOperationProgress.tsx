import {
  CheckCircle2,
  CircleAlert,
  CircleSlash,
  Copy,
  LoaderCircle,
  Trash2,
} from 'lucide-react'
import type {
  FileOperationProgressSummary,
  Job,
  ProgressState,
} from '@/types'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

const PERCENT_SCALE = 100

const OPERATION_PRESENTATION: Record<
  'COPY' | 'TRASH',
  { label: string; activeLabel: string; icon: typeof Copy }
> = {
  COPY: { label: '文件转移', activeLabel: '正在转移', icon: Copy },
  TRASH: { label: '源文件清理', activeLabel: '正在清理', icon: Trash2 },
}

const OPERATION_STATE_ICON: Record<ProgressState, typeof CheckCircle2> = {
  QUEUED: LoaderCircle,
  RUNNING: LoaderCircle,
  WAITING_REVIEW: CircleSlash,
  COMPLETED: CheckCircle2,
  FAILED: CircleAlert,
  CANCELED: CircleSlash,
}

interface FileOperationProgressProps {
  job: Job
  isCompact?: boolean
}

export function FileOperationProgress({
  job,
  isCompact = false,
}: FileOperationProgressProps) {
  const summaries = readVisibleSummaries(job)
  if (!summaries.length) return null

  return (
    <div
      className={cn(
        'grid gap-2',
        isCompact ? 'text-[0.68rem]' : 'sm:grid-cols-2',
      )}
      aria-live="polite"
      aria-atomic="true"
    >
      {summaries.map(({ operationType, summary }) => (
        <OperationSummary
          key={operationType}
          operationType={operationType}
          summary={summary}
          isCompact={isCompact}
        />
      ))}
    </div>
  )
}

interface OperationSummaryProps {
  operationType: 'COPY' | 'TRASH'
  summary: FileOperationProgressSummary
  isCompact: boolean
}

function OperationSummary({
  operationType,
  summary,
  isCompact,
}: OperationSummaryProps) {
  const presentation = OPERATION_PRESENTATION[operationType]
  const Icon = presentation.icon
  const percentage = calculatePercentage(summary)
  const isRunning = summary.state === 'RUNNING' || summary.state === 'QUEUED'
  const isFailed = summary.failed > 0 || summary.state === 'FAILED'
  const displayState: ProgressState = isFailed ? 'FAILED' : summary.state
  const StateIcon = OPERATION_STATE_ICON[displayState]
  const label = operationStateLabel({
    displayState,
    label: presentation.label,
    activeLabel: presentation.activeLabel,
  })

  if (isCompact) {
    return (
      <span
        className={cn(
          'flex min-w-0 items-center gap-1 text-muted-foreground',
          isFailed && 'text-destructive',
        )}
      >
        <Icon aria-hidden="true" />
        <span>{label}</span>
        <strong className="tabular-nums text-foreground">
          {summary.completed}/{summary.total}
        </strong>
        {summary.failed > 0 ? <span>· {summary.failed} 失败</span> : null}
      </span>
    )
  }

  return (
    <div className="min-w-0 rounded-lg border bg-muted/20 p-2.5">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span
          className={cn(
            'flex min-w-0 items-center gap-1.5 font-medium',
            isFailed && 'text-destructive',
          )}
        >
          <StateIcon
            className={cn(isRunning && 'animate-spin')}
            aria-hidden="true"
          />
          {label}
        </span>
        <strong className="shrink-0 tabular-nums">
          {summary.completed}/{summary.total}
        </strong>
      </div>
      <Progress
        className="mt-2 h-1.5"
        value={percentage}
        aria-label={`${presentation.label} ${summary.completed}/${summary.total}`}
      />
      <p
        className="mt-1.5 truncate text-[0.68rem] text-muted-foreground"
        title={summary.current_filename}
      >
        {summary.current_filename ?? operationResultLabel(summary)}
      </p>
    </div>
  )
}

function readVisibleSummaries(
  job: Job,
): Array<{
  operationType: 'COPY' | 'TRASH'
  summary: FileOperationProgressSummary
}> {
  const operationTypes: Array<'COPY' | 'TRASH'> = ['COPY', 'TRASH']
  return operationTypes.flatMap((operationType) => {
    const summary = job.progress_detail.operations?.[operationType]
    return summary ? [{ operationType, summary }] : []
  })
}

function calculatePercentage(summary: FileOperationProgressSummary): number {
  if (summary.total <= 0) return 0
  return Math.min(PERCENT_SCALE, Math.round((summary.completed / summary.total) * PERCENT_SCALE))
}

function operationResultLabel(summary: FileOperationProgressSummary): string {
  const labels = [
    `${summary.succeeded} 成功`,
    summary.skipped > 0 ? `${summary.skipped} 跳过` : null,
    summary.failed > 0 ? `${summary.failed} 失败` : null,
  ]
  return labels.filter((label): label is string => label !== null).join(' · ')
}

interface OperationStateLabelInput {
  displayState: ProgressState
  label: string
  activeLabel: string
}

function operationStateLabel(input: OperationStateLabelInput): string {
  if (input.displayState === 'CANCELED') return `${input.label}已停止`
  if (input.displayState === 'RUNNING' || input.displayState === 'QUEUED') {
    return input.activeLabel
  }
  return input.label
}
