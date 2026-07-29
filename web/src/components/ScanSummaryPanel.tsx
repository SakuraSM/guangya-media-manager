import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { CircleSlash, FileSearch, Film, Languages, RotateCcw } from 'lucide-react'
import {
  type SourceAction,
  type SourceClassification,
  type SourceItem,
} from '../types'
import { formatBytes } from '../utils/format'

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

export function ScanSummaryPanel({
  items,
  isSaving,
  onChangeAction,
}: ScanSummaryPanelProps) {
  const counts = useMemo(() => countClassifications(items), [items])
  const reviewableItems = useMemo(
    () => items.filter((item) => item.is_reviewable),
    [items],
  )

  return (
    <section className="scan-summary-panel" aria-labelledby="scan-summary-title">
      <div className="section-heading">
        <div>
          <h2 id="scan-summary-title">预扫描分类</h2>
          <p>所有文件均保留分类和过滤原因，源目录不会被修改。</p>
        </div>
        <FileSearch size={20} aria-hidden="true" />
      </div>
      <dl className="scan-summary-grid">
        <SummaryMetric
          icon={<Film size={17} aria-hidden="true" />}
          label="媒体"
          value={counts.MEDIA}
        />
        <SummaryMetric
          icon={<Languages size={17} aria-hidden="true" />}
          label="字幕"
          value={counts.SUBTITLE}
        />
        <SummaryMetric
          icon={<RotateCcw size={17} aria-hidden="true" />}
          label="附加内容"
          value={counts.EXTRA}
        />
        <SummaryMetric
          icon={<CircleSlash size={17} aria-hidden="true" />}
          label="已过滤/素材"
          value={counts.IGNORED + counts.EXISTING_ASSET}
        />
      </dl>
      {reviewableItems.length ? (
        <div className="filtered-items">
          <h3>可人工恢复的内容</h3>
          <ul>
            {reviewableItems.map((item) => (
              <li key={item.id}>
                <span>
                  <strong>{item.relative_path || item.filename}</strong>
                  <small>
                    {CLASSIFICATION_LABELS[item.classification]} · {item.filter_reason} ·{' '}
                    {formatBytes(item.size_bytes)}
                  </small>
                </span>
                <button
                  type="button"
                  className="button button-secondary"
                  disabled={isSaving}
                  onClick={() =>
                    onChangeAction(
                      item.id,
                      item.user_action === 'INCLUDE' ? 'DEFAULT' : 'INCLUDE',
                    )
                  }
                >
                  {item.user_action === 'INCLUDE' ? '恢复默认排除' : '标记为包含'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

interface SummaryMetricProps {
  icon: ReactNode
  label: string
  value: number
}

function SummaryMetric({ icon, label, value }: SummaryMetricProps) {
  return (
    <div>
      <dt>
        {icon}
        {label}
      </dt>
      <dd>{value}</dd>
    </div>
  )
}

function countClassifications(
  items: SourceItem[],
): Record<SourceClassification, number> {
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
