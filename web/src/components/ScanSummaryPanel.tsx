import { useMemo, useState } from 'react'
import {
  ChevronDown,
  CircleSlash,
  FileSearch,
  Film,
  Languages,
  RotateCcw,
} from 'lucide-react'
import {
  type SourceAction,
  type SourceClassification,
  type SourceItem,
} from '@/types'
import { formatBytes } from '@/utils/format'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'

const CLASSIFICATION_LABELS: Record<SourceClassification, string> = {
  MEDIA: '正片/剧集',
  SUBTITLE: '字幕',
  EXTRA: '附加视频',
  EXISTING_ASSET: '已有素材',
  IGNORED: '已过滤',
  UNKNOWN: '待判断',
}

interface ScanSummaryPanelProps {
  items: SourceItem[]
  isSaving: boolean
  onChangeAction: (itemId: string, action: SourceAction) => void
}

export function ScanSummaryPanel({ items, isSaving, onChangeAction }: ScanSummaryPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const counts = useMemo(() => countClassifications(items), [items])
  const reviewableItems = useMemo(
    () => items.filter((item) => item.is_reviewable),
    [items],
  )

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="gap-0 py-0">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
          >
            <div className="min-w-0">
              <h2 className="text-sm font-medium">扫描分类与过滤</h2>
              <p className="mt-1 truncate text-xs text-muted-foreground">
                媒体 {counts.MEDIA} · 字幕 {counts.SUBTITLE} · 附加内容 {counts.EXTRA} ·
                已过滤/素材 {counts.IGNORED + counts.EXISTING_ASSET}
              </p>
            </div>
            <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
              <FileSearch aria-hidden="true" />
              查看扫描项
              <ChevronDown
                className={cn('transition-transform', isOpen && 'rotate-180')}
                aria-hidden="true"
              />
            </span>
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="border-t py-4">
            <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <SummaryMetric icon={Film} label="媒体" value={counts.MEDIA} />
              <SummaryMetric icon={Languages} label="字幕" value={counts.SUBTITLE} />
              <SummaryMetric icon={RotateCcw} label="附加内容" value={counts.EXTRA} />
              <SummaryMetric
                icon={CircleSlash}
                label="已过滤/素材"
                value={counts.IGNORED + counts.EXISTING_ASSET}
              />
            </dl>
            {reviewableItems.length ? (
              <div className="mt-4 max-h-64 overflow-auto rounded-lg border">
                <div className="border-b bg-muted/40 px-3 py-2 text-xs font-medium">
                  可人工恢复的内容
                </div>
                <ul className="divide-y">
                  {reviewableItems.map((item) => (
                    <li className="flex items-center gap-3 p-3" key={item.id}>
                      <span className="min-w-0 flex-1">
                        <strong className="block truncate text-sm font-medium">
                          {item.relative_path || item.filename}
                        </strong>
                        <small className="block truncate text-xs text-muted-foreground">
                          {CLASSIFICATION_LABELS[item.classification]} · {item.filter_reason} ·{' '}
                          {formatBytes(item.size_bytes)}
                        </small>
                      </span>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isSaving}
                        onClick={() =>
                          onChangeAction(
                            item.id,
                            item.user_action === 'INCLUDE' ? 'DEFAULT' : 'INCLUDE',
                          )
                        }
                      >
                        {item.user_action === 'INCLUDE' ? '恢复默认排除' : '标记为包含'}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}

function SummaryMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Film
  label: string
  value: number
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-muted/20 p-3">
      <span className="grid size-8 place-items-center rounded-lg bg-accent text-accent-foreground">
        <Icon aria-hidden="true" />
      </span>
      <div>
        <dt className="text-xs text-muted-foreground">{label}</dt>
        <dd className="text-base font-semibold tabular-nums">{value}</dd>
      </div>
    </div>
  )
}

function countClassifications(items: SourceItem[]): Record<SourceClassification, number> {
  const counts: Record<SourceClassification, number> = {
    MEDIA: 0,
    SUBTITLE: 0,
    EXTRA: 0,
    EXISTING_ASSET: 0,
    IGNORED: 0,
    UNKNOWN: 0,
  }
  for (const item of items) {
    counts[item.classification] += 1
  }
  return counts
}
