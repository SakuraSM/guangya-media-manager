import type { Job } from '../types'
import { ReviewCommandBar } from './ReviewCommandBar'

interface ReviewPageHeaderProps {
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
  actionMessage: string
  onApproveGroup: () => void
  onApproveSelection: () => void
  onExecute: () => void
  onCancel: () => void
}

export function ReviewPageHeader({
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
  actionMessage,
  onApproveGroup,
  onApproveSelection,
  onExecute,
  onCancel,
}: ReviewPageHeaderProps) {
  const handleJobChange = (jobId: string) => {
    window.location.assign(`/review?job=${encodeURIComponent(jobId)}`)
  }

  return (
    <>
      <ReviewCommandBar
        jobs={jobs}
        job={job}
        selectedJobId={selectedJobId}
        canApproveGroup={canApproveGroup}
        canApproveSelection={canApproveSelection}
        selectedCount={selectedCount}
        isApprovingGroup={isApprovingGroup}
        isApprovingSelection={isApprovingSelection}
        isExecuting={isExecuting}
        isCancelling={isCancelling}
        onJobChange={handleJobChange}
        onApproveGroup={onApproveGroup}
        onApproveSelection={onApproveSelection}
        onExecute={onExecute}
        onCancel={onCancel}
      />
      {actionMessage ? (
        <p className="action-success" role="status">
          {actionMessage}
        </p>
      ) : null}
    </>
  )
}
