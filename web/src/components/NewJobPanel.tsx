import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bot, ScanSearch, ShieldCheck, Workflow, X } from 'lucide-react'
import { api } from '@/api/client'
import type { CloudDirectory, CreateJobInput } from '@/types'
import { DEFAULT_ORGANIZE_CONFIG } from '@/organizeConfig'
import { DirectoryPicker } from '@/components/DirectoryPicker'
import { ErrorNotice } from '@/components/ErrorNotice'
import { ScrapingOptions } from '@/components/ScrapingOptions'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

interface NewJobPanelProps {
  onCreated: () => void
  onCancel: () => void
}

export function NewJobPanel({ onCreated, onCancel }: NewJobPanelProps) {
  const queryClient = useQueryClient()
  const [sourceDirectory, setSourceDirectory] = useState<CloudDirectory | null>(null)
  const [targetDirectory, setTargetDirectory] = useState<CloudDirectory | null>(null)
  const [config, setConfig] = useState(DEFAULT_ORGANIZE_CONFIG)
  const [excludeGlobsText, setExcludeGlobsText] = useState('')
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
      name: `${sourceDirectory.name} · 媒体整理`,
      source_directory_id: sourceDirectory.id,
      source_directory_path: sourceDirectory.path,
      target_directory_id: targetDirectory.id,
      target_directory_path: targetDirectory.path,
      config: {
        ...config,
        exclude_globs: excludeGlobsText
          .split(/\r?\n|,/)
          .map((pattern) => pattern.trim())
          .filter(Boolean),
      },
    })
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">新建整理任务</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            选择源目录和目标目录，扫描后按审核策略继续执行。
          </p>
        </div>
        <Button variant="ghost" size="icon" type="button" onClick={onCancel}>
          <X aria-hidden="true" />
          <span className="sr-only">关闭创建面板</span>
        </Button>
      </div>

      <ol className="grid grid-cols-4 gap-2" aria-label="任务创建步骤">
        {['选择目录', '识别规则', '预扫描', '审核执行'].map((step, index) => (
          <li className="flex min-w-0 items-center gap-2" key={step}>
            <Badge variant={index === 0 ? 'default' : 'secondary'}>{index + 1}</Badge>
            <span className="truncate text-xs text-muted-foreground">{step}</span>
          </li>
        ))}
      </ol>

      <FieldGroup className="grid gap-4 sm:grid-cols-2">
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
        <Field data-disabled>
          <FieldLabel htmlFor="organize-mode">整理模式</FieldLabel>
          <Input id="organize-mode" value="复制后整理" disabled readOnly />
        </Field>
        <Field>
          <FieldLabel htmlFor="media-layout">媒体布局</FieldLabel>
          <Select
            value={config.output_layout}
            onValueChange={(value) =>
              setConfig((current) => ({ ...current, output_layout: value as typeof current.output_layout }))
            }
          >
            <SelectTrigger id="media-layout" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="STANDARD">标准 Movies / TV</SelectItem>
              <SelectItem value="CLASSIFIED">按类型与地区分类</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="quality-profile">多版本偏好</FieldLabel>
          <Select
            value={config.quality_profile}
            onValueChange={(value) =>
              setConfig((current) => ({ ...current, quality_profile: value as typeof current.quality_profile }))
            }
          >
            <SelectTrigger id="quality-profile" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="QUALITY">质量优先</SelectItem>
              <SelectItem value="COMPATIBILITY">兼容优先</SelectItem>
              <SelectItem value="SPACE_SAVING">节省空间</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="extras-policy">附加视频</FieldLabel>
          <Select
            value={config.extras_policy}
            onValueChange={(value) =>
              setConfig((currentConfig) => ({
                ...currentConfig,
                extras_policy: value as typeof currentConfig.extras_policy,
              }))
            }
          >
            <SelectTrigger id="extras-policy" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="EXCLUDE_REVIEWABLE">识别后排除，可人工恢复</SelectItem>
                <SelectItem value="INCLUDE">分类保留</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="sample-threshold">样片阈值（MB）</FieldLabel>
          <Input
            id="sample-threshold"
            type="number"
            min={1}
            max={10_000}
            value={config.sample_max_mb}
            onChange={(event) =>
              setConfig((currentConfig) => ({
                ...currentConfig,
                sample_max_mb: Number(event.target.value),
              }))
            }
          />
        </Field>
        <Field className="sm:col-span-2">
          <FieldLabel htmlFor="exclude-globs">自定义排除规则</FieldLabel>
          <Textarea
            id="exclude-globs"
            value={excludeGlobsText}
            onChange={(event) => setExcludeGlobsText(event.target.value)}
            placeholder={'每行一个 glob，例如：临时/*\n*.torrent'}
            rows={3}
          />
          <FieldDescription>支持每行一个 glob，也可以使用逗号分隔。</FieldDescription>
        </Field>
        <Field className="sm:col-span-2">
          <FieldLabel htmlFor="title-extraction-regex">文件名标题提取正则</FieldLabel>
          <Input
            id="title-extraction-regex"
            value={config.title_extraction_regex}
            onChange={(event) =>
              setConfig((current) => ({
                ...current,
                title_extraction_regex: event.target.value,
              }))
            }
            placeholder={'例如：^\\[[^\\]]+\\]\\s*(?P<title>.+?)(?:\\.S\\d+E\\d+.*)?$'}
            spellCheck={false}
          />
          <FieldDescription>
            仅应用于当前源目录。优先读取名为 title 的捕获组，其次读取第一个捕获组；不匹配时沿用原识别结果。
          </FieldDescription>
        </Field>
      </FieldGroup>

      <ScrapingOptions
        config={config}
        onChange={(changes) =>
          setConfig((currentConfig) => ({ ...currentConfig, ...changes }))
        }
      />

      <FieldSet className="rounded-xl border p-4">
        <FieldLegend>自动化流程</FieldLegend>
        <FieldGroup data-slot="checkbox-group">
          <Field orientation="horizontal">
            <FieldLabel htmlFor="auto-approve">
              <FieldContent>
                <FieldTitle className="gap-2">
                  <Bot aria-hidden="true" />
                  自动审批
                </FieldTitle>
                <FieldDescription>
                  TMDB 置信度达到阈值时自动通过；AI 识别结果仍需人工确认。
                </FieldDescription>
              </FieldContent>
            </FieldLabel>
            <Switch
              id="auto-approve"
              checked={config.auto_approve_enabled}
              onCheckedChange={(checked) =>
                setConfig((currentConfig) => ({
                  ...currentConfig,
                  auto_approve_enabled: checked,
                }))
              }
            />
          </Field>
          <Field orientation="horizontal">
            <FieldLabel htmlFor="auto-execute">
              <FieldContent>
                <FieldTitle className="gap-2">
                  <Workflow aria-hidden="true" />
                  审批完成后自动整理
                </FieldTitle>
                <FieldDescription>
                  所有记录审批完成后，自动进入整批复制、刮削和发布流程。
                </FieldDescription>
              </FieldContent>
            </FieldLabel>
            <Switch
              id="auto-execute"
              checked={config.auto_execute_after_approval}
              onCheckedChange={(checked) =>
                setConfig((currentConfig) => ({
                  ...currentConfig,
                  auto_execute_after_approval: checked,
                }))
              }
            />
          </Field>
        </FieldGroup>
      </FieldSet>

      <Alert>
        <ShieldCheck aria-hidden="true" />
        <AlertTitle>安全执行策略</AlertTitle>
        <AlertDescription>
          源目录零写入、目标同名不覆盖、失败暂存内容不自动删除。
        </AlertDescription>
      </Alert>
      {createMutation.isError ? <ErrorNotice message={createMutation.error.message} /> : null}
      <div className="flex justify-end">
        <Button
          type="submit"
          size="lg"
          disabled={!sourceDirectory || !targetDirectory || createMutation.isPending}
        >
          <ScanSearch data-icon="inline-start" aria-hidden="true" />
          {createMutation.isPending
            ? '正在创建并扫描…'
            : config.auto_execute_after_approval
              ? '创建并启动自动流程'
              : '创建并开始预扫描'}
        </Button>
      </div>
    </form>
  )
}
