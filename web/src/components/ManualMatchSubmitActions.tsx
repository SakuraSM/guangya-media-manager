import { Check } from 'lucide-react'
import type { ManualMatchInput, MediaType } from '@/types'
import { Button } from '@/components/ui/button'

interface ManualMatchSubmitActionsProps {
  mediaType: MediaType | null
  input: ManualMatchInput | null
  isPreviewReady: boolean
  isSaving: boolean
  onSubmitCurrent: (match: ManualMatchInput) => void
  onSubmitGroup: (match: ManualMatchInput) => void
}

export function ManualMatchSubmitActions({
  mediaType,
  input,
  isPreviewReady,
  isSaving,
  onSubmitCurrent,
  onSubmitGroup,
}: ManualMatchSubmitActionsProps) {
  const isDisabled = !isPreviewReady || !input || isSaving
  const submitCurrent = () => {
    if (input) onSubmitCurrent(input)
  }
  const submitGroup = () => {
    if (input) onSubmitGroup(input)
  }

  if (mediaType !== 'TV') {
    return (
      <Button type="button" disabled={isDisabled} onClick={submitCurrent}>
        <Check data-icon="inline-start" aria-hidden="true" />
        保存并采用手动匹配
      </Button>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs leading-relaxed text-muted-foreground">
        整剧应用会统一剧名和 TMDB 元数据，并保留其他文件已有的季、集编号。
        无法确定季集的文件会继续留在审核中。
      </p>
      <Button type="button" disabled={isDisabled} onClick={submitGroup}>
        <Check data-icon="inline-start" aria-hidden="true" />
        应用到整个剧集
      </Button>
      <Button
        type="button"
        variant="outline"
        disabled={isDisabled}
        onClick={submitCurrent}
      >
        仅应用当前文件
      </Button>
    </div>
  )
}
