import type { CreateJobInput } from '@/types'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from '@/components/ui/field'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

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

export function ScrapingOptions({ config, onChange }: ScrapingOptionsProps) {
  return (
    <FieldSet className="rounded-xl border bg-muted/20 p-4">
      <FieldLegend>刮削与兼容选项</FieldLegend>
      <FieldGroup className="grid gap-4 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="scrape-metadata-language">TMDB 元数据语言</FieldLabel>
          <Select
            value={config.scrape_metadata_language}
            onValueChange={(value) =>
              onChange({
                scrape_metadata_language:
                  value as JobScrapingConfig['scrape_metadata_language'],
              })
            }
          >
            <SelectTrigger id="scrape-metadata-language" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="zh-CN">简体中文</SelectItem>
                <SelectItem value="en-US">English</SelectItem>
                <SelectItem value="ja-JP">日本語</SelectItem>
                <SelectItem value="ko-KR">한국어</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="scrape-image-quality">TMDB 图片质量</FieldLabel>
          <Select
            value={config.scrape_image_quality}
            onValueChange={(value) =>
              onChange({
                scrape_image_quality:
                  value as JobScrapingConfig['scrape_image_quality'],
              })
            }
          >
            <SelectTrigger id="scrape-image-quality" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="STANDARD">标准图（节省流量）</SelectItem>
                <SelectItem value="ORIGINAL">原图（更清晰）</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
      </FieldGroup>
      <div data-slot="checkbox-group" className="grid gap-2 sm:grid-cols-2">
        {SCRAPING_CHECKBOXES.map(({ name, label }) => (
          <Field key={name} orientation="horizontal">
            <Checkbox
              id={`scrape-${name}`}
              name={name}
              checked={config[name]}
              onCheckedChange={(checked) => onChange({ [name]: checked === true })}
            />
            <FieldLabel htmlFor={`scrape-${name}`}>
              <FieldContent>
                <FieldTitle>{label}</FieldTitle>
              </FieldContent>
            </FieldLabel>
          </Field>
        ))}
      </div>
      <FieldDescription>
        默认采用“仅生成缺失资产”的安全语义；暂存区不覆盖正式媒体库中的同名文件。
      </FieldDescription>
    </FieldSet>
  )
}
