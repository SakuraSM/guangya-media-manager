import { cn } from '@/lib/utils'

const BRAND_LOGO_SIZE_CLASSES = {
  sidebar: 'size-9 rounded-xl',
  login: 'size-14 rounded-2xl',
} as const

interface BrandLogoProps {
  size: keyof typeof BRAND_LOGO_SIZE_CLASSES
}

export function BrandLogo({ size }: BrandLogoProps) {
  return (
    <img
      src="/logo.png"
      alt=""
      aria-hidden="true"
      className={cn(
        'shrink-0 object-cover shadow-xs',
        BRAND_LOGO_SIZE_CLASSES[size],
      )}
      decoding="async"
      draggable={false}
    />
  )
}
