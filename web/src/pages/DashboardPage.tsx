import { AlertTriangle, CheckCircle2, Database, Files, Plus } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { ErrorNotice } from '@/components/ErrorNotice'
import { JobProgress } from '@/components/JobProgress'
import { LoadingScreen } from '@/components/LoadingScreen'
import { MetricCard } from '@/components/MetricCard'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Empty,
  EmptyContent,
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
import { cn } from '@/lib/utils'

export function DashboardPage() {
  const dashboardQuery = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.getDashboard,
    refetchInterval: 5_000,
  })

  if (dashboardQuery.isPending) {
    return <LoadingScreen label="正在加载看板" />
  }
  if (dashboardQuery.isError) {
    return <ErrorNotice message={dashboardQuery.error.message} />
  }

  const dashboard = dashboardQuery.data
  const account = dashboard.account
  const usagePercentage =
    account && account.capacity_bytes > 0
      ? Math.round((account.used_bytes / account.capacity_bytes) * PERCENT_SCALE)
      : 0

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardContent className="grid items-center gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(18rem,1.4fr)_auto]">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-success/10 text-success">
              <CheckCircle2 aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <strong className="block truncate font-medium">
                {account ? '账号已连接' : '账号未连接'}
              </strong>
              <span className="block truncate text-sm text-muted-foreground">
                {account?.display_name ?? '前往设置连接光鸭账号'}
              </span>
            </div>
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between gap-4 text-sm">
              <strong>存储空间</strong>
              <span className="tabular-nums text-muted-foreground">
                {account ? `${formatBytes(account.used_bytes)} / ${formatBytes(account.capacity_bytes)}` : '—'}
              </span>
            </div>
            <Progress value={usagePercentage} aria-label={`存储空间已使用 ${usagePercentage}%`} />
            <small className="mt-2 block text-xs text-muted-foreground">
              已使用 {usagePercentage}% · 整理任务只做云内复制
            </small>
          </div>
          <Button asChild>
            <a href="/jobs">
              <Plus data-icon="inline-start" aria-hidden="true" />
              新建整理任务
            </a>
          </Button>
        </CardContent>
      </Card>

      {dashboard.active_job ? (
        <JobProgress job={dashboard.active_job} />
      ) : (
        <Card>
          <CardContent>
            <Empty className="min-h-52">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Database aria-hidden="true" />
                </EmptyMedia>
                <EmptyTitle>当前没有运行中的任务</EmptyTitle>
                <EmptyDescription>
                  选择一个源目录，先预扫描并审核识别结果。
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button variant="outline" asChild>
                  <a href="/jobs">创建整理任务</a>
                </Button>
              </EmptyContent>
            </Empty>
          </CardContent>
        </Card>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="任务指标">
        <MetricCard
          label="等待审核"
          value={String(dashboard.metrics.pending_review)}
          detail="需要人工确认的匹配"
          icon={Files}
          tone="amber"
        />
        <MetricCard
          label="今日完成"
          value={String(dashboard.metrics.completed_today)}
          detail="已安全复制的文件"
          icon={CheckCircle2}
          tone="green"
        />
        <MetricCard
          label="失败"
          value={String(dashboard.metrics.failed)}
          detail="可重试或人工处理"
          icon={AlertTriangle}
          tone="red"
        />
        <MetricCard
          label="存储变更"
          value={`+${formatBytes(dashboard.metrics.copied_bytes)}`}
          detail="累计云内复制体积"
          icon={Database}
          tone="blue"
        />
      </section>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="min-w-0 gap-0 py-0">
          <CardHeader className="flex-row items-center justify-between border-b py-4">
            <div>
              <CardTitle>最近整理任务</CardTitle>
              <CardDescription>所有写操作均保留审计记录</CardDescription>
            </div>
            <Button variant="link" size="sm" asChild>
              <a href="/jobs">查看全部</a>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <Table className="min-w-[720px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">任务</TableHead>
                  <TableHead>文件</TableHead>
                  <TableHead>进度</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>更新时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dashboard.recent_jobs.map((job) => {
                  const progress = Math.round(job.progress * PERCENT_SCALE)
                  return (
                    <TableRow key={job.id}>
                      <TableCell className="max-w-72 pl-4">
                        <strong className="block truncate font-medium">{job.name}</strong>
                        <small className="block truncate text-xs text-muted-foreground">
                          {job.target_directory_path}
                        </small>
                      </TableCell>
                      <TableCell className="tabular-nums">{job.total_items}</TableCell>
                      <TableCell className="min-w-28">
                        <span className="mb-1 block text-xs tabular-nums">{progress}%</span>
                        <Progress value={progress} aria-label={`任务进度 ${progress}%`} />
                      </TableCell>
                      <TableCell><StatusBadge status={job.status} /></TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(job.updated_at)}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>活动日志</CardTitle>
            <CardDescription>最近系统事件</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-4">
              {dashboard.recent_events.map((event) => (
                <li className="grid grid-cols-[auto_1fr] gap-3" key={event.id}>
                  <span
                    className={cn(
                      'mt-1.5 size-2 rounded-full bg-muted-foreground',
                      event.severity === 'error' && 'bg-destructive',
                      event.severity === 'warning' && 'bg-warning',
                      event.severity === 'success' && 'bg-success',
                    )}
                    aria-hidden="true"
                  />
                  <div className="min-w-0">
                    <strong className="block text-sm font-medium">{event.message}</strong>
                    <time className="text-xs text-muted-foreground" dateTime={event.created_at}>
                      {formatDateTime(event.created_at)}
                    </time>
                  </div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
