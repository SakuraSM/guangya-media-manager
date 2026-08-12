import type { Job } from '../types'
import { ReviewCommandBar } from './ReviewCommandBar'
import { CheckCircle2 } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { EventStreamState } from '@/hooks/useJobEventStream'

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
  canStartAiReview: boolean
  isStartingAiReview: boolean
  actionMessage: string
  connectionState: EventStreamState
  isFollowingProgress: boolean
  onResumeFollowing: () => void
  isProcessingOtherPage: boolean
  onApproveGroup: () => void
  onApproveSelection: () => void
  onExecute: () => void
  onCancel: () => void
  onStartAiReview: () => void
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
  canStartAiReview,
  isStartingAiReview,
  actionMessage,
  connectionState,
  isFollowingProgress,
  onResumeFollowing,
  isProcessingOtherPage,
  onApproveGroup,
  onApproveSelection,
  onExecute,
  onCancel,
  onStartAiReview,
}: ReviewPageHeaderProps) {
  const handleJobChange = (jobId: string) => {
    window.location.assign(`/review?job=${encodeURIComponent(jobId)}`)
  }

  return (
    <div className="flex flex-col gap-3">
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
        canStartAiReview={canStartAiReview}
        isStartingAiReview={isStartingAiReview}
        onJobChange={handleJobChange}
        onApproveGroup={onApproveGroup}
        onApproveSelection={onApproveSelection}
        onExecute={onExecute}
        onCancel={onCancel}
        onStartAiReview={onStartAiReview}
        connectionState={connectionState}
        isFollowingProgress={isFollowingProgress}
        onResumeFollowing={onResumeFollowing}
        isProcessingOtherPage={isProcessingOtherPage}
      />
      {actionMessage ? (
        <Alert className="border-success/20 bg-success/5 text-success" role="status">
          <CheckCircle2 aria-hidden="true" />
          <AlertDescription className="text-success">{actionMessage}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
