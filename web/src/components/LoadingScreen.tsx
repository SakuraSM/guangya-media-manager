import { LoaderCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface LoadingScreenProps {
  label: string
}

export function LoadingScreen({ label }: LoadingScreenProps) {
  return (
    <Card className="mx-auto w-full max-w-xl" role="status" aria-live="polite">
      <CardContent className="flex items-center gap-4 py-8">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent text-accent-foreground">
          <LoaderCircle className="animate-spin" aria-hidden="true" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <span className="text-sm font-medium">{label}</span>
          <Skeleton className="h-1.5 w-full" />
        </div>
      </CardContent>
    </Card>
  )
}
