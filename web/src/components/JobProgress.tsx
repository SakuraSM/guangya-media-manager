import {
  BrainCircuit,
  Check,
  Copy,
  Database,
  FolderSearch,
  Link2,
} from 'lucide-react'
import type { Job } from '../types'
import { PERCENT_SCALE } from '../constants'

const STAGES = [
  { label: '扫描', icon: FolderSearch, boundary: 0.18 },
  { label: '识别', icon: BrainCircuit, boundary: 0.38 },
  { label: '匹配', icon: Link2, boundary: 0.5 },
  { label: '复制', icon: Copy, boundary: 0.85 },
  { label: '刮削', icon: Database, boundary: 1 },
] as const

interface JobProgressProps {
  job: Job
}

export function JobProgress({ job }: JobProgressProps) {
  return (
    <section className="job-progress-panel" aria-labelledby="active-job-title">
      <div className="job-progress-heading">
        <div>
          <div className="eyeline-row">
            <span className="pulse-dot" aria-hidden="true" />
            <span>正在整理</span>
          </div>
          <h2 id="active-job-title">{job.name}</h2>
          <p>
            来源：{job.source_directory_path}
            <br />
            目标：{job.target_directory_path}
          </p>
        </div>
        <div className="progress-number">
          <strong>{Math.round(job.progress * PERCENT_SCALE)}%</strong>
          <span>{job.current_stage}</span>
        </div>
      </div>
      <div
        className="stage-rail"
        aria-label={`任务进度 ${Math.round(job.progress * PERCENT_SCALE)}%`}
      >
        <div className="stage-line">
          <span style={{ width: `${job.progress * PERCENT_SCALE}%` }} />
        </div>
        {STAGES.map((stage) => {
          const Icon = stage.icon
          const isComplete = job.progress >= stage.boundary
          const previousBoundary =
            STAGES[Math.max(0, STAGES.indexOf(stage) - 1)]?.boundary ?? 0
          const isActive = !isComplete && job.progress >= previousBoundary
          return (
            <div
              className={`stage${isComplete ? ' stage-complete' : ''}${
                isActive ? ' stage-active' : ''
              }`}
              key={stage.label}
            >
              <span className="stage-icon">
                {isComplete ? <Check size={18} /> : <Icon size={18} />}
              </span>
              <strong>{stage.label}</strong>
              <small>{isComplete ? '已完成' : isActive ? '进行中' : '等待中'}</small>
            </div>
          )
        })}
      </div>
    </section>
  )
}
