import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Plus, RefreshCw, Rows3 } from 'lucide-react'
import { api } from '@/api/client'
import { PaginationControls } from '@/components/PaginationControls'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LoadingScreen } from '@/components/LoadingScreen'
import { NewJobPanel } from '@/components/NewJobPanel'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { PERCENT_SCALE } from '@/constants'
import { formatBytes, formatDateTime } from '@/utils/format'
import { useJobEventStream } from '@/hooks/useJobEvents'

const DEFAULT_PAGE_SIZE = 20

export function JobsPage() {
  const eventStream = useJobEventStream()
  const [isCreating, setIsCreating] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const jobsQuery = useQuery({
    queryKey: ['jobs', 'page', page, pageSize],
    queryFn: () => api.getJobsPage(page, pageSize),
    placeholderData: (previousData) => previousData,
    refetchInterval: eventStream.connectionState === 'CONNECTED' ? false : 4_000,
  })

  if (jobsQuery.isPending) {
    return <LoadingScreen label="正在加载整理任务" />
  }
  if (jobsQuery.isError) {
    return <ErrorNotice message={jobsQuery.error.message} />
  }

  const jobs = jobsQuery.data.items

  return (
    <div className="flex h-[calc(100svh-7rem)] min-h-[36rem] flex-col gap-4">
      <section className="flex shrink-0 flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">整理任务</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            任务按源文件到目标目录统一展示，在线时实时更新。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            type="button"
            onClick={() => void jobsQuery.refetch()}
            disabled={jobsQuery.isFetching}
          >
            <RefreshCw
              data-icon="inline-start"
              className={jobsQuery.isFetching ? 'animate-spin' : undefined}
              aria-hidden="true"
            />
            {jobsQuery.isFetching ? '刷新中' : '刷新'}
          </Button>
          <Button type="button" onClick={() => setIsCreating(true)}>
            <Plus data-icon="inline-start" aria-hidden="true" />
            新建整理任务
          </Button>
        </div>
      </section>

      <Card className="min-h-0 flex-1 gap-0 overflow-hidden py-0">
        <CardHeader className="flex-row items-center justify-between border-b px-4 py-4">
          <div className="flex flex-col gap-1">
            <CardTitle>全部任务</CardTitle>
            <CardDescription>{jobsQuery.data.total} 个任务</CardDescription>
          </div>
          <Rows3 className="text-muted-foreground" aria-hidden="true" />
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-auto p-0">
          {jobs.length ? (
            <Table className="min-w-[1080px]">
              <TableHeader className="sticky top-0 bg-card shadow-[0_1px_0_var(--border)]">
                <TableRow>
                  <TableHead className="w-52 pl-4">任务</TableHead>
                  <TableHead>源文件 → 目标目录</TableHead>
                  <TableHead className="w-28">文件</TableHead>
                  <TableHead className="w-32">审批结果</TableHead>
                  <TableHead className="w-36">执行进度</TableHead>
                  <TableHead className="w-36">状态</TableHead>
                  <TableHead className="w-16">
                    <span className="sr-only">操作</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => {
                  const progress = Math.round(job.progress * PERCENT_SCALE)
                  return (
                    <TableRow key={job.id} className="h-28">
                      <TableCell className="pl-4">
                        <strong className="block max-w-48 truncate font-medium">
                          {job.name}
                        </strong>
                        <span className="mt-1 block text-[0.65rem] font-medium text-primary">
                          {job.trigger_type === 'SCHEDULED'
                            ? '定时规则'
                            : job.trigger_type === 'FAILED_RETRY'
                              ? '失败重试'
                            : job.trigger_type === 'DIRTY_RETRY'
                              ? '变化补跑'
                              : '手动任务'}
                        </span>
                        <small className="mt-1 block text-xs text-muted-foreground">
                          {formatDateTime(job.created_at)}
                        </small>
                      </TableCell>
                      <TableCell>
                        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3">
                          <PathCell label="源文件" path={job.source_directory_path} />
                          <ArrowRight className="text-muted-foreground" aria-hidden="true" />
                          <PathCell label="目标目录" path={job.target_directory_path} />
                        </div>
                      </TableCell>
                      <TableCell>
                        <strong className="block tabular-nums">{job.total_items}</strong>
                        <small className="mt-1 block text-xs text-muted-foreground">
                          {job.rule_id
                            ? `${job.changed_items} 个变化 · ${job.skipped_directories} 个目录无变化`
                            : `${formatBytes(job.copied_bytes)} 已复制`}
                        </small>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1 text-xs tabular-nums">
                          <span className="text-success">{job.approved_items} 通过</span>
                          <span className="text-warning">{job.review_items} 待审核</span>
                          {job.failed_items > 0 ? (
                            <span className="text-destructive">{job.failed_items} 异常</span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="mb-2 block text-sm tabular-nums">{progress}%</span>
                        <Progress value={progress} aria-label={`执行进度 ${progress}%`} />
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={job.status} />
                        <small className="mt-2 block max-w-32 truncate text-xs text-muted-foreground">
                          {job.current_stage}
                        </small>
                      </TableCell>
                      <TableCell>
                        <Button variant="link" size="sm" asChild>
                          <a href={`/review?job=${encodeURIComponent(job.id)}`}>查看</a>
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          ) : (
            <Empty className="h-full min-h-72">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Rows3 aria-hidden="true" />
                </EmptyMedia>
                <EmptyTitle>还没有整理任务</EmptyTitle>
                <EmptyDescription>
                  新建任务后，扫描、审批和整理状态会显示在这里。
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </CardContent>
        <PaginationControls
          page={page}
          pages={jobsQuery.data.pages}
          pageSize={pageSize}
          total={jobsQuery.data.total}
          isLoading={jobsQuery.isFetching}
          ariaLabel="任务列表分页"
          onPageChange={setPage}
          onPageSizeChange={(nextPageSize) => {
            setPage(1)
            setPageSize(nextPageSize)
          }}
        />
      </Card>

      <Dialog open={isCreating} onOpenChange={setIsCreating}>
        <DialogContent
          className="max-h-[92svh] overflow-y-auto sm:max-w-4xl"
          showCloseButton={false}
        >
          <DialogHeader className="sr-only">
            <DialogTitle>新建整理任务</DialogTitle>
            <DialogDescription>选择目录、识别规则和自动化策略。</DialogDescription>
          </DialogHeader>
          <NewJobPanel
            onCreated={() => {
              setIsCreating(false)
              setPage(1)
            }}
            onCancel={() => setIsCreating(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}

function PathCell({ label, path }: { label: string; path: string }) {
  return (
    <div className="min-w-0">
      <span className="block text-[0.7rem] text-muted-foreground">{label}</span>
      <code className="mt-1 block max-w-72 truncate text-xs" title={path}>
        {path}
      </code>
    </div>
  )
}
