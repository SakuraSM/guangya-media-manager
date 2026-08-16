import { CircleAlert, Play } from 'lucide-react'
import type { MediaMatch } from '@/types'
import { formatBytes } from '@/utils/format'
import { episodeLabel, type MediaMatchGroup } from '@/utils/reviewGrouping'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

interface SourceMatchBrowserProps {
  groups: MediaMatchGroup[]
  selectedMatchId: string | null
  pageItemCount: number
  total: number
  onSelectMatch: (mediaMatch: MediaMatch) => void
}

export function SourceMatchBrowser({
  groups,
  selectedMatchId,
  pageItemCount,
  total,
  onSelectMatch,
}: SourceMatchBrowserProps) {
  return (
    <aside className="flex h-full min-h-0 flex-col bg-card">
      <div className="flex h-12 shrink-0 items-center justify-between border-b px-3">
        <h2 className="text-sm font-medium">源文件</h2>
        <span className="text-xs text-muted-foreground">
          本页 {pageItemCount} / 共 {total}
        </span>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <ul className="flex flex-col">
          {groups.map((group) => (
            <li key={group.key}>
              <h3 className="sticky top-0 border-b bg-muted/70 px-3 py-2 text-xs font-medium backdrop-blur-sm">
                {group.label}
              </h3>
              <ul className="flex flex-col gap-1 p-1.5">
                {group.items.map((mediaMatch) => (
                  <SourceMatchItem
                    key={mediaMatch.id}
                    mediaMatch={mediaMatch}
                    isSelected={mediaMatch.id === selectedMatchId}
                    onSelectMatch={onSelectMatch}
                  />
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </ScrollArea>
    </aside>
  )
}

function SourceMatchItem({
  mediaMatch,
  isSelected,
  onSelectMatch,
}: {
  mediaMatch: MediaMatch
  isSelected: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
}) {
  return (
    <li>
      <Button
        type="button"
        variant="ghost"
        className={cn(
          'h-auto w-full justify-start gap-2 px-2 py-2.5 text-left',
          isSelected && 'bg-accent text-accent-foreground ring-1 ring-primary/30',
        )}
        onClick={() => onSelectMatch(mediaMatch)}
      >
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
          <Play aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <strong className="block truncate text-xs font-medium">
            {episodeLabel(mediaMatch)}
          </strong>
          <small className="block truncate text-[0.68rem] text-muted-foreground">
            {mediaMatch.filename} · {formatBytes(mediaMatch.size_bytes)}
          </small>
          {mediaMatch.cleanup_error ?? mediaMatch.execution_error ? (
            <small className="mt-1 flex items-center gap-1 truncate text-[0.68rem] text-destructive">
              <CircleAlert aria-hidden="true" />
              {mediaMatch.cleanup_error ?? mediaMatch.execution_error}
            </small>
          ) : null}
        </span>
      </Button>
    </li>
  )
}
