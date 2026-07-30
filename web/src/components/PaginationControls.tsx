import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
} from '@/components/ui/pagination'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const PAGE_SIZE_OPTIONS = [20, 50, 100] as const

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

  return (
    <Pagination
      className="shrink-0 justify-end border-t bg-card px-3 py-3"
      aria-label={ariaLabel}
    >
      <PaginationContent className="flex-wrap justify-end">
        <PaginationItem>
          <span className="px-1 text-xs text-muted-foreground sm:px-2">
            <span className="sm:hidden">{total} 条 · {page}/{displayPages} 页</span>
            <span className="hidden sm:inline">
              共 {total} 条 · 第 {page}/{displayPages} 页
            </span>
          </span>
        </PaginationItem>
        <PaginationItem>
          <Select
            value={String(pageSize)}
            onValueChange={(value) => onPageSizeChange(Number(value))}
            disabled={isLoading}
          >
            <SelectTrigger className="w-24" aria-label="每页数量">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {PAGE_SIZE_OPTIONS.map((option) => (
                  <SelectItem value={String(option)} key={option}>
                    {option} 条
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </PaginationItem>
        <PaginationItem>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="上一页"
            disabled={page <= 1 || isLoading}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft aria-hidden="true" />
            <span className="hidden sm:inline">上一页</span>
          </Button>
        </PaginationItem>
        <PaginationItem>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="下一页"
            disabled={page >= displayPages || isLoading}
            onClick={() => onPageChange(page + 1)}
          >
            <span className="hidden sm:inline">下一页</span>
            <ChevronRight aria-hidden="true" />
          </Button>
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  )
}
