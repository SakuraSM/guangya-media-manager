import { AlertCircle, CheckCircle2, LoaderCircle, PauseCircle } from 'lucide-react'
import type { JobStatus, MatchDecision } from '../types'

type SupportedStatus = JobStatus | MatchDecision

interface StatusDefinition {
  label: string
  tone: 'success' | 'warning' | 'danger' | 'info' | 'neutral'
  icon: typeof CheckCircle2
}

const STATUS_REGISTRY: Record<SupportedStatus, StatusDefinition> = {
  DRAFT: { label: '草稿', tone: 'neutral', icon: PauseCircle },
  SCANNING: { label: '扫描中', tone: 'info', icon: LoaderCircle },
  IDENTIFYING: { label: '识别中', tone: 'info', icon: LoaderCircle },
  REVIEW_REQUIRED: { label: '等待审核', tone: 'warning', icon: AlertCircle },
  READY: { label: '可以执行', tone: 'success', icon: CheckCircle2 },
  COPYING: { label: '复制中', tone: 'info', icon: LoaderCircle },
  SCRAPING: { label: '刮削中', tone: 'info', icon: LoaderCircle },
  FINALIZING: { label: '收尾中', tone: 'info', icon: LoaderCircle },
  COMPLETED: { label: '已完成', tone: 'success', icon: CheckCircle2 },
  PARTIAL_FAILED: { label: '部分失败', tone: 'danger', icon: AlertCircle },
  FAILED: { label: '失败', tone: 'danger', icon: AlertCircle },
  CANCELED: { label: '已停止', tone: 'neutral', icon: PauseCircle },
  AUTO_APPROVED: { label: '自动通过', tone: 'success', icon: CheckCircle2 },
  APPROVED: { label: '已通过', tone: 'success', icon: CheckCircle2 },
  REVIEW: { label: '需要审核', tone: 'warning', icon: AlertCircle },
  IGNORED: { label: '已忽略', tone: 'neutral', icon: PauseCircle },
  UNRESOLVED: { label: '未识别', tone: 'danger', icon: AlertCircle },
}

interface StatusBadgeProps {
  status: SupportedStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const definition = STATUS_REGISTRY[status]
  const Icon = definition.icon
  const isAnimated = ['SCANNING', 'IDENTIFYING', 'COPYING', 'SCRAPING', 'FINALIZING'].includes(
    status,
  )
  return (
    <span className={`status-badge status-${definition.tone}`}>
      <Icon className={isAnimated ? 'spin' : ''} size={14} aria-hidden="true" />
      {definition.label}
    </span>
  )
}
