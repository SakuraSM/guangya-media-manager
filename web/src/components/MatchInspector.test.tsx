import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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
  library_category: 'TV',
  region_bucket: 'OTHER',
  classification_reasons: [],
  quality_profile: {},
  version_group_key: 'version-1',
  version_score: 0,
  version_recommendation: 'SINGLE',
}

describe('MatchInspector', () => {
  it('keeps ignore, retry, and TMDB search usable without candidates', () => {
    const handleToggleIgnore = vi.fn()
    const handleRetry = vi.fn()
    const handleManualMatch = vi.fn()
    const handleSelectNext = vi.fn()

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MatchInspector
          jobId="job-1"
          mediaMatch={UNRESOLVED_MATCH}
          selectedCandidateId={null}
          isSaving={false}
          isRetrying={false}
          isRetryingGroup={false}
          onSelectCandidate={vi.fn()}
          onApproveCandidate={vi.fn()}
          onToggleIgnore={handleToggleIgnore}
          onRetry={handleRetry}
          onRetryGroup={vi.fn()}
          onManualMatch={handleManualMatch}
          onManualGroupMatch={vi.fn()}
          versionMatches={[UNRESOLVED_MATCH]}
          onConfirmVersionGroup={vi.fn()}
          onUpdateClassification={vi.fn()}
          position={1}
          total={2}
          canSelectPrevious={false}
          canSelectNext
          onSelectPrevious={vi.fn()}
          onSelectNext={handleSelectNext}
        />
      </QueryClientProvider>,
    )

    expect(
      screen.getByText('TMDB 请求失败，请检查网络或 API Token。'),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '源文件与整理设置' }))
    expect(screen.getByText('原始文件')).toBeVisible()
    expect(screen.getAllByText(UNRESOLVED_MATCH.filename).length).toBeGreaterThan(0)
    expect(
      screen.getAllByText(UNRESOLVED_MATCH.source_path).some((element) =>
        element.classList.contains('font-mono'),
      ),
    ).toBe(true)
    expect(screen.getByLabelText('TMDB 关键字')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '下一条审核项' }))
    fireEvent.keyDown(screen.getByRole('button', { name: '更多审核操作' }), {
      key: 'Enter',
    })
    fireEvent.click(screen.getByRole('menuitem', { name: '忽略此文件' }))
    fireEvent.keyDown(screen.getByRole('button', { name: '更多审核操作' }), {
      key: 'Enter',
    })
    fireEvent.click(screen.getByRole('menuitem', { name: '仅重新识别此文件' }))

    expect(handleToggleIgnore).toHaveBeenCalledOnce()
    expect(handleRetry).toHaveBeenCalledOnce()
    expect(handleManualMatch).not.toHaveBeenCalled()
    expect(handleSelectNext).toHaveBeenCalledOnce()
  })
})
