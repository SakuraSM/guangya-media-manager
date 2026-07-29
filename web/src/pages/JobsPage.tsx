import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Plus, Rows3 } from 'lucide-react'
import { api } from '../api/client'
import { PERCENT_SCALE } from '../constants'
import { ErrorNotice } from '../components/ErrorNotice'
import { LoadingScreen } from '../components/LoadingScreen'
import { NewJobPanel } from '../components/NewJobPanel'
import { StatusBadge } from '../components/StatusBadge'
import { formatBytes, formatDateTime } from '../utils/format'

export function JobsPage() {
  const [isCreating, setIsCreating] = useState(false)
  const jobsQuery = useQuery({
    queryKey: ['jobs'],
    queryFn: api.getJobs,
    refetchInterval: 4_000,
  })

  if (jobsQuery.isPending) {
    return <LoadingScreen label="正在加载整理任务" />
  }
  if (jobsQuery.isError) {
    return <ErrorNotice message={jobsQuery.error.message} />
  }

  return (
    <div className="page-stack">
      <section className="page-command-bar">
        <div>
          <h2>整理任务</h2>
          <p>先预扫描并审核识别结果，再执行复制与刮削。</p>
        </div>
        <button
          className="button button-primary"
          type="button"
          onClick={() => setIsCreating((current) => !current)}
          aria-expanded={isCreating}
        >
          <Plus size={17} aria-hidden="true" />
          {isCreating ? '收起创建面板' : '新建整理任务'}
        </button>
      </section>

      {isCreating ? <NewJobPanel onCreated={() => setIsCreating(false)} /> : null}

      <section className="table-panel">
        <div className="section-heading">
          <div>
            <h2>任务记录</h2>
            <p>{jobsQuery.data.length} 个任务 · 自动刷新状态</p>
          </div>
          <Rows3 size={20} aria-hidden="true" />
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>任务名称</th>
                <th>源目录 → 输出目录</th>
                <th>识别结果</th>
                <th>复制体积</th>
                <th>进度</th>
                <th>状态</th>
                <th>
                  <span className="visually-hidden">操作</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {jobsQuery.data.map((job) => (
                <tr key={job.id}>
                  <td>
                    <strong>{job.name}</strong>
                    <small>{formatDateTime(job.created_at)}</small>
                  </td>
                  <td className="path-flow">
                    <span>{job.source_directory_path}</span>
                    <ArrowRight size={13} aria-hidden="true" />
                    <span>{job.target_directory_path}</span>
                  </td>
                  <td>
                    <span className="count-success">{job.approved_items} 通过</span>
                    <span className="count-warning">{job.review_items} 审核</span>
                    <span className="count-danger">{job.failed_items} 异常</span>
                  </td>
                  <td>{formatBytes(job.copied_bytes)}</td>
                  <td className="progress-cell">
                    <span>{Math.round(job.progress * PERCENT_SCALE)}%</span>
                    <div className="progress-track progress-track-small">
                      <span style={{ width: `${job.progress * PERCENT_SCALE}%` }} />
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td>
                    <a
                      className="table-action"
                      href={`/review?job=${encodeURIComponent(job.id)}`}
                    >
                      查看详情
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
