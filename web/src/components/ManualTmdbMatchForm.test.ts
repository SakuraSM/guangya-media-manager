import { describe, expect, it } from 'vitest'
import {
  inferManualEpisodeMapping,
  parseEpisodeExpression,
} from '@/utils/episodeExpression'

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

describe('inferManualEpisodeMapping', () => {
  it('infers a bare episode number and season from the parent path', () => {
    expect(
      inferManualEpisodeMapping({
        filename: '12.mp4',
        sourcePath: '/媒体/示例剧/第2季/12.mp4',
        seasonNumber: null,
        episodeNumbers: [],
      }),
    ).toEqual({ seasonNumber: 2, episodeNumbers: [12], source: 'filename' })
  })

  it('infers season and a multi-episode range from the filename', () => {
    expect(
      inferManualEpisodeMapping({
        filename: 'Example.Show.S03E07-E09.mkv',
        sourcePath: '/媒体/示例剧/Example.Show.S03E07-E09.mkv',
        seasonNumber: null,
        episodeNumbers: [],
      }),
    ).toEqual({ seasonNumber: 3, episodeNumbers: [7, 8, 9], source: 'filename' })
  })

  it('keeps the mapping already produced by scanning', () => {
    expect(
      inferManualEpisodeMapping({
        filename: 'wrong-name.mkv',
        sourcePath: '/媒体/示例剧/wrong-name.mkv',
        seasonNumber: 4,
        episodeNumbers: [6],
      }),
    ).toEqual({ seasonNumber: 4, episodeNumbers: [6], source: 'scan' })
  })
})
