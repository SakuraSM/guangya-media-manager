import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PaginationControls } from './PaginationControls'

const NEXT_PAGE = 3

describe('PaginationControls', () => {
  it('navigates server-side result pages', () => {
    const handlePageChange = vi.fn()

    render(
      <PaginationControls
        page={2}
        pages={7}
        pageSize={20}
        total={138}
        isLoading={false}
        onPageChange={handlePageChange}
        onPageSizeChange={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '下一页' }))

    expect(screen.getByText('共 138 条 · 第 2/7 页')).toBeVisible()
    expect(handlePageChange).toHaveBeenCalledWith(NEXT_PAGE)
  })
})
