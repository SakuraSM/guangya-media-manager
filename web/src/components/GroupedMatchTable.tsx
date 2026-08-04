import { LoaderCircle } from 'lucide-react'
import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { AUTO_APPROVE_THRESHOLD, REVIEW_THRESHOLD } from '@/constants'
import type { MediaMatch, ReviewFilter } from '@/types'
import { formatConfidence } from '@/utils/format'
import { isMetadataPending, matchRecognitionMessages } from '@/utils/matchFailureReasons'
import {
  episodeLabel,
  isBatchApprovableMatch,
  type MediaMatchGroup,
} from '@/utils/reviewGrouping'
import { OriginalFileInfo } from '@/components/OriginalFileInfo'
import { ReviewFilterControl } from '@/components/ReviewFilterControl'
import { Poster } from '@/components/Poster'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

interface GroupedMatchTableProps {
  groups: MediaMatchGroup[]
  selectedMatchId: string | null
  selectedMatchIds: ReadonlySet<string>
  isSelectionEnabled: boolean
  reviewFilter: ReviewFilter
  isFilterLoading: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
  onToggleSelection: (matchId: string) => void
  onTogglePageSelection: () => void
  onReviewFilterChange: (value: ReviewFilter) => void
  leadingAction?: ReactNode
}

export function GroupedMatchTable({
  groups,
  selectedMatchId,
  selectedMatchIds,
  isSelectionEnabled,
  reviewFilter,
  isFilterLoading,
  onSelectMatch,
  onToggleSelection,
  onTogglePageSelection,
  onReviewFilterChange,
  leadingAction,
}: GroupedMatchTableProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const visibleMatchKey = groups
    .flatMap((group) => group.items)
    .map((mediaMatch) => mediaMatch.id)
    .join('|')
  const approvableMatches = groups
    .flatMap((group) => group.items)
    .filter(isBatchApprovableMatch)
  const areAllApprovableSelected =
    approvableMatches.length > 0 &&
    approvableMatches.every((mediaMatch) => selectedMatchIds.has(mediaMatch.id))
  useLayoutEffect(() => {
    const viewport = viewportRef.current
    if (!viewport || !selectedMatchId) return
    const selectedRow = Array.from(
      viewport.querySelectorAll<HTMLElement>('[data-match-id]'),
    ).find((row) => row.dataset.matchId === selectedMatchId)
    if (!selectedRow) return

    const viewportBounds = viewport.getBoundingClientRect()
    const rowBounds = selectedRow.getBoundingClientRect()
    let scrollOffset = 0
    if (rowBounds.top < viewportBounds.top) {
      scrollOffset = rowBounds.top - viewportBounds.top
    } else if (rowBounds.bottom > viewportBounds.bottom) {
      scrollOffset = rowBounds.bottom - viewportBounds.bottom
    }
    if (scrollOffset === 0) return

    const shouldReduceMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const behavior = shouldReduceMotion ? 'auto' : 'smooth'
    const targetTop = viewport.scrollTop + scrollOffset
    if (typeof viewport.scrollTo === 'function') {
      viewport.scrollTo({ top: targetTop, behavior })
      return
    }
    viewport.scrollTop = targetTop
  }, [selectedMatchId, visibleMatchKey])

  return (
    <section className="flex h-full min-h-0 flex-col bg-card" aria-labelledby="match-table-title">
      <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b px-3">
        <div className="flex min-w-0 items-center gap-2">
          {leadingAction}
          <h2 id="match-table-title" className="hidden truncate text-sm font-medium 2xl:block">
            TMDB 优先识别
          </h2>
          <ReviewFilterControl
            value={reviewFilter}
            isLoading={isFilterLoading}
            onChange={onReviewFilterChange}
          />
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Checkbox
            checked={areAllApprovableSelected}
            disabled={!isSelectionEnabled || approvableMatches.length === 0}
            onCheckedChange={onTogglePageSelection}
          />
          选择本页可批准项
        </label>
      </div>
      <ScrollArea className="min-h-0 flex-1" viewportRef={viewportRef}>
        {groups.map((group) => (
          <section key={group.key}>
            <h3 className="sticky top-0 border-b bg-muted/70 px-4 py-2 text-xs font-medium backdrop-blur-sm">
              {group.label}
            </h3>
            <div className="divide-y">
              {group.items.map((mediaMatch) => (
                <MatchRow
                  key={mediaMatch.id}
                  mediaMatch={mediaMatch}
                  isSelected={mediaMatch.id === selectedMatchId}
                  isChecked={selectedMatchIds.has(mediaMatch.id)}
                  isSelectionEnabled={isSelectionEnabled}
                  onSelectMatch={onSelectMatch}
                  onToggleSelection={onToggleSelection}
                />
              ))}
            </div>
          </section>
        ))}
      </ScrollArea>
    </section>
  )
}

function MatchRow({
  mediaMatch,
  isSelected,
  isChecked,
  isSelectionEnabled,
  onSelectMatch,
  onToggleSelection,
}: {
  mediaMatch: MediaMatch
  isSelected: boolean
  isChecked: boolean
  isSelectionEnabled: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
  onToggleSelection: (matchId: string) => void
}) {
  const selectedCandidate =
    mediaMatch.candidates.find(
      (candidate) => candidate.tmdb_id === mediaMatch.selected_tmdb_id,
    ) ?? mediaMatch.candidates[0]
  const recognitionMessage = matchRecognitionMessages(mediaMatch)[0]
  const isPending = isMetadataPending(mediaMatch)
  const isApprovable = isBatchApprovableMatch(mediaMatch)
  return (
    <div
      data-match-id={mediaMatch.id}
      aria-current={isSelected ? 'true' : undefined}
      className={cn(
        'grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2 px-3 py-1 transition-colors',
        isSelected && 'bg-accent/70',
      )}
    >
      <Checkbox
        aria-label={`选择 ${mediaMatch.filename}`}
        checked={isChecked}
        disabled={!isSelectionEnabled || !isApprovable}
        onCheckedChange={() => onToggleSelection(mediaMatch.id)}
      />
      <Button
        variant="ghost"
        className="grid h-auto min-w-0 grid-cols-[auto_minmax(8rem,0.9fr)_minmax(8rem,1.1fr)_auto_auto] gap-3 rounded-none px-1 py-3 text-left"
        type="button"
        onClick={() => onSelectMatch(mediaMatch)}
      >
        <Poster
          src={selectedCandidate?.poster_url ?? null}
          title={selectedCandidate?.title ?? mediaMatch.parsed_title}
        />
        <span className="min-w-0">
          <strong className="block truncate text-xs font-medium">{episodeLabel(mediaMatch)}</strong>
          <OriginalFileInfo
            filename={mediaMatch.filename}
            sourcePath={mediaMatch.source_path}
          />
        </span>
        <span className="min-w-0">
          <strong className="block truncate text-xs font-medium">
            {selectedCandidate?.title ?? '未找到候选'}
          </strong>
          <Badge variant="outline" className="mt-1 max-w-full text-[0.62rem]">
            {originLabel(mediaMatch.match_origin)}
          </Badge>
          <small
            className={cn(
              'block truncate text-[0.68rem] text-muted-foreground',
              recognitionMessage && (isPending ? 'text-info' : 'text-destructive'),
            )}
          >
            {recognitionMessage ?? selectedCandidate?.original_title ?? mediaMatch.parsed_title}
          </small>
        </span>
        <strong className={cn('text-xs tabular-nums', confidenceClass(mediaMatch.confidence))}>
          {formatConfidence(mediaMatch.confidence)}
        </strong>
        {isPending ? (
          <Badge variant="outline" className="text-info">
            <LoaderCircle className="animate-spin" aria-hidden="true" />
            识别中
          </Badge>
        ) : (
          <StatusBadge status={mediaMatch.decision} />
        )}
      </Button>
    </div>
  )
}

function originLabel(origin: MediaMatch['match_origin']): string {
  return {
    PATH_ID: '路径 ID',
    NFO: 'NFO',
    TMDB: 'TMDB',
    AI: 'AI',
    LOCAL: '本地',
    MANUAL: '手动',
    RULE: '规则',
  }[origin ?? 'RULE']
}

function confidenceClass(confidence: number): string {
  if (confidence >= AUTO_APPROVE_THRESHOLD) return 'text-success'
  if (confidence >= REVIEW_THRESHOLD) return 'text-warning'
  return 'text-destructive'
}
