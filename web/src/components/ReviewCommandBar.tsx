import {
  CheckCircle2,
  CircleSlash,
  ListChecks,
  Play,
  StopCircle,
  TriangleAlert,
} from 'lucide-react'
import { JOB_STATUS, type Job, type JobStatus } from '../types'

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

  return (
    <section className="review-command-bar">
      <div>
        <span>当前任务</span>
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
      <div className="review-summary">
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
        disabled={job.status !== JOB_STATUS.READY || isExecuting}
        onClick={onExecute}
      >
        <Play size={16} aria-hidden="true" />
        确认并执行
      </button>
    </section>
  )
}
