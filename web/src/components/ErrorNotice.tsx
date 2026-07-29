import { AlertTriangle } from 'lucide-react'

interface ErrorNoticeProps {
  message: string
}

export function ErrorNotice({ message }: ErrorNoticeProps) {
  return (
    <div className="error-notice" role="alert">
      <AlertTriangle size={18} aria-hidden="true" />
      <span>{message}</span>
    </div>
  )
}
