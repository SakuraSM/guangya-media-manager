import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { TooltipProvider } from '@/components/ui/tooltip'
import { DirectoryPicker } from './DirectoryPicker'

describe('DirectoryPicker', () => {
  it('truncates a long directory name without hiding its select action', async () => {
    const directoryName =
      '这是一个非常非常长且没有适合换行位置的电视剧资源归档目录名称第一季到第二十季'
    vi.spyOn(api, 'getDirectories').mockResolvedValue([
      {
        id: 'long-directory',
        parent_id: '',
        name: directoryName,
        path: `/光鸭云盘/${directoryName}`,
        item_count: null,
      },
    ])
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <DirectoryPicker
            id="source"
            label="源目录"
            value={null}
            onSelect={vi.fn()}
          />
        </TooltipProvider>
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: '源目录' }))

    const directoryLabel = await screen.findByText(directoryName)
    expect(directoryLabel).toHaveClass('truncate')
    expect(screen.getByRole('button', { name: '选择' })).toBeVisible()
    expect(screen.getByText('项目数量未知')).toBeVisible()
  })
})
