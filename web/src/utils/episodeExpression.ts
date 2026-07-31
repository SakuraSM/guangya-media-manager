const EPISODE_SEPARATOR_PATTERN = /[,，\s]+/
const EPISODE_RANGE_PATTERN = /^(\d+)-(\d+)$/
const MAX_EPISODE_RANGE_SIZE = 20

export function parseEpisodeExpression(value: string): number[] {
  const numbers: number[] = []
  for (const token of value.trim().split(EPISODE_SEPARATOR_PATTERN)) {
    if (!token) continue
    const rangeMatch = EPISODE_RANGE_PATTERN.exec(token)
    if (rangeMatch) {
      const start = Number(rangeMatch[1])
      const end = Number(rangeMatch[2])
      if (start <= 0 || end < start || end - start + 1 > MAX_EPISODE_RANGE_SIZE) {
        return []
      }
      for (let episodeNumber = start; episodeNumber <= end; episodeNumber += 1) {
        numbers.push(episodeNumber)
      }
      continue
    }
    const episodeNumber = Number(token)
    if (!Number.isInteger(episodeNumber) || episodeNumber <= 0) return []
    numbers.push(episodeNumber)
  }
  return [...new Set(numbers)]
}

interface BuildManualMatchInput {
  candidate: MatchCandidate | null
  seasonNumber: string
  episodeExpression: string
}

export function buildManualMatchInput({
  candidate,
  seasonNumber,
  episodeExpression,
}: BuildManualMatchInput): ManualMatchInput | null {
  if (!candidate || candidate.media_type === 'UNKNOWN') return null
  if (candidate.media_type === 'MOVIE') {
    return {
      tmdbId: candidate.tmdb_id,
      title: candidate.title,
      originalTitle: candidate.original_title,
      year: candidate.year,
      mediaType: 'MOVIE',
      seasonNumber: null,
      episodeNumbers: [],
    }
  }
  const parsedSeasonNumber = Number(seasonNumber)
  const episodeNumbers = parseEpisodeExpression(episodeExpression)
  if (
    !Number.isInteger(parsedSeasonNumber) ||
    parsedSeasonNumber < 0 ||
    episodeNumbers.length === 0
  ) {
    return null
  }
  return {
    tmdbId: candidate.tmdb_id,
    title: candidate.title,
    originalTitle: candidate.original_title,
    year: candidate.year,
    mediaType: 'TV',
    seasonNumber: parsedSeasonNumber,
    episodeNumbers,
  }
}
import {
  type ManualMatchInput,
  type MatchCandidate,
} from '@/types'
