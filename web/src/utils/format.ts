import { BYTES_PER_UNIT, LARGE_UNIT_INDEX, PERCENT_SCALE } from '../constants'

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const
const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B'
  const unitIndex = Math.min(
    Math.floor(Math.log(bytes) / Math.log(BYTES_PER_UNIT)),
    BYTE_UNITS.length - 1,
  )
  const unit = BYTE_UNITS[unitIndex] ?? 'B'
  return `${(bytes / BYTES_PER_UNIT ** unitIndex).toFixed(unitIndex >= LARGE_UNIT_INDEX ? 1 : 0)} ${unit}`
}

export function formatDateTime(value: string): string {
  return DATE_TIME_FORMATTER.format(new Date(value))
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * PERCENT_SCALE)}%`
}
