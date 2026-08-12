import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { CreateJobInput } from '../types'
import { ScrapingOptions } from './ScrapingOptions'

const SECOND_CALL_INDEX = 2

const SCRAPING_CONFIG: CreateJobInput['config'] = {
  generate_nfo: true,
  download_poster: true,
  download_fanart: true,
  download_backdrop_alias: true,
  download_season_poster: true,
  download_episode_thumb: true,
  season_artwork_compat: true,
  scrape_metadata_language: 'zh-CN',
  scrape_image_quality: 'STANDARD',
  rename_subtitles: true,
      auto_approve_threshold: 0.9,
      review_threshold: 0.65,
      auto_approve_enabled: true,
      auto_execute_after_approval: false,
  naming_profile: 'UNIVERSAL_ENHANCED',
  extras_policy: 'EXCLUDE_REVIEWABLE',
  sample_max_mb: 300,
  exclude_globs: [],
  include_paths: [],
  output_layout: 'STANDARD',
  include_region_directory: true,
  quality_profile: 'QUALITY',
}

describe('ScrapingOptions', () => {
  it('updates metadata language and image quality', () => {
    const handleChange = vi.fn()

    render(
      <ScrapingOptions
        config={SCRAPING_CONFIG}
        onChange={handleChange}
      />,
    )

    fireEvent.click(screen.getByLabelText('TMDB 元数据语言'))
    fireEvent.click(screen.getByRole('option', { name: 'English' }))
    fireEvent.click(screen.getByLabelText('TMDB 图片质量'))
    fireEvent.click(screen.getByRole('option', { name: '原图（更清晰）' }))

    expect(handleChange).toHaveBeenNthCalledWith(1, {
      scrape_metadata_language: 'en-US',
    })
    expect(handleChange).toHaveBeenNthCalledWith(SECOND_CALL_INDEX, {
      scrape_image_quality: 'ORIGINAL',
    })
  })

  it('can disable the episode thumbnail scrape', () => {
    const handleChange = vi.fn()

    render(
      <ScrapingOptions
        config={SCRAPING_CONFIG}
        onChange={handleChange}
      />,
    )

    fireEvent.click(screen.getByLabelText('下载剧集缩略图'))

    expect(handleChange).toHaveBeenCalledWith({
      download_episode_thumb: false,
    })
  })
})
