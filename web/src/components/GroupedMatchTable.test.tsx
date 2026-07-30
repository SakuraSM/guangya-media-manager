import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { MediaMatch } from '../types'
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
        onSelectMatch={vi.fn()}
        onToggleSelection={handleToggleSelection}
        onTogglePageSelection={vi.fn()}
      />,
    )

    fireEvent.click(
      screen.getByRole('checkbox', { name: '选择 S01E01.mkv' }),
    )

    expect(handleToggleSelection).toHaveBeenCalledWith('match-1')
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
        onSelectMatch={vi.fn()}
        onToggleSelection={vi.fn()}
        onTogglePageSelection={vi.fn()}
      />,
    )

    expect(screen.getByText('正在查询 TMDB/AI 元数据。')).toBeVisible()
    expect(screen.getByText('识别中')).toBeVisible()
  })
})
