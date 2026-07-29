import { describe, expect, it } from 'vitest'
import { formatBytes, formatConfidence } from './format'

const SAMPLE_TERABYTES = 18.72
const BYTES_PER_UNIT = 1024
const TERABYTE_EXPONENT = 4
const SAMPLE_CONFIDENCE = 0.976

describe('formatBytes', () => {
  it('formats terabytes with one decimal', () => {
    expect(
      formatBytes(SAMPLE_TERABYTES * BYTES_PER_UNIT ** TERABYTE_EXPONENT),
    ).toBe('18.7 TB')
  })

  it('formats zero bytes', () => {
    expect(formatBytes(0)).toBe('0 B')
  })
})

describe('formatConfidence', () => {
  it('formats confidence as a rounded percentage', () => {
    expect(formatConfidence(SAMPLE_CONFIDENCE)).toBe('98%')
  })
})
