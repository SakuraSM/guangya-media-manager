import { Button } from '@/components/ui/button'
import { REVIEW_FILTER, type ReviewFilter } from '@/types'
import { cn } from '@/lib/utils'

const REVIEW_FILTER_ITEMS: ReadonlyArray<{
  value: ReviewFilter
  label: string
}> = [
  { value: REVIEW_FILTER.PENDING, label: '待审核' },
  { value: REVIEW_FILTER.REVIEWED, label: '已审核' },
  { value: REVIEW_FILTER.ALL, label: '全部' },
]

interface ReviewFilterControlProps {
  value: ReviewFilter
  isLoading: boolean
  onChange: (value: ReviewFilter) => void
}

export function ReviewFilterControl({
  value,
  isLoading,
  onChange,
}: ReviewFilterControlProps) {
  return (
    <div
      className="flex shrink-0 items-center rounded-lg border bg-muted/40 p-0.5"
      role="group"
      aria-label="筛选审核状态"
      aria-busy={isLoading}
    >
      {REVIEW_FILTER_ITEMS.map((item) => (
        <Button
          key={item.value}
          type="button"
          size="sm"
          variant="ghost"
          className={cn(
            'h-7 px-2 text-xs',
            value === item.value && 'bg-background text-foreground shadow-sm',
          )}
          aria-pressed={value === item.value}
          disabled={isLoading}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </Button>
      ))}
    </div>
  )
}
