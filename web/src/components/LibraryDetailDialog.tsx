import { useQuery } from '@tanstack/react-query'
import {
  CalendarDays,
  ChevronDown,
  Clapperboard,
  FolderOpen,
  ListVideo,
} from 'lucide-react'
import { api } from '@/api/client'
import { ErrorNotice } from '@/components/ErrorNotice'
import { Poster } from '@/components/Poster'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import type { LibraryEpisode, LibraryItem, LibrarySeason } from '@/types'

interface LibraryDetailDialogProps {
  item: LibraryItem | null
  onOpenChange: (isOpen: boolean) => void
}

interface SeasonPanelProps {
  season: LibrarySeason
  defaultOpen: boolean
}

const MEDIA_NUMBER_WIDTH = 2

function getSeasonLabel(season: LibrarySeason): string {
  if (season.name) return season.name
  if (season.season_number === 0) return '特别篇'
  return `Season ${String(season.season_number).padStart(MEDIA_NUMBER_WIDTH, '0')}`
}

function getEpisodeLabel(episode: LibraryEpisode): string {
  const episodeNumber = `E${String(episode.episode_number).padStart(MEDIA_NUMBER_WIDTH, '0')}`
  return episode.title ? `${episodeNumber} · ${episode.title}` : `第 ${episode.episode_number} 集`
}

function EpisodeRow({ episode }: { episode: LibraryEpisode }) {
  return (
    <li>
      <Card size="sm">
        <CardHeader>
          <CardTitle>{getEpisodeLabel(episode)}</CardTitle>
          {episode.air_date ? (
            <Badge variant="outline">
              <CalendarDays aria-hidden="true" />
              {episode.air_date}
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {episode.overview ? (
            <p className="line-clamp-2 text-sm text-muted-foreground">
              {episode.overview}
            </p>
          ) : null}
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            <Clapperboard aria-hidden="true" />
            <span className="break-all">{episode.source_filename}</span>
          </div>
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            <FolderOpen aria-hidden="true" />
            <code className="break-all">{episode.target_path}</code>
          </div>
        </CardContent>
      </Card>
    </li>
  )
}

function SeasonPanel({ season, defaultOpen }: SeasonPanelProps) {
  return (
    <Collapsible defaultOpen={defaultOpen}>
      <Card size="sm">
        <CollapsibleTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            className="group h-auto w-full justify-between rounded-none px-4 py-3"
          >
            <span className="flex min-w-0 items-center gap-3">
              <ListVideo data-icon="inline-start" />
              <span className="truncate font-medium">{getSeasonLabel(season)}</span>
              <Badge variant="secondary">{season.episode_count} 集</Badge>
            </span>
            <ChevronDown
              data-icon="inline-end"
              className="transition-transform group-data-[state=open]:rotate-180"
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent>
            {season.overview ? (
              <p className="mb-3 text-sm text-muted-foreground">{season.overview}</p>
            ) : null}
            <ol className="flex flex-col gap-2" aria-label={`${getSeasonLabel(season)} 剧集`}>
              {season.episodes.map((episode) => (
                <EpisodeRow key={episode.id} episode={episode} />
              ))}
            </ol>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}

function DetailLoading() {
  return (
    <div className="flex flex-col gap-3 p-5" role="status" aria-label="正在加载季与剧集">
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-full" />
    </div>
  )
}

export function LibraryDetailDialog({
  item,
  onOpenChange,
}: LibraryDetailDialogProps) {
  const itemId = item?.id ?? ''
  const detailQuery = useQuery({
    queryKey: ['library', itemId],
    queryFn: () => api.getLibraryDetail(itemId),
    enabled: Boolean(itemId),
  })

  return (
    <Dialog open={Boolean(item)} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100vh-2rem)] gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="px-5 pt-5 pr-14 pb-4">
          <DialogTitle>{item?.title ?? '剧集详情'}</DialogTitle>
          <DialogDescription>
            按 Season 浏览已经整理完成的剧集文件。
          </DialogDescription>
        </DialogHeader>
        {detailQuery.isPending ? <DetailLoading /> : null}
        {detailQuery.isError ? (
          <div className="p-5">
            <ErrorNotice message={detailQuery.error.message} />
          </div>
        ) : null}
        {detailQuery.data ? (
          <ScrollArea className="max-h-[calc(100vh-8rem)]">
            <div className="flex flex-col gap-4 p-5 pt-0">
              <section className="flex gap-4" aria-label="剧集概览">
                <Poster
                  src={detailQuery.data.poster_url}
                  title={detailQuery.data.title}
                  size="medium"
                />
                <div className="flex min-w-0 flex-1 flex-col gap-2">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">{detailQuery.data.season_count} 季</Badge>
                    <Badge variant="outline">{detailQuery.data.episode_count} 集</Badge>
                  </div>
                  {detailQuery.data.overview ? (
                    <p className="line-clamp-3 text-sm text-muted-foreground">
                      {detailQuery.data.overview}
                    </p>
                  ) : null}
                  <code className="break-all text-xs text-muted-foreground">
                    {detailQuery.data.target_path}
                  </code>
                </div>
              </section>
              {detailQuery.data.seasons.length ? (
                <section className="flex flex-col gap-3" aria-label="Season 与剧集">
                  {detailQuery.data.seasons.map((season, index) => (
                    <SeasonPanel
                      key={season.id}
                      season={season}
                      defaultOpen={index === 0}
                    />
                  ))}
                </section>
              ) : (
                <Empty className="min-h-56">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <ListVideo aria-hidden="true" />
                    </EmptyMedia>
                    <EmptyTitle>暂无季集信息</EmptyTitle>
                    <EmptyDescription>
                      该条目已入库，但当前记录中没有可展示的 Season 或剧集。
                    </EmptyDescription>
                  </EmptyHeader>
                </Empty>
              )}
            </div>
          </ScrollArea>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
