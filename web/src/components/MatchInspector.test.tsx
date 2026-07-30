import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { MediaMatch } from '../types'
import { MatchInspector } from './MatchInspector'

const UNRESOLVED_MATCH: MediaMatch = {
  id: 'match-1',
  source_item_id: 'source-1',
  filename: '01.mp4',
  source_path: '/光鸭云盘/第一季/01.mp4',
  size_bytes: 1024,
  media_type: 'TV',
  parsed_title: '示例剧',
  parsed_year: 2026,
  season_number: 1,
  episode_numbers: [1],
  edition: '',
  confidence: 0,
  decision: 'UNRESOLVED',
  selected_tmdb_id: null,
  candidates: [],
  target_path: '',
  reason_codes: ['TMDB_FAILED'],
  group_key: 'TV|示例剧|2026',
  episode_title: '',
  episode_date: null,
  release_info: {},
}

describe('MatchInspector', () => {
  it('keeps ignore, retry, and manual matching usable without candidates', () => {
    const handleToggleIgnore = vi.fn()
    const handleRetry = vi.fn()
    const handleManualMatch = vi.fn()

    render(
      <MatchInspector
        mediaMatch={UNRESOLVED_MATCH}
        selectedCandidateId={null}
        isSaving={false}
        isRetrying={false}
        onSelectCandidate={vi.fn()}
        onApprove={vi.fn()}
        onToggleIgnore={handleToggleIgnore}
        onRetry={handleRetry}
        onManualMatch={handleManualMatch}
      />,
    )

    expect(screen.getByRole('button', { name: '采用此匹配' })).toBeDisabled()
    expect(
      screen.getByText('TMDB 请求失败，请检查网络或 API Token。'),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '忽略此文件' }))
    fireEvent.click(screen.getByRole('button', { name: '重试此文件' }))
    fireEvent.change(screen.getByLabelText('TMDB ID'), {
      target: { value: '12345' },
    })
    const manualMatchForm = screen
      .getByRole('button', { name: '保存并采用手动匹配' })
      .closest('form')
    expect(manualMatchForm).not.toBeNull()
    if (manualMatchForm) fireEvent.submit(manualMatchForm)

    expect(handleToggleIgnore).toHaveBeenCalledOnce()
    expect(handleRetry).toHaveBeenCalledOnce()
    expect(handleManualMatch).toHaveBeenCalledWith({
      tmdbId: 12345,
      title: '示例剧',
      originalTitle: '',
      year: 2026,
      mediaType: 'TV',
    })
  })
})
