import { Film } from 'lucide-react'

interface PosterProps {
  src: string | null
  title: string
  size?: 'small' | 'medium' | 'large'
}

export function Poster({ src, title, size = 'small' }: PosterProps) {
  if (!src) {
    return (
      <div className={`poster poster-${size} poster-fallback`} aria-label={`${title} 暂无海报`}>
        <Film size={20} aria-hidden="true" />
      </div>
    )
  }

  return (
    <img
      className={`poster poster-${size}`}
      src={src}
      alt={`${title} 海报`}
      loading="lazy"
    />
  )
}
