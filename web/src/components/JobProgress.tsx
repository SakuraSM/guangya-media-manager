import { BrainCircuit, Check, Copy, Database, FolderSearch, Link2 } from 'lucide-react'
import type { Job } from '@/types'
import { PERCENT_SCALE } from '@/constants'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

const STAGES = [
  { label: '扫描', icon: FolderSearch, boundary: 0.18 },
  { label: '识别', icon: BrainCircuit, boundary: 0.38 },
  { label: '匹配', icon: Link2, boundary: 0.5 },
  { label: '复制', icon: Copy, boundary: 0.85 },
  { label: '刮削', icon: Database, boundary: 1 },
] as const

interface JobProgressProps {
  job: Job
}

export function JobProgress({ job }: JobProgressProps) {
  const progress = Math.round(job.progress * PERCENT_SCALE)
  return (
    <Card aria-labelledby="active-job-title">
      <CardHeader className="gap-3">
        <Badge variant="secondary" className="w-fit">
          <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />
          正在整理
        </Badge>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <CardTitle id="active-job-title" className="truncate text-lg">
              {job.name}
            </CardTitle>
            <CardDescription className="mt-1 line-clamp-2">
              {job.source_directory_path} → {job.target_directory_path}
            </CardDescription>
          </div>
          <div className="shrink-0 text-right">
            <strong className="block text-2xl tabular-nums">{progress}%</strong>
            <span className="text-xs text-muted-foreground">{job.current_stage}</span>
          </div>
        </div>
        <Progress value={progress} aria-label={`任务进度 ${progress}%`} />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-5 gap-2">
          {STAGES.map((stage, index) => {
            const Icon = stage.icon
            const isComplete = job.progress >= stage.boundary
            const previousBoundary = STAGES[Math.max(0, index - 1)]?.boundary ?? 0
            const isActive = !isComplete && job.progress >= previousBoundary
            return (
              <div
                className={cn(
                  'flex min-w-0 flex-col items-center gap-2 rounded-lg border p-2 text-center',
                  isComplete && 'border-success/30 bg-success/5 text-success',
                  isActive && 'border-primary/30 bg-primary/5 text-primary',
                )}
                key={stage.label}
              >
                <span className="grid size-8 place-items-center rounded-full bg-muted">
                  {isComplete ? <Check aria-hidden="true" /> : <Icon aria-hidden="true" />}
                </span>
                <strong className="text-xs">{stage.label}</strong>
                <small className="hidden text-[0.65rem] text-muted-foreground sm:block">
                  {isComplete ? '已完成' : isActive ? '进行中' : '等待中'}
                </small>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
