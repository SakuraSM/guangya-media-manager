import { AlertTriangle, LoaderCircle } from 'lucide-react'
import type { MediaMatch } from '@/types'
import { isMetadataPending, matchRecognitionMessages } from '@/utils/matchFailureReasons'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

interface RecognitionNoticeProps {
  mediaMatch: MediaMatch
}

export function RecognitionNotice({ mediaMatch }: RecognitionNoticeProps) {
  const decisionReasons = mediaMatch.decision_reasons ?? []
  const messages = matchRecognitionMessages(mediaMatch)
  if (messages.length === 0 && decisionReasons.length === 0) return null
  const isPending = isMetadataPending(mediaMatch)
  const isBlocking = decisionReasons.some((reason) => reason.severity === 'BLOCKING')

  return (
    <Alert variant={isPending || (!isBlocking && decisionReasons.length > 0) ? 'default' : 'destructive'}>
      {isPending ? (
        <LoaderCircle className="animate-spin" aria-hidden="true" />
      ) : (
        <AlertTriangle aria-hidden="true" />
      )}
      <AlertTitle>
        {isPending ? '识别进度' : decisionReasons.length ? '审批依据' : '识别说明与失败原因'}
      </AlertTitle>
      <AlertDescription>
        <ul className="flex list-disc flex-col gap-1 pl-4">
          {decisionReasons.map((reason) => (
            <li key={`${reason.code}-${reason.origin}`}>{reason.message}</li>
          ))}
          {messages.map((message) => <li key={message}>{message}</li>)}
        </ul>
      </AlertDescription>
    </Alert>
  )
}
