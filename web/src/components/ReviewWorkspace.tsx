import { useState } from 'react'
import { FolderTree } from 'lucide-react'
import type { ManualMatchInput, MediaMatch, MediaMatchPage } from '@/types'
import type { MediaMatchGroup } from '@/utils/reviewGrouping'
import { GroupedMatchTable } from '@/components/GroupedMatchTable'
import { MatchInspector } from '@/components/MatchInspector'
import { PaginationControls } from '@/components/PaginationControls'
import { SourceMatchBrowser } from '@/components/SourceMatchBrowser'
import { Button } from '@/components/ui/button'
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'

interface ReviewWorkspaceProps {
  jobId: string
  matchGroups: MediaMatchGroup[]
  matchPage: MediaMatchPage
  selectedMatch: MediaMatch | null
  selectedMatchIds: ReadonlySet<string>
  isSelectionEnabled: boolean
  selectedCandidateId: number | null
  isFetching: boolean
  isSaving: boolean
  isRetrying: boolean
  isRetryingGroup: boolean
  onSelectMatch: (mediaMatch: MediaMatch) => void
  onToggleMatchSelection: (matchId: string) => void
  onTogglePageSelection: () => void
  onSelectCandidate: (candidateId: number) => void
  onApprove: () => void
  onToggleIgnore: () => void
  onRetry: () => void
  onRetryGroup: () => void
  onManualMatch: (match: ManualMatchInput) => void
  onManualGroupMatch: (match: ManualMatchInput) => void
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

export function ReviewWorkspace(props: ReviewWorkspaceProps) {
  const [isInspectorOpen, setIsInspectorOpen] = useState(false)
  const handleMobileSelect = (mediaMatch: MediaMatch) => {
    props.onSelectMatch(mediaMatch)
    setIsInspectorOpen(true)
  }

  const sourceBrowser = (
    <SourceMatchBrowser
      groups={props.matchGroups}
      selectedMatchId={props.selectedMatch?.id ?? null}
      pageItemCount={props.matchPage.items.length}
      total={props.matchPage.total}
      onSelectMatch={props.onSelectMatch}
    />
  )
  const matchTable = (
    onSelectMatch: (mediaMatch: MediaMatch) => void,
    leadingAction?: React.ReactNode,
  ) => (
    <GroupedMatchTable
      groups={props.matchGroups}
      selectedMatchId={props.selectedMatch?.id ?? null}
      selectedMatchIds={props.selectedMatchIds}
      isSelectionEnabled={props.isSelectionEnabled}
      onSelectMatch={onSelectMatch}
      onToggleSelection={props.onToggleMatchSelection}
      onTogglePageSelection={props.onTogglePageSelection}
      leadingAction={leadingAction}
    />
  )
  const inspector = (
    <MatchInspector
      jobId={props.jobId}
      mediaMatch={props.selectedMatch}
      selectedCandidateId={props.selectedCandidateId}
      isSaving={props.isSaving}
      isRetrying={props.isRetrying}
      isRetryingGroup={props.isRetryingGroup}
      onSelectCandidate={props.onSelectCandidate}
      onApprove={props.onApprove}
      onToggleIgnore={props.onToggleIgnore}
      onRetry={props.onRetry}
      onRetryGroup={props.onRetryGroup}
      onManualMatch={props.onManualMatch}
      onManualGroupMatch={props.onManualGroupMatch}
    />
  )

  return (
    <section
      className="flex min-h-[32rem] flex-col overflow-hidden rounded-xl border bg-card lg:min-h-0 lg:flex-1"
      aria-label="匹配审核工作台"
    >
      <div className="hidden min-h-0 flex-1 xl:block">
        <ResizablePanelGroup orientation="horizontal">
          <ResizablePanel defaultSize="22%" minSize="16%" maxSize="32%">
            {sourceBrowser}
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize="48%" minSize="35%">
            {matchTable(props.onSelectMatch)}
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize="30%" minSize="24%" maxSize="40%">
            {inspector}
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      <div className="hidden min-h-0 flex-1 grid-cols-[minmax(0,1.25fr)_minmax(19rem,0.75fr)] md:grid xl:hidden">
        <div className="relative min-h-0 border-r">
          {matchTable(
            props.onSelectMatch,
            <SourceSheet>{sourceBrowser}</SourceSheet>,
          )}
        </div>
        {inspector}
      </div>

      <div className="relative min-h-0 flex-1 md:hidden">
        {matchTable(
          handleMobileSelect,
          <SourceSheet>{sourceBrowser}</SourceSheet>,
        )}
        <Drawer open={isInspectorOpen} onOpenChange={setIsInspectorOpen}>
          <DrawerContent>
            <DrawerHeader className="sr-only">
              <DrawerTitle>匹配详情</DrawerTitle>
              <DrawerDescription>审核当前媒体文件的 TMDB 匹配。</DrawerDescription>
            </DrawerHeader>
            <div className="h-[75svh] min-h-0">{inspector}</div>
          </DrawerContent>
        </Drawer>
      </div>

      <PaginationControls
        page={props.matchPage.page}
        pages={props.matchPage.pages}
        pageSize={props.matchPage.page_size}
        total={props.matchPage.total}
        isLoading={props.isFetching}
        onPageChange={props.onPageChange}
        onPageSizeChange={props.onPageSizeChange}
      />
    </section>
  )
}

function SourceSheet({ children }: { children: React.ReactNode }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          aria-label="打开源文件列表"
        >
          <FolderTree data-icon="inline-start" aria-hidden="true" />
          <span className="hidden sm:inline">源文件</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-[88vw] gap-0 p-0 sm:max-w-sm">
        <SheetHeader className="sr-only">
          <SheetTitle>源文件</SheetTitle>
          <SheetDescription>按影视、季和剧集浏览当前页源文件。</SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 pt-10">{children}</div>
      </SheetContent>
    </Sheet>
  )
}
