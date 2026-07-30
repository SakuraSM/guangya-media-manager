import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { LibraryItem, LibraryItemDetail } from '@/types'
import { LibraryPage } from './LibraryPage'

vi.mock('@/api/client', () => ({
  api: {
    getLibrary: vi.fn(),
    getLibraryDetail: vi.fn(),
  },
}))

const TV_SHOW: LibraryItem = {
  id: 'show-1',
  tmdb_id: 1396,
  title: '绝命毒师',
  year: 2008,
  media_type: 'TV',
  poster_url: null,
  target_path: 'TV/绝命毒师 (2008)',
  completed_at: '2026-07-30T10:00:00Z',
  file_count: 62,
  season_count: 5,
  episode_count: 62,
}

const TV_SHOW_DETAIL: LibraryItemDetail = {
  ...TV_SHOW,
  overview: '一位化学老师走上另一条人生道路。',
  backdrop_url: null,
  seasons: [
    {
      id: 'season-1',
      season_number: 1,
      name: '第 1 季',
      overview: '',
      poster_url: null,
      episode_count: 1,
      episodes: [
        {
          id: 'episode-3',
          episode_number: 3,
          title: '无可奈何',
          overview: '',
          air_date: '2008-02-10',
          still_url: null,
          source_filename: 'Breaking.Bad.S01E03.mkv',
          target_path: 'TV/绝命毒师 (2008)/Season 01/绝命毒师 - S01E03.mkv',
        },
      ],
    },
  ],
}

function renderLibraryPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <LibraryPage />
    </QueryClientProvider>,
  )
}

describe('LibraryPage', () => {
  beforeEach(() => {
    vi.mocked(api.getLibrary).mockResolvedValue([TV_SHOW])
    vi.mocked(api.getLibraryDetail).mockResolvedValue(TV_SHOW_DETAIL)
  })

  it('loads episode hierarchy only after opening the grouped TV show', async () => {
    renderLibraryPage()

    expect(await screen.findByText('绝命毒师')).toBeVisible()
    expect(screen.getByText('5 季')).toBeVisible()
    expect(screen.getByText('62 集')).toBeVisible()
    expect(api.getLibraryDetail).not.toHaveBeenCalled()
    expect(screen.queryByText('E03 · 无可奈何')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '查看季与剧集' }))

    expect(await screen.findByText('E03 · 无可奈何')).toBeVisible()
    expect(api.getLibraryDetail).toHaveBeenCalledWith('show-1')
  })
})
