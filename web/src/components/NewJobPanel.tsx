import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, ScanSearch, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'
import type { CloudDirectory, CreateJobInput } from '../types'
import { DirectoryPicker } from './DirectoryPicker'
import { ErrorNotice } from './ErrorNotice'

const DEFAULT_CONFIG: CreateJobInput['config'] = {
  generate_nfo: true,
  download_poster: true,
  download_fanart: true,
  download_season_poster: true,
  rename_subtitles: true,
  auto_approve_threshold: 0.9,
  review_threshold: 0.65,
}

interface NewJobPanelProps {
  onCreated: () => void
}

export function NewJobPanel({ onCreated }: NewJobPanelProps) {
  const queryClient = useQueryClient()
  const [sourceDirectory, setSourceDirectory] = useState<CloudDirectory | null>(null)
  const [targetDirectory, setTargetDirectory] = useState<CloudDirectory | null>(null)
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const createMutation = useMutation({
    mutationFn: async (input: CreateJobInput) => {
      const job = await api.createJob(input)
      await api.scanJob(job.id)
      return job
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['jobs'] })
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      onCreated()
    },
  })

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!sourceDirectory || !targetDirectory) return
    createMutation.mutate({
      name: `${sourceDirectory.name} · AI 整理`,
      source_directory_id: sourceDirectory.id,
      source_directory_path: sourceDirectory.path,
      target_directory_id: targetDirectory.id,
      target_directory_path: targetDirectory.path,
      config,
    })
  }

  const handleConfigChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fieldName = event.target.name as keyof typeof config
    setConfig((currentConfig) => ({
      ...currentConfig,
      [fieldName]: event.target.checked,
    }))
  }

  return (
    <form className="new-job-panel" onSubmit={handleSubmit}>
      <div className="stepper" aria-label="任务创建步骤">
        {['选择目录', '识别规则', '预扫描', '审核执行'].map((step, index) => (
          <div className={index === 0 ? 'step step-active' : 'step'} key={step}>
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </div>
      <div className="new-job-grid">
        <DirectoryPicker
          id="source-directory"
          label="源目录"
          value={sourceDirectory}
          onSelect={setSourceDirectory}
        />
        <DirectoryPicker
          id="target-directory"
          label="输出目录"
          value={targetDirectory}
          onSelect={setTargetDirectory}
        />
        <label className="field">
          <span>整理模式</span>
          <select value="copy" disabled>
            <option value="copy">复制后整理</option>
          </select>
        </label>
        <label className="field">
          <span>媒体布局</span>
          <select value="plex" disabled>
            <option value="plex">Plex / Jellyfin 通用</option>
          </select>
        </label>
      </div>
      <fieldset className="option-fieldset">
        <legend>额外操作</legend>
        <div className="option-row">
          {[
            ['generate_nfo', '生成 NFO'],
            ['download_poster', '下载海报'],
            ['download_fanart', '下载背景图'],
            ['download_season_poster', '下载季度海报'],
            ['rename_subtitles', '重命名字幕'],
          ].map(([name, label]) => (
            <label className="checkbox-label" key={name}>
              <input
                type="checkbox"
                name={name}
                checked={Boolean(config[name as keyof typeof config])}
                onChange={handleConfigChange}
              />
              <span className="custom-checkbox" aria-hidden="true">
                <Check size={12} />
              </span>
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="safe-operation-note">
        <ShieldCheck size={19} aria-hidden="true" />
        <div>
          <strong>安全执行策略</strong>
          <span>源目录零写入、目标同名不覆盖、失败暂存内容不自动删除。</span>
        </div>
      </div>
      {createMutation.isError ? <ErrorNotice message={createMutation.error.message} /> : null}
      <div className="panel-actions">
        <button
          className="button button-primary"
          type="submit"
          disabled={!sourceDirectory || !targetDirectory || createMutation.isPending}
        >
          <ScanSearch size={17} aria-hidden="true" />
          {createMutation.isPending ? '正在创建并扫描…' : '创建并开始预扫描'}
        </button>
      </div>
    </form>
  )
}
