import type { MediaMatch } from '../types'

const NUMBER_PAD_WIDTH = 2

export interface MediaMatchGroup {
  key: string
  label: string
  items: MediaMatch[]
}

export function groupMediaMatches(matches: MediaMatch[]): MediaMatchGroup[] {
  const groups = new Map<string, MediaMatch[]>()
  for (const mediaMatch of matches) {
    const key = mediaMatch.group_key || mediaMatch.id
    groups.set(key, [...(groups.get(key) ?? []), mediaMatch])
  }
  return [...groups.entries()].map(([key, items]) => {
    const firstItem = items[0]
    const seasonNumbers = [
      ...new Set(
        items
          .map((item) => item.season_number)
          .filter((season): season is number => season !== null),
      ),
    ].sort((left, right) => left - right)
    const seasons = seasonNumbers.map(
      (season) => `Season ${String(season).padStart(NUMBER_PAD_WIDTH, '0')}`,
    )
    return {
      key,
      label: `${firstItem?.parsed_title || '未识别媒体'}${seasons.length ? ` · ${seasons.join(' / ')}` : ''}`,
      items: [...items].sort(compareMediaMatches),
    }
  })
}

export function episodeLabel(mediaMatch: MediaMatch): string {
  if (mediaMatch.media_type !== 'TV') return mediaMatch.parsed_title
  const season = String(mediaMatch.season_number ?? 0).padStart(NUMBER_PAD_WIDTH, '0')
  const episodes = mediaMatch.episode_numbers
    .map((episode) => `E${String(episode).padStart(NUMBER_PAD_WIDTH, '0')}`)
    .join('')
  const title = mediaMatch.episode_title ? ` · ${mediaMatch.episode_title}` : ''
  return `S${season}${episodes || 'E??'}${title}`
}

function compareMediaMatches(left: MediaMatch, right: MediaMatch): number {
  const leftSeason = left.season_number ?? -1
  const rightSeason = right.season_number ?? -1
  if (leftSeason !== rightSeason) return leftSeason - rightSeason
  return (left.episode_numbers[0] ?? -1) - (right.episode_numbers[0] ?? -1)
}
