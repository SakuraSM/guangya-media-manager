import { Check } from 'lucide-react'
import type { CreateJobInput } from '../types'

type JobScrapingConfig = CreateJobInput['config']

interface ScrapingOptionsProps {
  config: JobScrapingConfig
  onChange: (changes: Partial<JobScrapingConfig>) => void
}

const SCRAPING_CHECKBOXES: ReadonlyArray<{
  name: keyof Pick<
    JobScrapingConfig,
    | 'generate_nfo'
    | 'download_poster'
    | 'download_fanart'
    | 'download_backdrop_alias'
    | 'download_season_poster'
    | 'download_episode_thumb'
    | 'season_artwork_compat'
    | 'rename_subtitles'
  >
  label: string
}> = [
  { name: 'generate_nfo', label: '生成增强 NFO' },
  { name: 'download_poster', label: '下载海报' },
  { name: 'download_fanart', label: '下载背景图' },
  { name: 'download_backdrop_alias', label: '生成 backdrop/fanart 兼容别名' },
  { name: 'download_season_poster', label: '下载季度海报' },
  { name: 'season_artwork_compat', label: '季海报双位置兼容' },
  { name: 'download_episode_thumb', label: '下载剧集缩略图' },
  { name: 'rename_subtitles', label: '重命名字幕' },
]

export function ScrapingOptions({
  config,
  onChange,
}: ScrapingOptionsProps) {
  const handleCheckboxChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    onChange({
      [event.target.name]: event.target.checked,
    })
  }
  const handleLanguageChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    onChange({
      scrape_metadata_language:
        event.target.value as JobScrapingConfig['scrape_metadata_language'],
    })
  }
  const handleImageQualityChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    onChange({
      scrape_image_quality:
        event.target.value as JobScrapingConfig['scrape_image_quality'],
    })
  }

  return (
    <fieldset className="option-fieldset scraping-options">
      <legend>刮削与兼容选项</legend>
      <div className="scraping-select-grid">
        <label className="field" htmlFor="scrape-metadata-language">
          <span>TMDB 元数据语言</span>
          <select
            id="scrape-metadata-language"
            value={config.scrape_metadata_language}
            onChange={handleLanguageChange}
          >
            <option value="zh-CN">简体中文</option>
            <option value="en-US">English</option>
            <option value="ja-JP">日本語</option>
            <option value="ko-KR">한국어</option>
          </select>
        </label>
        <label className="field" htmlFor="scrape-image-quality">
          <span>TMDB 图片质量</span>
          <select
            id="scrape-image-quality"
            value={config.scrape_image_quality}
            onChange={handleImageQualityChange}
          >
            <option value="STANDARD">标准图（节省流量）</option>
            <option value="ORIGINAL">原图（更清晰）</option>
          </select>
        </label>
      </div>
      <div className="option-row">
        {SCRAPING_CHECKBOXES.map(({ name, label }) => (
          <label className="checkbox-label" key={name}>
            <input
              type="checkbox"
              name={name}
              checked={config[name]}
              onChange={handleCheckboxChange}
            />
            <span className="custom-checkbox" aria-hidden="true">
              <Check size={12} />
            </span>
            {label}
          </label>
        ))}
      </div>
      <p className="field-help">
        默认采用“仅生成缺失资产”的安全语义；暂存区不覆盖正式媒体库中的同名文件。
      </p>
    </fieldset>
  )
}
