import type { LucideIcon } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  value: string
  detail: string
  icon: LucideIcon
  tone: 'blue' | 'green' | 'amber' | 'red'
}

const TONE_CLASSES = {
  blue: 'bg-info/10 text-info',
  green: 'bg-success/10 text-success',
  amber: 'bg-warning/10 text-warning',
  red: 'bg-destructive/10 text-destructive',
} as const

export function MetricCard({ label, value, detail, icon: Icon, tone }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <CardDescription>{label}</CardDescription>
          <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
        </div>
        <span className={cn('grid size-9 place-items-center rounded-xl', TONE_CLASSES[tone])}>
          <Icon aria-hidden="true" />
        </span>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  )
}
