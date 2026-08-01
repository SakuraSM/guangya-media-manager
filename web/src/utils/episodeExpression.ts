import {
  type ManualMatchInput,
  type MatchCandidate,
} from '@/types'

const EPISODE_SEPARATOR_PATTERN = /[,，\s]+/
const EPISODE_RANGE_PATTERN = /^(?<start>\d+)-(?<end>\d+)$/
const SEASON_EPISODE_RANGE_PATTERN = /S(?<season>\d{1,2})[ ._-]*E(?<start>\d{1,3})[-_](?:E)?(?<end>\d{1,3})/i
const SEASON_EPISODE_PATTERN = /S(?<season>\d{1,2})[ ._-]*E(?<episode>\d{1,3})/i
const ALTERNATE_EPISODE_PATTERN = /(?<season>\d{1,2})x(?<episode>\d{1,3})/i
const STANDALONE_EPISODE_PATTERN = /(?:^|[ ._-])(?:E|EP|第)(?<episode>\d{1,3})(?:集|话)?(?:$|[ ._-])/i
const BARE_EPISODE_PATTERN = /^(?:第)?(?<start>\d{1,3})(?:[-至](?<end>\d{1,3}))?(?:集|话)?$/
const PATH_SEASON_PATTERN = /(?:^|[/\\ ._-])(?:Season[ ._-]*|S)(?<season>\d{1,2})(?=$|[/\\ ._-])/gi
const CHINESE_PATH_SEASON_PATTERN = /第(?<season>\d{1,2})季/g
const MAX_EPISODE_RANGE_SIZE = 20
const DEFAULT_TV_SEASON_NUMBER = 1
const MEDIA_INDEX_WIDTH = 2

export interface EpisodeMappingSuggestion {
  seasonNumber: number
  episodeNumbers: number[]
  source: 'scan' | 'filename'
}

interface EpisodeSourceInput {
  filename: string
  sourcePath: string
  seasonNumber: number | null
  episodeNumbers: number[]
}

export function parseEpisodeExpression(value: string): number[] {
  const numbers: number[] = []
  for (const token of value.trim().split(EPISODE_SEPARATOR_PATTERN)) {
    if (!token) continue
    const rangeMatch = EPISODE_RANGE_PATTERN.exec(token)
    if (rangeMatch) {
      const start = numberFromGroup(rangeMatch, 'start')
      const end = numberFromGroup(rangeMatch, 'end')
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

export function inferManualEpisodeMapping(
  input: EpisodeSourceInput,
): EpisodeMappingSuggestion | null {
  if (input.seasonNumber !== null && input.episodeNumbers.length > 0) {
    return {
      seasonNumber: input.seasonNumber,
      episodeNumbers: input.episodeNumbers,
      source: 'scan',
    }
  }

  const filenameStem = input.filename.replace(/\.[^.]+$/, '')
  const filenameMapping = parseEpisodeMappingFromFilename(filenameStem)
  if (!filenameMapping) return null
  return {
    seasonNumber:
      filenameMapping.seasonNumber ??
      inferSeasonNumberFromPath(input.sourcePath) ??
      DEFAULT_TV_SEASON_NUMBER,
    episodeNumbers: filenameMapping.episodeNumbers,
    source: 'filename',
  }
}

export function formatEpisodeMappingLabel(
  mapping: EpisodeMappingSuggestion,
): string {
  const seasonLabel = String(mapping.seasonNumber).padStart(MEDIA_INDEX_WIDTH, '0')
  const episodeLabel = mapping.episodeNumbers
    .map(
      (episodeNumber) =>
        `E${String(episodeNumber).padStart(MEDIA_INDEX_WIDTH, '0')}`,
    )
    .join('')
  return `S${seasonLabel}${episodeLabel}`
}

interface FilenameEpisodeMapping {
  seasonNumber: number | null
  episodeNumbers: number[]
}

function parseEpisodeMappingFromFilename(
  filenameStem: string,
): FilenameEpisodeMapping | null {
  const rangeMatch = SEASON_EPISODE_RANGE_PATTERN.exec(filenameStem)
  if (rangeMatch) {
    const episodeNumbers = expandEpisodeRange(
      numberFromGroup(rangeMatch, 'start'),
      numberFromGroup(rangeMatch, 'end'),
    )
    return episodeNumbers.length
      ? { seasonNumber: numberFromGroup(rangeMatch, 'season'), episodeNumbers }
      : null
  }
  const seasonEpisodeMatch = SEASON_EPISODE_PATTERN.exec(filenameStem)
  if (seasonEpisodeMatch) {
    return {
      seasonNumber: numberFromGroup(seasonEpisodeMatch, 'season'),
      episodeNumbers: [numberFromGroup(seasonEpisodeMatch, 'episode')],
    }
  }
  const alternateMatch = ALTERNATE_EPISODE_PATTERN.exec(filenameStem)
  if (alternateMatch) {
    return {
      seasonNumber: numberFromGroup(alternateMatch, 'season'),
      episodeNumbers: [numberFromGroup(alternateMatch, 'episode')],
    }
  }
  const standaloneMatch = STANDALONE_EPISODE_PATTERN.exec(filenameStem)
  if (standaloneMatch) {
    return {
      seasonNumber: null,
      episodeNumbers: [numberFromGroup(standaloneMatch, 'episode')],
    }
  }
  const bareMatch = BARE_EPISODE_PATTERN.exec(filenameStem)
  if (!bareMatch) return null
  const startEpisode = numberFromGroup(bareMatch, 'start')
  const endEpisode = bareMatch.groups?.end
    ? numberFromGroup(bareMatch, 'end')
    : startEpisode
  const episodeNumbers = expandEpisodeRange(startEpisode, endEpisode)
  return episodeNumbers.length ? { seasonNumber: null, episodeNumbers } : null
}

function expandEpisodeRange(startEpisode: number, endEpisode: number): number[] {
  if (
    startEpisode <= 0 ||
    endEpisode < startEpisode ||
    endEpisode - startEpisode + 1 > MAX_EPISODE_RANGE_SIZE
  ) {
    return []
  }
  return Array.from(
    { length: endEpisode - startEpisode + 1 },
    (_, index) => startEpisode + index,
  )
}

function inferSeasonNumberFromPath(sourcePath: string): number | null {
  const matches = [...sourcePath.matchAll(PATH_SEASON_PATTERN)]
  const chineseMatches = [...sourcePath.matchAll(CHINESE_PATH_SEASON_PATTERN)]
  const lastMatch = chineseMatches.at(-1) ?? matches.at(-1)
  return lastMatch ? numberFromGroup(lastMatch, 'season') : null
}

function numberFromGroup(match: RegExpExecArray, groupName: string): number {
  return Number(match.groups?.[groupName])
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
