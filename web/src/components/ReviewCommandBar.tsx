import {
  ArrowRight,
  Bot,
  CheckCircle2,
  CircleSlash,
  FolderInput,
  FolderOutput,
  ListChecks,
  Play,
  Sparkles,
  StopCircle,
  TriangleAlert,
} from 'lucide-react'
import { PERCENT_SCALE } from '../constants'
import { JOB_STATUS, type Job, type JobStatus } from '../types'
import { formatBytes } from '../utils/format'
import { StatusBadge } from './StatusBadge'

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
  onJobChange: (jobId: string) => void
  onApproveGroup: () => void
  onApproveSelection: () => void
  onExecute: () => void
  onCancel: () => void
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
  onJobChange,
  onApproveGroup,
  onApproveSelection,
  onExecute,
  onCancel,
}: ReviewCommandBarProps) {
  const handleJobChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    onJobChange(event.target.value)
  }
  const canCancel = !NON_CANCELABLE_STATUSES.has(job.status)
  const isRetryingBatch =
    job.status === JOB_STATUS.PARTIAL_FAILED &&
    (job.failed_items > 0 || Boolean(job.error_message))
  const canExecute = job.status === JOB_STATUS.READY || isRetryingBatch
  const progressPercentage = Math.round(job.progress * PERCENT_SCALE)

  return (
    <section className="review-command-bar">
      <div className="review-task-context">
        <div className="review-task-selector">
          <span>审核任务</span>
          <select
            value={selectedJobId}
            onChange={handleJobChange}
            aria-label="选择审核任务"
          >
            {jobs.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <StatusBadge status={job.status} />
      </div>
      <div className="review-route" aria-label="整理路径">
        <div>
          <span><FolderInput size={13} aria-hidden="true" />源目录</span>
          <strong title={job.source_directory_path}>{job.source_directory_path}</strong>
        </div>
        <ArrowRight size={16} aria-hidden="true" />
        <div>
          <span><FolderOutput size={13} aria-hidden="true" />目标目录</span>
          <strong title={job.target_directory_path}>{job.target_directory_path}</strong>
        </div>
      </div>
      <div className="review-automation" aria-label="自动化策略">
        <span className={job.auto_approve_enabled ? 'automation-on' : ''}>
          <Sparkles size={14} aria-hidden="true" />
          TMDB 自动审批 {job.auto_approve_enabled ? '开启' : '关闭'}
        </span>
        <span className={job.auto_execute_after_approval ? 'automation-on' : ''}>
          <Bot size={14} aria-hidden="true" />
          审批后自动整理 {job.auto_execute_after_approval ? '开启' : '关闭'}
        </span>
      </div>
      <div className="review-progress-summary">
        <div>
          <span>{job.current_stage || '等待处理'}</span>
          <strong>{progressPercentage}%</strong>
        </div>
        <div
          className="progress-track progress-track-small"
          role="progressbar"
          aria-label={`任务进度 ${progressPercentage}%`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progressPercentage}
        >
          <span style={{ width: `${progressPercentage}%` }} />
        </div>
        <small>已复制 {formatBytes(job.copied_bytes)}</small>
      </div>
      <div className="review-summary" aria-label="审核统计">
        <span>
          <CheckCircle2 size={15} /> {job.approved_items} 已通过
        </span>
        <span>
          <TriangleAlert size={15} /> {job.review_items} 需要审核
        </span>
        <span>
          <CircleSlash size={15} /> {job.failed_items} 失败
        </span>
      </div>
      <div className="review-command-actions">
        <button
          className="button button-primary"
          type="button"
          disabled={!canApproveSelection || isApprovingSelection}
          onClick={onApproveSelection}
        >
          <ListChecks size={16} aria-hidden="true" />
          {isApprovingSelection
            ? '正在批量批准'
            : `批准已选（${selectedCount}）`}
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={!canApproveGroup || isApprovingGroup}
          onClick={onApproveGroup}
        >
          <CheckCircle2 size={16} aria-hidden="true" />
          批准当前整组
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={!canCancel || isCancelling || job.is_cancel_requested}
          onClick={onCancel}
        >
          <StopCircle size={16} aria-hidden="true" />
          {job.is_cancel_requested ? '已请求取消' : '取消任务'}
        </button>
        <button
          className="button button-primary"
          type="button"
          disabled={!canExecute || isExecuting}
          onClick={onExecute}
        >
          <Play size={16} aria-hidden="true" />
          {isExecuting
            ? '正在提交整批任务'
            : isRetryingBatch
              ? '重试整批执行'
              : '确认并整批执行'}
        </button>
      </div>
    </section>
  )
}
