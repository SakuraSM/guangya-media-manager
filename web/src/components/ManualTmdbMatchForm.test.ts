import { describe, expect, it } from 'vitest'
import { parseEpisodeExpression } from '@/utils/episodeExpression'

describe('parseEpisodeExpression', () => {
  it('parses individual episodes and ranges without duplicates', () => {
    expect(parseEpisodeExpression('1, 2，4-6, 2')).toEqual([1, 2, 4, 5, 6])
  })

  it('rejects invalid or excessively large ranges', () => {
    expect(parseEpisodeExpression('0')).toEqual([])
    expect(parseEpisodeExpression('5-2')).toEqual([])
    expect(parseEpisodeExpression('1-30')).toEqual([])
  })
})
