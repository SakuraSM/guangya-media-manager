import { Film } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PosterProps {
  src: string | null
  title: string
  size?: 'small' | 'medium' | 'large'
}

const SIZE_CLASSES = {
  small: 'h-16 w-11',
  medium: 'h-20 w-14',
  large: 'h-44 w-28 sm:h-52 sm:w-36',
} as const

export function Poster({ src, title, size = 'small' }: PosterProps) {
  const className = cn(
    'shrink-0 rounded-md border bg-muted object-cover shadow-xs',
    SIZE_CLASSES[size],
  )
  if (!src) {
    return (
      <div
        className={cn(className, 'grid place-items-center text-muted-foreground')}
        aria-label={`${title} 暂无海报`}
      >
        <Film aria-hidden="true" />
      </div>
    )
  }

  return (
    <img
      className={className}
      src={src}
      alt={`${title} 海报`}
      loading="lazy"
    />
  )
}
