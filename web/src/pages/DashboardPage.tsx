import { AlertTriangle, CheckCircle2, Database, Files } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { PERCENT_SCALE } from '../constants'
import { ErrorNotice } from '../components/ErrorNotice'
import { JobProgress } from '../components/JobProgress'
import { LoadingScreen } from '../components/LoadingScreen'
import { MetricCard } from '../components/MetricCard'
import { StatusBadge } from '../components/StatusBadge'
import { formatBytes, formatDateTime } from '../utils/format'

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
    <div className="dashboard-layout">
      <section className="account-strip" aria-label="账号和存储状态">
        <article className="account-card">
          <span className="account-check" aria-hidden="true">
            <CheckCircle2 size={22} />
          </span>
          <div>
            <strong>{account ? '账号已连接' : '账号未连接'}</strong>
            <span>{account?.display_name ?? '前往设置连接光鸭账号'}</span>
          </div>
        </article>
        <article className="storage-card">
          <div className="storage-heading">
            <strong>存储空间</strong>
            <span>
              {account ? `${formatBytes(account.used_bytes)} / ${formatBytes(account.capacity_bytes)}` : '—'}
            </span>
          </div>
          <div className="progress-track">
            <span style={{ width: `${usagePercentage}%` }} />
          </div>
          <small>已使用 {usagePercentage}% · 整理任务只做云内复制</small>
        </article>
        <a className="button button-primary" href="/jobs">
          新建整理任务
        </a>
      </section>

      {dashboard.active_job ? (
        <JobProgress job={dashboard.active_job} />
      ) : (
        <section className="empty-panel">
          <Database size={28} aria-hidden="true" />
          <h2>当前没有运行中的任务</h2>
          <p>选择一个源目录，先预扫描并审核识别结果。</p>
          <a className="button button-secondary" href="/jobs">
            创建整理任务
          </a>
        </section>
      )}

      <section className="metric-grid" aria-label="任务指标">
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

      <div className="dashboard-lower">
        <section className="table-panel">
          <div className="section-heading">
            <div>
              <h2>最近整理任务</h2>
              <p>所有写操作均保留审计记录</p>
            </div>
            <a href="/jobs">查看全部</a>
          </div>
          <div className="table-scroll">
            <table className="recent-jobs-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>来源</th>
                  <th>文件</th>
                  <th>进度</th>
                  <th>状态</th>
                  <th>更新时间</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.recent_jobs.map((job) => (
                  <tr key={job.id}>
                    <td className="recent-job-title">
                      <strong>{job.name}</strong>
                      <small>{job.target_directory_path}</small>
                    </td>
                    <td className="recent-job-source">{job.source_directory_path}</td>
                    <td className="recent-job-files">{job.total_items}</td>
                    <td className="progress-cell">
                      <span>{Math.round(job.progress * PERCENT_SCALE)}%</span>
                      <div className="progress-track progress-track-small">
                        <span style={{ width: `${job.progress * PERCENT_SCALE}%` }} />
                      </div>
                    </td>
                    <td className="recent-job-status">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="recent-job-updated">{formatDateTime(job.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="activity-panel" aria-labelledby="activity-title">
          <div className="section-heading">
            <div>
              <h2 id="activity-title">活动日志</h2>
              <p>最近系统事件</p>
            </div>
          </div>
          <ol className="activity-list">
            {dashboard.recent_events.map((event) => (
              <li key={event.id}>
                <span className={`activity-dot activity-${event.severity}`} aria-hidden="true" />
                <div>
                  <strong>{event.message}</strong>
                  <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time>
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  )
}
