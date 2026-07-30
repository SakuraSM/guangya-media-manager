import { AlertTriangle } from 'lucide-react'
import type { MediaMatch } from '../types'
import {
  isMetadataPending,
  matchRecognitionMessages,
} from '../utils/matchFailureReasons'

interface RecognitionNoticeProps {
  mediaMatch: MediaMatch
}

export function RecognitionNotice({ mediaMatch }: RecognitionNoticeProps) {
  const messages = matchRecognitionMessages(mediaMatch)
  if (messages.length === 0) return null
  const isPending = isMetadataPending(mediaMatch)

  return (
    <section
      className={`recognition-notice${isPending ? ' recognition-pending' : ''}`}
      aria-labelledby="recognition-notice-title"
    >
      <div>
        <AlertTriangle size={16} aria-hidden="true" />
        <h3 id="recognition-notice-title">
          {isPending ? '识别进度' : '识别说明与失败原因'}
        </h3>
      </div>
      <ul>
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </section>
  )
}
