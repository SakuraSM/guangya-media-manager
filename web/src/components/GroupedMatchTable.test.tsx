import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { REVIEW_FILTER, type MediaMatch } from '../types'
import { groupMediaMatches } from '../utils/reviewGrouping'
import { GroupedMatchTable } from './GroupedMatchTable'

const APPROVABLE_MATCH: MediaMatch = {
  id: 'match-1',
  source_item_id: 'source-1',
  filename: 'S01E01.mkv',
  source_path: '/剧集/S01E01.mkv',
  size_bytes: 1024,
  media_type: 'TV',
  parsed_title: '示例剧',
  parsed_year: 2026,
  season_number: 1,
  episode_numbers: [1],
  edition: '',
  confidence: 0.8,
  decision: 'REVIEW',
  selected_tmdb_id: null,
  candidates: [
    {
      tmdb_id: 123,
      title: '示例剧',
      original_title: 'Example Show',
      year: 2026,
      media_type: 'TV',
      score: 0.8,
      poster_url: null,
      backdrop_url: null,
      overview: '',
    },
  ],
  target_path: '',
  reason_codes: [],
  group_key: 'TV|示例剧|2026',
  episode_title: '',
  episode_date: null,
  release_info: {},
}

describe('GroupedMatchTable', () => {
  it('selects an approvable record for batch approval', () => {
    const handleToggleSelection = vi.fn()

    render(
      <GroupedMatchTable
        groups={groupMediaMatches([APPROVABLE_MATCH])}
        selectedMatchId={null}
        selectedMatchIds={new Set()}
        isSelectionEnabled
        reviewFilter={REVIEW_FILTER.PENDING}
        isFilterLoading={false}
        onSelectMatch={vi.fn()}
        onToggleSelection={handleToggleSelection}
        onTogglePageSelection={vi.fn()}
        onReviewFilterChange={vi.fn()}
      />,
    )

    fireEvent.click(
      screen.getByRole('checkbox', { name: '选择 S01E01.mkv' }),
    )

    expect(handleToggleSelection).toHaveBeenCalledWith('match-1')
  })

  it('shows the original filename and source path for every record', () => {
    render(
      <GroupedMatchTable
        groups={groupMediaMatches([APPROVABLE_MATCH])}
        selectedMatchId={null}
        selectedMatchIds={new Set()}
        isSelectionEnabled
        reviewFilter={REVIEW_FILTER.PENDING}
        isFilterLoading={false}
        onSelectMatch={vi.fn()}
        onToggleSelection={vi.fn()}
        onTogglePageSelection={vi.fn()}
        onReviewFilterChange={vi.fn()}
      />,
    )

    expect(screen.getByText(APPROVABLE_MATCH.filename)).toBeVisible()
    expect(screen.getByText(APPROVABLE_MATCH.source_path)).toBeVisible()
  })

  it('shows a pending state for incrementally persisted rule results', () => {
    const pendingMatch: MediaMatch = {
      ...APPROVABLE_MATCH,
      id: 'pending-match',
      decision: 'UNRESOLVED',
      candidates: [],
      reason_codes: ['TITLE_PARSED', 'METADATA_PENDING'],
    }

    render(
      <GroupedMatchTable
        groups={groupMediaMatches([pendingMatch])}
        selectedMatchId={null}
        selectedMatchIds={new Set()}
        isSelectionEnabled
        reviewFilter={REVIEW_FILTER.PENDING}
        isFilterLoading={false}
        onSelectMatch={vi.fn()}
        onToggleSelection={vi.fn()}
        onTogglePageSelection={vi.fn()}
        onReviewFilterChange={vi.fn()}
      />,
    )

    expect(screen.getByText('正在查询 TMDB/AI 元数据。')).toBeVisible()
    expect(screen.getByText('识别中')).toBeVisible()
  })

  it('scrolls the active approval row inside the list viewport', () => {
    const boundsSpy = vi
      .spyOn(Element.prototype, 'getBoundingClientRect')
      .mockImplementation(function getBoundingClientRect(this: Element) {
        if (this.getAttribute('data-slot') === 'scroll-area-viewport') {
          return DOMRect.fromRect({ y: 0, height: 100 })
        }
        if (this.getAttribute('data-match-id') === APPROVABLE_MATCH.id) {
          return DOMRect.fromRect({ y: 120, height: 40 })
        }
        return DOMRect.fromRect()
      })
    const scrollTo = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: scrollTo,
    })

    try {
      render(
        <GroupedMatchTable
          groups={groupMediaMatches([APPROVABLE_MATCH])}
          selectedMatchId={APPROVABLE_MATCH.id}
          selectedMatchIds={new Set()}
          isSelectionEnabled
          reviewFilter={REVIEW_FILTER.PENDING}
          isFilterLoading={false}
          onSelectMatch={vi.fn()}
          onToggleSelection={vi.fn()}
          onTogglePageSelection={vi.fn()}
          onReviewFilterChange={vi.fn()}
        />,
      )

      expect(scrollTo).toHaveBeenCalledWith({ top: 60, behavior: 'smooth' })
    } finally {
      boundsSpy.mockRestore()
      Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo')
    }
  })

  it('switches between pending and reviewed records', () => {
    const handleReviewFilterChange = vi.fn()

    render(
      <GroupedMatchTable
        groups={groupMediaMatches([APPROVABLE_MATCH])}
        selectedMatchId={null}
        selectedMatchIds={new Set()}
        isSelectionEnabled
        reviewFilter={REVIEW_FILTER.PENDING}
        isFilterLoading={false}
        onSelectMatch={vi.fn()}
        onToggleSelection={vi.fn()}
        onTogglePageSelection={vi.fn()}
        onReviewFilterChange={handleReviewFilterChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '已审核' }))

    expect(handleReviewFilterChange).toHaveBeenCalledWith(REVIEW_FILTER.REVIEWED)
  })
})
