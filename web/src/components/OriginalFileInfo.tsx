type OriginalFileInfoVariant = 'compact' | 'detail'

interface OriginalFileInfoProps {
  filename: string
  sourcePath: string
  variant?: OriginalFileInfoVariant
}

export function OriginalFileInfo({
  filename,
  sourcePath,
  variant = 'compact',
}: OriginalFileInfoProps) {
  if (variant === 'detail') {
    return (
      <dl className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-xs">
        <dt className="text-muted-foreground">文件名</dt>
        <dd className="break-all font-medium">{filename}</dd>
        <dt className="text-muted-foreground">原始地址</dt>
        <dd className="break-all font-mono text-[0.68rem] leading-relaxed">{sourcePath}</dd>
      </dl>
    )
  }

  return (
    <dl className="min-w-0 space-y-0.5 text-[0.68rem] text-muted-foreground">
      <div className="flex min-w-0 items-center gap-1.5">
        <dt className="shrink-0">文件</dt>
        <dd className="min-w-0 truncate" title={filename}>
          {filename}
        </dd>
      </div>
      <div className="flex min-w-0 items-center gap-1.5">
        <dt className="shrink-0">地址</dt>
        <dd className="min-w-0 truncate font-mono text-[0.64rem]" title={sourcePath}>
          {sourcePath}
        </dd>
      </div>
    </dl>
  )
}
