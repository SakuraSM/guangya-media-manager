import { LoaderCircle } from 'lucide-react'

interface LoadingScreenProps {
  label: string
}

export function LoadingScreen({ label }: LoadingScreenProps) {
  return (
    <div className="loading-screen" role="status" aria-live="polite">
      <LoaderCircle className="spin" size={28} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
