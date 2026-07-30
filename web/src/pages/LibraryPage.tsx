import { useQuery } from '@tanstack/react-query'
import { Film, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '@/api/client'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LibraryCard } from '@/components/LibraryCard'
import { LibraryDetailDialog } from '@/components/LibraryDetailDialog'
import { LoadingScreen } from '@/components/LoadingScreen'
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
import type { LibraryItem } from '@/types'

export function LibraryPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedItem, setSelectedItem] = useState<LibraryItem | null>(null)
  const libraryQuery = useQuery({ queryKey: ['library'], queryFn: api.getLibrary })
  const filteredItems = useMemo(() => {
    const normalizedSearchTerm = searchTerm.trim().toLocaleLowerCase()
    if (!normalizedSearchTerm) return libraryQuery.data ?? []
    return (libraryQuery.data ?? []).filter((item) =>
      item.title.toLocaleLowerCase().includes(normalizedSearchTerm),
    )
  }, [libraryQuery.data, searchTerm])

  function handleOpenLibraryItem(item: LibraryItem) {
    setSelectedItem(item)
  }

  function handleDetailOpenChange(isOpen: boolean) {
    if (!isOpen) setSelectedItem(null)
  }

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
            按整部作品归类展示，点击剧集可继续浏览 Season 与单集。
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
          className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3"
          aria-label="媒体列表"
        >
          {filteredItems.map((item) => (
            <LibraryCard key={item.id} item={item} onOpen={handleOpenLibraryItem} />
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
      <LibraryDetailDialog
        item={selectedItem}
        onOpenChange={handleDetailOpenChange}
      />
    </div>
  )
}
