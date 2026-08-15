import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { MediaMatch } from '@/types'
import { ManualTmdbMatchForm } from './ManualTmdbMatchForm'

vi.mock('@/api/client', () => ({
  api: {
    searchTmdb: vi.fn().mockResolvedValue([
      {
        tmdb_id: 42,
        title: '纠正后的剧名',
        original_title: 'Corrected Series',
        year: 2026,
        media_type: 'TV',
        score: 1,
        poster_url: null,
        backdrop_url: null,
        overview: '',
      },
    ]),
    previewManualMatch: vi.fn().mockResolvedValue({
      tmdb_id: 42,
      title: '纠正后的剧名',
      year: 2026,
      media_type: 'TV',
      season_number: 1,
      episode_numbers: [1],
      missing_episode_numbers: [],
      target_path: 'TV/纠正后的剧名 (2026)/Season 01/纠正后的剧名 - S01E01.mkv',
    }),
    getTmdbSeasons: vi.fn().mockResolvedValue([]),
    getTmdbEpisodes: vi.fn().mockResolvedValue([]),
  },
}))

const MEDIA_MATCH: MediaMatch = {
  id: 'match-1',
  source_item_id: 'source-1',
  filename: '01.mkv',
  source_path: '/媒体/错误剧名/第1季/01.mkv',
  size_bytes: 1024,
  media_type: 'TV',
  parsed_title: '错误剧名',
  parsed_year: null,
  season_number: 1,
  episode_numbers: [1],
  edition: '',
  confidence: 0.4,
  decision: 'REVIEW',
  selected_tmdb_id: null,
  candidates: [],
  target_path: '',
  reason_codes: [],
  group_key: 'TV|错误剧名|',
  episode_title: '',
  episode_date: null,
  release_info: {},
  library_category: 'TV',
  region_bucket: 'OTHER',
  classification_reasons: [],
  quality_profile: {},
  version_group_key: 'version-1',
  version_score: 0,
  version_recommendation: 'SINGLE',
}

describe('ManualTmdbMatchForm', () => {
  it('applies a selected TV result to the whole series immediately', async () => {
    const onSubmitCurrent = vi.fn()
    const onSubmitGroup = vi.fn()

    render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: { queries: { retry: false } },
          })
        }
      >
        <ManualTmdbMatchForm
          jobId="job-1"
          mediaMatch={MEDIA_MATCH}
          isSaving={false}
          onSubmitCurrent={onSubmitCurrent}
          onSubmitGroup={onSubmitGroup}
        />
      </QueryClientProvider>,
    )

    expect(screen.getByLabelText('TMDB 关键字')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '搜索 TMDB' }))
    fireEvent.click(await screen.findByRole('button', { name: /纠正后的剧名/ }))

    await waitFor(() =>
      expect(onSubmitGroup).toHaveBeenCalledWith(
        expect.objectContaining({ tmdbId: 42, seasonNumber: 1, episodeNumbers: [1] }),
      ),
    )
    expect(onSubmitCurrent).not.toHaveBeenCalled()
  })

  it('prefills season and episode from a numeric source filename', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ManualTmdbMatchForm
          jobId="job-1"
          mediaMatch={{
            ...MEDIA_MATCH,
            filename: '12.mkv',
            source_path: '/媒体/错误剧名/第2季/12.mkv',
            season_number: null,
            episode_numbers: [],
          }}
          isSaving={false}
          onSubmitCurrent={vi.fn()}
          onSubmitGroup={vi.fn()}
        />
      </QueryClientProvider>,
    )

    expect(screen.getByLabelText('TMDB 关键字')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '搜索 TMDB' }))
    fireEvent.click(await screen.findByRole('button', { name: /纠正后的剧名/ }))

    expect(screen.getByLabelText('季号')).toHaveValue(2)
    expect(screen.getByLabelText('集号')).toHaveValue('12')
    expect(screen.getByText('已从原文件自动识别：S02E12')).toBeVisible()
  })
})
