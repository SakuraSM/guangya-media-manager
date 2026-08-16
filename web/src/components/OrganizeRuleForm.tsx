import { useState } from 'react'
import type { CloudDirectory, CreateOrganizeRuleInput, RuleScheduleType } from '@/types'
import { DEFAULT_ORGANIZE_CONFIG } from '@/organizeConfig'
import { DirectoryPicker } from '@/components/DirectoryPicker'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

export function OrganizeRuleForm({
  isSaving,
  onCancel,
  onSubmit,
}: {
  isSaving: boolean
  onCancel: () => void
  onSubmit: (input: CreateOrganizeRuleInput) => void
}) {
  const [name, setName] = useState('')
  const [source, setSource] = useState<CloudDirectory | null>(null)
  const [target, setTarget] = useState<CloudDirectory | null>(null)
  const [scheduleType, setScheduleType] = useState<RuleScheduleType>('INTERVAL')
  const [intervalMinutes, setIntervalMinutes] = useState(60)
  const [cronExpression, setCronExpression] = useState('0 3 * * *')
  const [autoExecute, setAutoExecute] = useState(true)
  const [runImmediately, setRunImmediately] = useState(true)
  const [retryLimit, setRetryLimit] = useState(2)
  const [outputLayout, setOutputLayout] = useState<'STANDARD' | 'CLASSIFIED'>('STANDARD')
  const [qualityProfile, setQualityProfile] = useState<'QUALITY' | 'COMPATIBILITY' | 'SPACE_SAVING'>('QUALITY')
  const [versionKeepCount, setVersionKeepCount] = useState(1)
  const [titleExtractionRegex, setTitleExtractionRegex] = useState('')
  const [trashOrganizedSource, setTrashOrganizedSource] = useState(false)
  const [trashIgnoredSource, setTrashIgnoredSource] = useState(false)

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault()
        if (!source || !target) return
        onSubmit({
          name: name.trim() || `${source.name} · 持续整理`,
          enabled: true,
          source_directory_id: source.id,
          source_directory_path: source.path,
          target_directory_id: target.id,
          target_directory_path: target.path,
          config: {
            ...DEFAULT_ORGANIZE_CONFIG,
            auto_execute_after_approval: autoExecute,
            output_layout: outputLayout,
            quality_profile: qualityProfile,
            version_keep_count: versionKeepCount,
            title_extraction_regex: titleExtractionRegex,
            trash_organized_source_files: trashOrganizedSource,
            trash_ignored_source_files: trashIgnoredSource,
          },
          schedule_type: scheduleType,
          interval_minutes: scheduleType === 'INTERVAL' ? intervalMinutes : null,
          cron_expression: scheduleType === 'CRON' ? cronExpression : null,
          timezone: 'Asia/Shanghai',
          retry_limit: retryLimit,
          retry_backoff_minutes: 5,
          run_immediately: runImmediately,
        })
      }}
    >
      <FieldGroup className="grid gap-4 sm:grid-cols-2">
        <Field className="sm:col-span-2">
          <FieldLabel htmlFor="rule-name">规则名称</FieldLabel>
          <Input id="rule-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：电视剧每日增量整理" />
        </Field>
        <DirectoryPicker id="rule-source" label="监控源目录" value={source} onSelect={setSource} />
        <DirectoryPicker id="rule-target" label="输出目录" value={target} onSelect={setTarget} />
        <Field>
          <FieldLabel htmlFor="rule-schedule">运行计划</FieldLabel>
          <Select value={scheduleType} onValueChange={(value) => setScheduleType(value as RuleScheduleType)}>
            <SelectTrigger id="rule-schedule" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="MANUAL">仅手动运行</SelectItem>
              <SelectItem value="INTERVAL">固定间隔</SelectItem>
              <SelectItem value="CRON">Cron 表达式</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field className="sm:col-span-2">
          <FieldLabel htmlFor="rule-title-regex">文件名标题提取正则</FieldLabel>
          <Input
            id="rule-title-regex"
            value={titleExtractionRegex}
            onChange={(event) => setTitleExtractionRegex(event.target.value)}
            placeholder={'例如：^\\[[^\\]]+\\]\\s*(?P<title>.+?)(?:\\.S\\d+E\\d+.*)?$'}
            spellCheck={false}
          />
          <FieldDescription>
            每次扫描先按此规则提取作品名，再对整个作品分组识别。留空则关闭。
          </FieldDescription>
        </Field>
        {scheduleType === 'INTERVAL' ? (
          <Field>
            <FieldLabel htmlFor="rule-interval">间隔分钟</FieldLabel>
            <Input id="rule-interval" type="number" min={5} value={intervalMinutes} onChange={(event) => setIntervalMinutes(Number(event.target.value))} />
          </Field>
        ) : null}
        {scheduleType === 'CRON' ? (
          <Field>
            <FieldLabel htmlFor="rule-cron">Cron</FieldLabel>
            <Input id="rule-cron" value={cronExpression} onChange={(event) => setCronExpression(event.target.value)} />
            <FieldDescription>五段格式，按 Asia/Shanghai 执行。</FieldDescription>
          </Field>
        ) : null}
        <Field>
          <FieldLabel htmlFor="rule-layout">输出布局</FieldLabel>
          <Select value={outputLayout} onValueChange={(value) => setOutputLayout(value as typeof outputLayout)}>
            <SelectTrigger id="rule-layout" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="STANDARD">标准目录</SelectItem><SelectItem value="CLASSIFIED">类型与地区分类</SelectItem></SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="rule-quality">版本偏好</FieldLabel>
          <Select value={qualityProfile} onValueChange={(value) => setQualityProfile(value as typeof qualityProfile)}>
            <SelectTrigger id="rule-quality" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="QUALITY">质量优先</SelectItem><SelectItem value="COMPATIBILITY">兼容优先</SelectItem><SelectItem value="SPACE_SAVING">节省空间</SelectItem></SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="rule-version-keep-count">每组自动保留</FieldLabel>
          <Select value={String(versionKeepCount)} onValueChange={(value) => setVersionKeepCount(Number(value))}>
            <SelectTrigger id="rule-version-keep-count" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="1">最优 1 个版本</SelectItem><SelectItem value="2">最优 2 个版本</SelectItem><SelectItem value="3">最优 3 个版本</SelectItem><SelectItem value="0">全部保留</SelectItem></SelectContent>
          </Select>
          <FieldDescription>按版本偏好自动选择，不阻塞后续自动整理。</FieldDescription>
        </Field>
        <Field orientation="horizontal" className="sm:col-span-2">
          <div className="flex-1">
            <FieldLabel htmlFor="rule-auto-execute">审核完成后自动整理</FieldLabel>
            <FieldDescription>版本会按上述规则自动选择；只有元数据待审核时才暂停。</FieldDescription>
          </div>
          <Switch id="rule-auto-execute" checked={autoExecute} onCheckedChange={setAutoExecute} />
        </Field>
        <Field orientation="horizontal" className="sm:col-span-2">
          <div className="flex-1">
            <FieldLabel htmlFor="rule-trash-organized">整理成功后清理源文件</FieldLabel>
            <FieldDescription>将已发布媒体及关联字幕移入回收站；失败、取消或冲突时不清理。</FieldDescription>
          </div>
          <Switch id="rule-trash-organized" checked={trashOrganizedSource} onCheckedChange={setTrashOrganizedSource} />
        </Field>
        <Field orientation="horizontal" className="sm:col-span-2">
          <div className="flex-1">
            <FieldLabel htmlFor="rule-trash-ignored">清理明确无关文件</FieldLabel>
            <FieldDescription>仅在任务最终完成时，将明确过滤的无关文件移入回收站。</FieldDescription>
          </div>
          <Switch id="rule-trash-ignored" checked={trashIgnoredSource} onCheckedChange={setTrashIgnoredSource} />
        </Field>
        <Field orientation="horizontal" className="sm:col-span-2">
          <div className="flex-1">
            <FieldLabel htmlFor="rule-run-immediately">保存后立即扫描一次</FieldLabel>
            <FieldDescription>首次运行建立目录快照，之后只处理新增或变化内容。</FieldDescription>
          </div>
          <Switch id="rule-run-immediately" checked={runImmediately} onCheckedChange={setRunImmediately} />
        </Field>
        <Field>
          <FieldLabel htmlFor="rule-retry-limit">失败自动重试次数</FieldLabel>
          <Input id="rule-retry-limit" type="number" min={0} max={10} value={retryLimit} onChange={(event) => setRetryLimit(Number(event.target.value))} />
          <FieldDescription>按 5、10、20 分钟指数退避；设为 0 则关闭。</FieldDescription>
        </Field>
      </FieldGroup>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>取消</Button>
        <Button type="submit" disabled={!source || !target || isSaving}>{isSaving ? '保存中…' : '创建规则'}</Button>
      </div>
    </form>
  )
}
