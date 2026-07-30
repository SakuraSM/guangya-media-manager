import { useQuery } from '@tanstack/react-query'
import { Film, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '@/api/client'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LoadingScreen } from '@/components/LoadingScreen'
import { Poster } from '@/components/Poster'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { formatDateTime } from '@/utils/format'

export function LibraryPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const libraryQuery = useQuery({ queryKey: ['library'], queryFn: api.getLibrary })
  const filteredItems = useMemo(() => {
    const normalizedSearchTerm = searchTerm.trim().toLocaleLowerCase()
    if (!normalizedSearchTerm) return libraryQuery.data ?? []
    return (libraryQuery.data ?? []).filter((item) =>
      item.title.toLocaleLowerCase().includes(normalizedSearchTerm),
    )
  }, [libraryQuery.data, searchTerm])

  if (libraryQuery.isPending) {
    return <LoadingScreen label="正在加载媒体库" />
  }
  if (libraryQuery.isError) {
    return <ErrorNotice message={libraryQuery.error.message} />
  }

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">已整理媒体</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            展示通过任务完成并落入目标目录的影视内容。
          </p>
        </div>
        <InputGroup className="w-full sm:w-72">
          <InputGroupAddon>
            <Search aria-hidden="true" />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="搜索标题"
            aria-label="搜索媒体库"
          />
        </InputGroup>
      </section>
      {filteredItems.length ? (
        <section
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
          aria-label="媒体列表"
        >
          {filteredItems.map((item) => (
            <Card key={item.id}>
              <CardContent className="flex gap-4">
                <Poster src={item.poster_url} title={item.title} size="large" />
                <div className="flex min-w-0 flex-1 flex-col">
                  <Badge variant="secondary" className="mb-3 w-fit">
                    {item.media_type === 'TV' ? '剧集' : '电影'}
                  </Badge>
                  <h2 className="line-clamp-2 text-base font-semibold">{item.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {item.year ?? '年份未知'}
                  </p>
                  <code className="mt-4 line-clamp-3 break-all text-xs text-muted-foreground">
                    {item.target_path}
                  </code>
                  <small className="mt-auto pt-4 text-xs text-muted-foreground">
                    完成于 {formatDateTime(item.completed_at)}
                  </small>
                </div>
              </CardContent>
            </Card>
          ))}
        </section>
      ) : (
        <Card>
          <CardContent>
            <Empty className="min-h-80">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Film aria-hidden="true" />
                </EmptyMedia>
                <EmptyTitle>{searchTerm ? '没有匹配的媒体' : '媒体库还没有完成项'}</EmptyTitle>
                <EmptyDescription>
                  {searchTerm
                    ? '换一个片名或清空搜索条件后再试。'
                    : '完成一次整理任务后，电影和剧集会显示在这里。'}
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                {searchTerm ? (
                  <Button variant="outline" type="button" onClick={() => setSearchTerm('')}>
                    清空搜索
                  </Button>
                ) : (
                  <Button variant="outline" asChild>
                    <a href="/jobs">创建整理任务</a>
                  </Button>
                )}
              </EmptyContent>
            </Empty>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
