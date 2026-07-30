import type { ManualMatchInput, MediaMatch, MediaMatchPage } from '../types'
import type { MediaMatchGroup } from '../utils/reviewGrouping'
import { GroupedMatchTable } from './GroupedMatchTable'
import { MatchInspector } from './MatchInspector'
import { PaginationControls } from './PaginationControls'
import { SourceMatchBrowser } from './SourceMatchBrowser'

interface ReviewWorkspaceProps {
  matchGroups: MediaMatchGroup[]
  matchPage: MediaMatchPage
  selectedMatch: MediaMatch | null
  selectedMatchIds: ReadonlySet<string>
  isSelectionEnabled: boolean
  selectedCandidateId: number | null
  isFetching: boolean
  isSaving: boolean
  isRetrying: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
  onToggleMatchSelection: (matchId: string) => void
  onTogglePageSelection: () => void
  onSelectCandidate: (candidateId: number) => void
  onApprove: () => void
  onToggleIgnore: () => void
  onRetry: () => void
  onManualMatch: (match: ManualMatchInput) => void
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

export function ReviewWorkspace({
  matchGroups,
  matchPage,
  selectedMatch,
  selectedMatchIds,
  isSelectionEnabled,
  selectedCandidateId,
  isFetching,
  isSaving,
  isRetrying,
  onSelectMatch,
  onToggleMatchSelection,
  onTogglePageSelection,
  onSelectCandidate,
  onApprove,
  onToggleIgnore,
  onRetry,
  onManualMatch,
  onPageChange,
  onPageSizeChange,
}: ReviewWorkspaceProps) {
  return (
    <section className="review-workbench" aria-label="匹配审核工作台">
      <div className="review-workspace">
        <SourceMatchBrowser
          groups={matchGroups}
          selectedMatchId={selectedMatch?.id ?? null}
          pageItemCount={matchPage.items.length}
          total={matchPage.total}
          onSelectMatch={onSelectMatch}
        />
        <GroupedMatchTable
          groups={matchGroups}
          selectedMatchId={selectedMatch?.id ?? null}
          selectedMatchIds={selectedMatchIds}
          isSelectionEnabled={isSelectionEnabled}
          onSelectMatch={onSelectMatch}
          onToggleSelection={onToggleMatchSelection}
          onTogglePageSelection={onTogglePageSelection}
        />
        <MatchInspector
          mediaMatch={selectedMatch}
          selectedCandidateId={selectedCandidateId}
          isSaving={isSaving}
          isRetrying={isRetrying}
          onSelectCandidate={onSelectCandidate}
          onApprove={onApprove}
          onToggleIgnore={onToggleIgnore}
          onRetry={onRetry}
          onManualMatch={onManualMatch}
        />
      </div>
      <PaginationControls
        page={matchPage.page}
        pages={matchPage.pages}
        pageSize={matchPage.page_size}
        total={matchPage.total}
        isLoading={isFetching}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />
    </section>
  )
}
