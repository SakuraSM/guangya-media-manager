import { useQuery } from '@tanstack/react-query'
import { Film, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { ErrorNotice } from '../components/ErrorNotice'
import { LoadingScreen } from '../components/LoadingScreen'
import { Poster } from '../components/Poster'
import { formatDateTime } from '../utils/format'

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
    <div className="page-stack">
      <section className="page-command-bar">
        <div>
          <h2>已整理媒体</h2>
          <p>展示通过任务完成并落入目标目录的影视内容。</p>
        </div>
        <label className="search-field">
          <Search size={16} aria-hidden="true" />
          <span className="visually-hidden">搜索媒体库</span>
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="搜索标题"
          />
        </label>
      </section>
      {filteredItems.length ? (
        <section className="library-grid" aria-label="媒体列表">
          {filteredItems.map((item) => (
            <article className="library-item" key={item.id}>
              <Poster src={item.poster_url} title={item.title} size="large" />
              <div>
                <span>{item.media_type === 'TV' ? '剧集' : '电影'}</span>
                <h2>{item.title}</h2>
                <p>{item.year ?? '年份未知'}</p>
                <code>{item.target_path}</code>
                <small>完成于 {formatDateTime(item.completed_at)}</small>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className="empty-panel">
          <Film size={30} aria-hidden="true" />
          <h2>媒体库还没有完成项</h2>
          <p>完成一次整理任务后，电影和剧集会显示在这里。</p>
        </section>
      )}
    </div>
  )
}
