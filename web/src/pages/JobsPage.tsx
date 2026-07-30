import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Plus, RefreshCw, Rows3 } from 'lucide-react'
import { api } from '../api/client'
import { PaginationControls } from '../components/PaginationControls'
import { ErrorNotice } from '../components/ErrorNotice'
import { LoadingScreen } from '../components/LoadingScreen'
import { NewJobPanel } from '../components/NewJobPanel'
import { StatusBadge } from '../components/StatusBadge'
import { PERCENT_SCALE } from '../constants'
import { formatBytes, formatDateTime } from '../utils/format'

const DEFAULT_PAGE_SIZE = 20

export function JobsPage() {
  const [isCreating, setIsCreating] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const jobsQuery = useQuery({
    queryKey: ['jobs', 'page', page, pageSize],
    queryFn: () => api.getJobsPage(page, pageSize),
    placeholderData: (previousData) => previousData,
    refetchInterval: 4_000,
  })

  if (jobsQuery.isPending) {
    return <LoadingScreen label="正在加载整理任务" />
  }
  if (jobsQuery.isError) {
    return <ErrorNotice message={jobsQuery.error.message} />
  }

  const jobs = jobsQuery.data.items

  return (
    <div className="jobs-page">
      <section className="page-command-bar jobs-command-bar">
        <div>
          <h2>整理任务</h2>
          <p>任务按源文件到目标目录统一展示，状态每 4 秒自动刷新。</p>
        </div>
        <div className="jobs-command-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={() => {
              void jobsQuery.refetch()
            }}
            disabled={jobsQuery.isFetching}
          >
            <RefreshCw size={16} aria-hidden="true" />
            {jobsQuery.isFetching ? '刷新中' : '刷新'}
          </button>
          <button
            className="button button-primary"
            type="button"
            onClick={() => setIsCreating(true)}
            aria-expanded={isCreating}
          >
            <Plus size={17} aria-hidden="true" />
            新建整理任务
          </button>
        </div>
      </section>

      <section className="table-panel jobs-list-panel">
        <div className="section-heading jobs-list-heading">
          <div>
            <h2>全部任务</h2>
            <p>{jobsQuery.data.total} 个任务</p>
          </div>
          <Rows3 size={20} aria-hidden="true" />
        </div>
        <div className="table-scroll jobs-table-scroll">
          <table className="jobs-table">
            <thead>
              <tr>
                <th>任务</th>
                <th>源文件 → 目标目录</th>
                <th>文件</th>
                <th>审批结果</th>
                <th>执行进度</th>
                <th>状态</th>
                <th>
                  <span className="visually-hidden">操作</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td className="job-name-cell">
                    <strong>{job.name}</strong>
                    <small>{formatDateTime(job.created_at)}</small>
                  </td>
                  <td>
                    <div className="job-route">
                      <div>
                        <span>源文件</span>
                        <code title={job.source_directory_path}>
                          {job.source_directory_path}
                        </code>
                      </div>
                      <ArrowRight size={15} aria-hidden="true" />
                      <div>
                        <span>目标目录</span>
                        <code title={job.target_directory_path}>
                          {job.target_directory_path}
                        </code>
                      </div>
                    </div>
                  </td>
                  <td>
                    <strong>{job.total_items}</strong>
                    <small>{formatBytes(job.copied_bytes)} 已复制</small>
                  </td>
                  <td>
                    <div className="approval-summary">
                      <span className="count-success">{job.approved_items} 通过</span>
                      <span className="count-warning">{job.review_items} 待审核</span>
                      {job.failed_items > 0 ? (
                        <span className="count-danger">{job.failed_items} 异常</span>
                      ) : null}
                    </div>
                  </td>
                  <td className="progress-cell">
                    <span>{Math.round(job.progress * PERCENT_SCALE)}%</span>
                    <div className="progress-track progress-track-small">
                      <span style={{ width: `${job.progress * PERCENT_SCALE}%` }} />
                    </div>
                  </td>
                  <td className="job-status-cell">
                    <StatusBadge status={job.status} />
                    <small>{job.current_stage}</small>
                  </td>
                  <td>
                    <a
                      className="table-action"
                      href={`/review?job=${encodeURIComponent(job.id)}`}
                    >
                      查看
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {jobs.length === 0 ? (
            <div className="jobs-empty-state">
              <Rows3 size={24} aria-hidden="true" />
              <strong>还没有整理任务</strong>
              <span>新建任务后，扫描、审批和整理状态会显示在这里。</span>
            </div>
          ) : null}
        </div>
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
      </section>

      {isCreating ? (
        <div className="new-job-overlay" role="dialog" aria-modal="true">
          <NewJobPanel
            onCreated={() => {
              setIsCreating(false)
              setPage(1)
            }}
            onCancel={() => setIsCreating(false)}
          />
        </div>
      ) : null}
    </div>
  )
}
