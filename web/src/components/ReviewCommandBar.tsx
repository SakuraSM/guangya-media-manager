import { useState } from 'react'
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleSlash,
  FolderInput,
  FolderOutput,
  ListChecks,
  Play,
  Sparkles,
  StopCircle,
  TriangleAlert,
  Radio,
} from 'lucide-react'
import { PERCENT_SCALE } from '@/constants'
import { JOB_STATUS, type Job, type JobStatus } from '@/types'
import { formatBytes } from '@/utils/format'
import { StatusBadge } from '@/components/StatusBadge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { EventStreamState } from '@/hooks/useJobEventStream'

const NON_CANCELABLE_STATUSES: ReadonlySet<JobStatus> = new Set([
  JOB_STATUS.COMPLETED,
  JOB_STATUS.PARTIAL_FAILED,
  JOB_STATUS.FAILED,
  JOB_STATUS.CANCELED,
])

interface ReviewCommandBarProps {
  jobs: Job[]
  job: Job
  selectedJobId: string
  canApproveGroup: boolean
  canApproveSelection: boolean
  selectedCount: number
  isApprovingGroup: boolean
  isApprovingSelection: boolean
  isExecuting: boolean
  isCancelling: boolean
  canStartAiReview: boolean
  isStartingAiReview: boolean
  onJobChange: (jobId: string) => void
  onApproveGroup: () => void
  onApproveSelection: () => void
  onExecute: () => void
  onCancel: () => void
  onStartAiReview: () => void
  connectionState: EventStreamState
  isFollowingProgress: boolean
  onResumeFollowing: () => void
  isProcessingOtherPage: boolean
}

export function ReviewCommandBar({
  jobs,
  job,
  selectedJobId,
  canApproveGroup,
  canApproveSelection,
  selectedCount,
  isApprovingGroup,
  isApprovingSelection,
  isExecuting,
  isCancelling,
  canStartAiReview,
  isStartingAiReview,
  onJobChange,
  onApproveGroup,
  onApproveSelection,
  onExecute,
  onCancel,
  onStartAiReview,
  connectionState,
  isFollowingProgress,
  onResumeFollowing,
  isProcessingOtherPage,
}: ReviewCommandBarProps) {
  const [isMobileSummaryOpen, setIsMobileSummaryOpen] = useState(false)
  const canCancel = !NON_CANCELABLE_STATUSES.has(job.status)
  const isRetryingBatch =
    job.status === JOB_STATUS.PARTIAL_FAILED &&
    (job.failed_items > 0 || Boolean(job.error_message))
  const canExecute = job.status === JOB_STATUS.READY || isRetryingBatch
  const progressPercentage = Math.round(job.progress * PERCENT_SCALE)
  const isSelectionApproval = selectedCount > 0
  const canApproveContext = isSelectionApproval
    ? canApproveSelection
    : canApproveGroup
  const isApprovingContext = isSelectionApproval
    ? isApprovingSelection
    : isApprovingGroup

  return (
    <Card className="gap-0 py-0">
      <CardContent className="grid gap-3 p-3 sm:p-4 md:grid-cols-[minmax(15rem,0.9fr)_minmax(20rem,1.1fr)] xl:grid-cols-[minmax(16rem,0.8fr)_minmax(22rem,1.4fr)_minmax(18rem,1fr)]">
        <div className="flex min-w-0 flex-col gap-2 sm:gap-3">
          <div className="flex items-center gap-2">
            <Select value={selectedJobId} onValueChange={onJobChange}>
              <SelectTrigger className="min-w-0 flex-1" aria-label="选择审核任务">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {jobs.map((item) => (
                    <SelectItem value={item.id} key={item.id}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <StatusBadge status={job.status} />
          </div>
          <div className="hidden flex-wrap gap-2 sm:flex">
            <Badge variant="outline" className={job.auto_approve_enabled ? 'text-success' : undefined}>
              <Sparkles aria-hidden="true" />
              TMDB 自动审批 {job.auto_approve_enabled ? '开启' : '关闭'}
            </Badge>
            <Badge variant="outline" className={job.auto_execute_after_approval ? 'text-success' : undefined}>
              <Bot aria-hidden="true" />
              审批后自动整理 {job.auto_execute_after_approval ? '开启' : '关闭'}
            </Badge>
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1 text-success">
              <CheckCircle2 aria-hidden="true" /> {job.approved_items} 已通过
            </span>
            <span className="flex items-center gap-1 text-warning">
              <TriangleAlert aria-hidden="true" /> {job.review_items} 需要审核
            </span>
            <span className="flex items-center gap-1 text-destructive">
              <CircleSlash aria-hidden="true" /> {job.failed_items} 失败
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs" aria-live="polite">
            <Badge variant="outline" className={connectionState === 'CONNECTED' ? 'text-success' : 'text-warning'}>
              <Radio aria-hidden="true" />
              {connectionState === 'CONNECTED' ? '实时连接' : connectionState === 'CONNECTING' ? '正在连接' : '轮询恢复'}
            </Badge>
            {!isFollowingProgress ? (
              <Button variant="ghost" size="sm" type="button" onClick={onResumeFollowing}>
                恢复跟随
              </Button>
            ) : null}
            {isProcessingOtherPage ? (
              <span className="text-muted-foreground">正在处理其他分页中的记录</span>
            ) : null}
          </div>
        </div>

        <div className="hidden min-w-0 flex-col gap-3 sm:flex">
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 rounded-lg border bg-muted/20 p-3">
            <RoutePath icon={FolderInput} label="源目录" path={job.source_directory_path} />
            <ArrowRight className="text-muted-foreground" aria-hidden="true" />
            <RoutePath icon={FolderOutput} label="目标目录" path={job.target_directory_path} />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{job.current_stage || '等待处理'}</span>
              <strong className="tabular-nums">{progressPercentage}%</strong>
            </div>
            <Progress value={progressPercentage} aria-label={`任务进度 ${progressPercentage}%`} />
            <small className="mt-2 block text-xs text-muted-foreground">
              {progressDetailLabel(job)} · 已复制 {formatBytes(job.copied_bytes)}
            </small>
          </div>
        </div>

        <Collapsible
          open={isMobileSummaryOpen}
          onOpenChange={setIsMobileSummaryOpen}
          className="sm:hidden"
        >
          <CollapsibleTrigger asChild>
            <Button variant="ghost" type="button" className="w-full justify-between px-2">
              <span>任务路径与自动化设置</span>
              <ChevronDown
                className={cn('transition-transform', isMobileSummaryOpen && 'rotate-180')}
                aria-hidden="true"
              />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 space-y-3 rounded-lg border bg-muted/20 p-3">
              <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
                <RoutePath icon={FolderInput} label="源目录" path={job.source_directory_path} />
                <ArrowRight className="text-muted-foreground" aria-hidden="true" />
                <RoutePath icon={FolderOutput} label="目标目录" path={job.target_directory_path} />
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className={job.auto_approve_enabled ? 'text-success' : undefined}>
                  <Sparkles aria-hidden="true" />
                  自动审批 {job.auto_approve_enabled ? '开启' : '关闭'}
                </Badge>
                <Badge variant="outline" className={job.auto_execute_after_approval ? 'text-success' : undefined}>
                  <Bot aria-hidden="true" />
                  自动整理 {job.auto_execute_after_approval ? '开启' : '关闭'}
                </Badge>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>

        <div className="grid grid-cols-2 items-center gap-2 self-center sm:flex sm:flex-wrap sm:justify-end md:col-span-2 xl:col-span-1">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="outline"
                type="button"
                className="w-full sm:w-auto"
                disabled={!canStartAiReview || isStartingAiReview}
              >
                <Bot data-icon="inline-start" aria-hidden="true" />
                {isStartingAiReview ? 'AI 正在审核' : 'AI 审核待确认项'}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>授权 AI 审核作品名称？</AlertDialogTitle>
                <AlertDialogDescription asChild>
                  <div className="space-y-3 text-sm leading-relaxed">
                    <p>
                      AI 会按影视分组对比父目录、文件名和 TMDB 候选，只在作品名称与电影/电视剧类型明确一致时批准。
                    </p>
                    <ul className="list-disc space-y-1 pl-5">
                      <li>不会判断季号、集号、单集标题或单集顺序。</li>
                      <li>已经通过的高置信记录不会重复处理。</li>
                      <li>证据不足或审核失败的分组会保留，继续由你手动确认。</li>
                    </ul>
                  </div>
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>暂不审核</AlertDialogCancel>
                <AlertDialogAction onClick={onStartAiReview}>
                  开始 AI 审核
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button
            variant="outline"
            type="button"
            className="w-full sm:w-auto"
            disabled={!canApproveContext || isApprovingContext}
            onClick={isSelectionApproval ? onApproveSelection : onApproveGroup}
          >
            {isSelectionApproval ? (
              <ListChecks data-icon="inline-start" aria-hidden="true" />
            ) : (
              <CheckCircle2 data-icon="inline-start" aria-hidden="true" />
            )}
            {isApprovingContext
              ? '正在批准'
              : isSelectionApproval
                ? `批准已选（${selectedCount}）`
                : '批准当前整组'}
          </Button>
          <Button className="w-full sm:w-auto" type="button" disabled={!canExecute || isExecuting} onClick={onExecute}>
            <Play data-icon="inline-start" aria-hidden="true" />
            {isExecuting
              ? '正在提交整批任务'
              : isRetryingBatch
                ? '重试整批执行'
                : '确认并整批执行'}
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                type="button"
                className="w-full sm:w-auto"
                disabled={!canCancel || isCancelling || job.is_cancel_requested}
              >
                <StopCircle data-icon="inline-start" aria-hidden="true" />
                {job.is_cancel_requested ? '已请求取消' : '取消任务'}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确认取消当前整理任务？</AlertDialogTitle>
                <AlertDialogDescription>
                  系统会安全停止后续操作，已完成的复制不会回滚，暂存内容不会自动删除。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>继续任务</AlertDialogCancel>
                <AlertDialogAction onClick={onCancel}>确认取消</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  )
}

function RoutePath({
  icon: Icon,
  label,
  path,
}: {
  icon: typeof FolderInput
  label: string
  path: string
}) {
  return (
    <div className="min-w-0">
      <span className="mb-1 flex items-center gap-1 text-[0.65rem] text-muted-foreground">
        <Icon aria-hidden="true" />
        {label}
      </span>
      <strong className="block truncate text-xs font-medium" title={path}>{path}</strong>
    </div>
  )
}

function progressDetailLabel(job: Job): string {
  const completed = job.progress_detail.completed ?? 0
  const total = job.progress_detail.total ?? 0
  if (total <= 0) return job.progress_detail.message ?? '等待进度数据'
  return `已处理 ${completed}/${total} · 成功 ${job.progress_detail.succeeded ?? 0} · 失败 ${job.progress_detail.failed ?? 0}`
}
