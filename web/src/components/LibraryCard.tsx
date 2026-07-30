import { CalendarDays, ChevronRight, Files, ListTree } from 'lucide-react'
import { Poster } from '@/components/Poster'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { LibraryItem } from '@/types'
import { formatDateTime } from '@/utils/format'

interface LibraryCardProps {
  item: LibraryItem
  onOpen: (item: LibraryItem) => void
}

export function LibraryCard({ item, onOpen }: LibraryCardProps) {
  const isTvShow = item.media_type === 'TV'

  function handleOpenLibraryItem() {
    onOpen(item)
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="line-clamp-2">{item.title}</CardTitle>
        <CardDescription>{item.year ?? '年份未知'}</CardDescription>
        <CardAction>
          <Badge variant="secondary">{isTvShow ? '剧集' : '电影'}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex min-h-52 gap-4">
        <Poster src={item.poster_url} title={item.title} size="large" />
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {isTvShow ? (
              <>
                <Badge variant="outline">{item.season_count} 季</Badge>
                <Badge variant="outline">{item.episode_count} 集</Badge>
              </>
            ) : null}
            <Badge variant="outline">
              <Files aria-hidden="true" />
              {item.file_count} 个文件
            </Badge>
          </div>
          <code className="line-clamp-4 break-all text-xs text-muted-foreground">
            {item.target_path || '目标路径暂不可用'}
          </code>
          <span className="mt-auto flex items-center gap-2 text-xs text-muted-foreground">
            <CalendarDays aria-hidden="true" />
            完成于 {formatDateTime(item.completed_at)}
          </span>
        </div>
      </CardContent>
      <CardFooter className="justify-between gap-3">
        <span className="text-xs text-muted-foreground">TMDB · {item.tmdb_id}</span>
        {isTvShow ? (
          <Button type="button" variant="outline" onClick={handleOpenLibraryItem}>
            <ListTree data-icon="inline-start" />
            查看季与剧集
            <ChevronRight data-icon="inline-end" />
          </Button>
        ) : (
          <Badge variant="secondary">已入库</Badge>
        )}
      </CardFooter>
    </Card>
  )
}
