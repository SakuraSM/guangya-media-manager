import { LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { AUTO_APPROVE_THRESHOLD, REVIEW_THRESHOLD } from '@/constants'
import type { MediaMatch } from '@/types'
import { formatConfidence } from '@/utils/format'
import { isMetadataPending, matchRecognitionMessages } from '@/utils/matchFailureReasons'
import {
  episodeLabel,
  isBatchApprovableMatch,
  type MediaMatchGroup,
} from '@/utils/reviewGrouping'
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
  onSelectMatch: (mediaMatch: MediaMatch) => void
  onToggleSelection: (matchId: string) => void
  onTogglePageSelection: () => void
  leadingAction?: ReactNode
}

export function GroupedMatchTable({
  groups,
  selectedMatchId,
  selectedMatchIds,
  isSelectionEnabled,
  onSelectMatch,
  onToggleSelection,
  onTogglePageSelection,
  leadingAction,
}: GroupedMatchTableProps) {
  const approvableMatches = groups
    .flatMap((group) => group.items)
    .filter(isBatchApprovableMatch)
  const areAllApprovableSelected =
    approvableMatches.length > 0 &&
    approvableMatches.every((mediaMatch) => selectedMatchIds.has(mediaMatch.id))
  return (
    <section className="flex h-full min-h-0 flex-col bg-card" aria-labelledby="match-table-title">
      <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b px-3">
        <div className="flex min-w-0 items-center gap-2">
          {leadingAction}
          <h2 id="match-table-title" className="truncate text-sm font-medium">
            TMDB 优先识别
          </h2>
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
      <ScrollArea className="min-h-0 flex-1">
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
        className="grid h-auto min-w-0 grid-cols-[auto_minmax(5.5rem,0.7fr)_minmax(8rem,1.2fr)_auto_auto] gap-3 rounded-none px-1 py-3 text-left"
        type="button"
        onClick={() => onSelectMatch(mediaMatch)}
      >
        <Poster
          src={selectedCandidate?.poster_url ?? null}
          title={selectedCandidate?.title ?? mediaMatch.parsed_title}
        />
        <span className="min-w-0">
          <strong className="block truncate text-xs font-medium">{episodeLabel(mediaMatch)}</strong>
          <small className="block truncate text-[0.68rem] text-muted-foreground">
            {mediaMatch.filename}
          </small>
        </span>
        <span className="min-w-0">
          <strong className="block truncate text-xs font-medium">
            {selectedCandidate?.title ?? '未找到候选'}
          </strong>
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

function confidenceClass(confidence: number): string {
  if (confidence >= AUTO_APPROVE_THRESHOLD) return 'text-success'
  if (confidence >= REVIEW_THRESHOLD) return 'text-warning'
  return 'text-destructive'
}
