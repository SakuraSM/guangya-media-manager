const COMPACT_PAGE_SIZE = 20
const DEFAULT_PAGE_SIZE = 50
const LARGE_PAGE_SIZE = 100
const PAGE_SIZE_OPTIONS = [
  COMPACT_PAGE_SIZE,
  DEFAULT_PAGE_SIZE,
  LARGE_PAGE_SIZE,
] as const

interface PaginationControlsProps {
  page: number
  pages: number
  pageSize: number
  total: number
  isLoading: boolean
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  ariaLabel?: string
}

export function PaginationControls({
  page,
  pages,
  pageSize,
  total,
  isLoading,
  onPageChange,
  onPageSizeChange,
  ariaLabel = '匹配结果分页',
}: PaginationControlsProps) {
  const displayPages = Math.max(pages, 1)
  const handlePageSizeChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    onPageSizeChange(Number(event.target.value))
  }

  return (
    <nav className="pagination-controls" aria-label={ariaLabel}>
      <span>
        共 {total} 条 · 第 {page}/{displayPages} 页
      </span>
      <label>
        每页
        <select
          value={pageSize}
          onChange={handlePageSizeChange}
          disabled={isLoading}
        >
          {PAGE_SIZE_OPTIONS.map((option) => (
            <option value={option} key={option}>
              {option} 条
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="button button-secondary"
        disabled={page <= 1 || isLoading}
        onClick={() => onPageChange(page - 1)}
      >
        上一页
      </button>
      <button
        type="button"
        className="button button-secondary"
        disabled={page >= displayPages || isLoading}
        onClick={() => onPageChange(page + 1)}
      >
        下一页
      </button>
    </nav>
  )
}
