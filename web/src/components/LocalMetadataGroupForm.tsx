import { useState } from 'react'
import { Database } from 'lucide-react'
import type { LocalMetadataGroupInput, MediaMatch } from '@/types'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface LocalMetadataGroupFormProps {
  mediaMatch: MediaMatch
  isSaving: boolean
  onSubmit: (metadata: LocalMetadataGroupInput) => void
}

export function LocalMetadataGroupForm({
  mediaMatch,
  isSaving,
  onSubmit,
}: LocalMetadataGroupFormProps) {
  const [title, setTitle] = useState(mediaMatch.parsed_title)
  const [year, setYear] = useState(mediaMatch.parsed_year?.toString() ?? '')
  const [seasonNumber, setSeasonNumber] = useState(
    (mediaMatch.season_number ?? 1).toString(),
  )

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedTitle = title.trim()
    if (!normalizedTitle) return
    onSubmit({
      title: normalizedTitle,
      year: year ? Number(year) : null,
      seasonNumber: Number(seasonNumber),
    })
  }

  return (
    <form className="space-y-3 rounded-lg border p-3" onSubmit={handleSubmit}>
      <Alert>
        <Database aria-hidden="true" />
        <AlertTitle>TMDB 未收录？</AlertTitle>
        <AlertDescription>
          使用本地元数据一次批准整部短剧。系统会从每个文件名自动推断集号，不会伪造 TMDB ID。
        </AlertDescription>
      </Alert>
      <div className="space-y-2">
        <Label htmlFor="local-title">剧名</Label>
        <Input id="local-title" value={title} onChange={(event) => setTitle(event.target.value)} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="local-year">年份（可选）</Label>
          <Input id="local-year" inputMode="numeric" value={year} onChange={(event) => setYear(event.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="local-season">季号</Label>
          <Input id="local-season" inputMode="numeric" min="0" type="number" value={seasonNumber} onChange={(event) => setSeasonNumber(event.target.value)} />
        </div>
      </div>
      <Button className="w-full" type="submit" disabled={isSaving || !title.trim()}>
        使用本地元数据整理整组
      </Button>
    </form>
  )
}
