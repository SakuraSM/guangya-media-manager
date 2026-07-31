import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Folder } from 'lucide-react'
import { api } from '@/api/client'
import type { CloudDirectory } from '@/types'
import { ErrorNotice } from '@/components/ErrorNotice'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface DirectoryPickerProps {
  id: string
  label: string
  value: CloudDirectory | null
  onSelect: (directory: CloudDirectory) => void
}

const CLOUD_ROOT = {
  id: '',
  path: '/光鸭云盘',
  name: '光鸭云盘',
}

export function DirectoryPicker({ id, label, value, onSelect }: DirectoryPickerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [pathStack, setPathStack] = useState([CLOUD_ROOT])
  const current = pathStack[pathStack.length - 1] ?? CLOUD_ROOT
  const directoriesQuery = useQuery({
    queryKey: ['directories', current.id, current.path],
    queryFn: () => api.getDirectories(current.id, current.path),
    enabled: isOpen,
  })

  const handleOpenChange = (open: boolean) => {
    if (open) setPathStack([CLOUD_ROOT])
    setIsOpen(open)
  }
  const enterDirectory = (directory: CloudDirectory) => {
    setPathStack((stack) => [
      ...stack,
      { id: directory.id, path: directory.path, name: directory.name },
    ])
  }
  const chooseDirectory = (directory: CloudDirectory) => {
    onSelect(directory)
    setIsOpen(false)
  }

  return (
    <Field>
      <FieldLabel id={`${id}-label`}>{label}</FieldLabel>
      <Dialog open={isOpen} onOpenChange={handleOpenChange}>
        <DialogTrigger asChild>
          <Button
            variant="outline"
            type="button"
            className="h-10 w-full justify-start px-3 font-normal"
            aria-labelledby={`${id}-label`}
          >
            <Folder data-icon="inline-start" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate text-left">
              {value?.path ?? '请选择光鸭目录'}
            </span>
            <ChevronRight data-icon="inline-end" aria-hidden="true" />
          </Button>
        </DialogTrigger>
        <DialogContent className="w-[calc(100%-2rem)] min-w-0 sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>浏览云盘目录</DialogTitle>
            <DialogDescription>为“{label}”选择一个光鸭云盘目录。</DialogDescription>
          </DialogHeader>
          <div className="flex min-w-0 items-center gap-2 rounded-lg border bg-muted/40 p-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={pathStack.length === 1}
              onClick={() => setPathStack((stack) => stack.slice(0, -1))}
            >
              <ChevronLeft data-icon="inline-start" aria-hidden="true" />
              返回
            </Button>
            <code className="min-w-0 flex-1 break-all text-xs leading-relaxed">
              {current.path}
            </code>
          </div>
          {directoriesQuery.isError ? (
            <ErrorNotice message={directoriesQuery.error.message} />
          ) : null}
          <ScrollArea className="h-72 rounded-lg border">
            <div className="flex min-w-0 flex-col divide-y">
              {directoriesQuery.isPending ? (
                <p className="p-6 text-center text-sm text-muted-foreground">
                  正在读取目录…
                </p>
              ) : null}
              {directoriesQuery.data?.map((directory) => (
                <div
                  className="flex min-w-0 items-center gap-2 overflow-hidden p-2"
                  key={directory.id}
                >
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        className="h-auto min-w-0 flex-1 justify-start overflow-hidden py-2"
                        onClick={() => enterDirectory(directory)}
                        aria-label={`打开目录 ${directory.name}`}
                      >
                        <Folder data-icon="inline-start" aria-hidden="true" />
                        <span className="min-w-0 flex-1 overflow-hidden text-left">
                          <strong className="block truncate font-medium">
                            {directory.name}
                          </strong>
                          <small className="block truncate text-xs text-muted-foreground">
                            {directory.item_count === null
                              ? '项目数量未知'
                              : `${directory.item_count} 个项目`}
                          </small>
                        </span>
                        <ChevronRight
                          data-icon="inline-end"
                          className="shrink-0"
                          aria-hidden="true"
                        />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-[min(24rem,calc(100vw-2rem))] break-all">
                      {directory.path}
                    </TooltipContent>
                  </Tooltip>
                  <Button
                    variant="outline"
                    size="sm"
                    type="button"
                    className="shrink-0"
                    onClick={() => chooseDirectory(directory)}
                  >
                    选择
                  </Button>
                </div>
              ))}
              {!directoriesQuery.isPending && !directoriesQuery.data?.length ? (
                <p className="p-6 text-center text-sm text-muted-foreground">
                  这个目录下没有子目录
                </p>
              ) : null}
            </div>
          </ScrollArea>
          <DialogFooter>
            {current.id ? (
              <Button
                type="button"
                onClick={() =>
                  chooseDirectory({
                    id: current.id,
                    parent_id: '',
                    name: current.name,
                    path: current.path,
                    item_count: null,
                  })
                }
              >
                选择当前目录
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Field>
  )
}
