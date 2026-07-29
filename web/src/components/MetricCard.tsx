import type { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  label: string
  value: string
  detail: string
  icon: LucideIcon
  tone: 'blue' | 'green' | 'amber' | 'red'
}

export function MetricCard({ label, value, detail, icon: Icon, tone }: MetricCardProps) {
  return (
    <article className={`metric metric-${tone}`}>
      <span className="metric-icon" aria-hidden="true">
        <Icon size={19} />
      </span>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  )
}
