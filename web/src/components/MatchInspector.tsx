import { useState } from 'react'
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleSlash,
  FileCog,
  FolderOutput,
  MoreHorizontal,
  RefreshCcw,
  RotateCcw,
  Undo2,
} from 'lucide-react'
import { Poster } from '@/components/Poster'
import { RecognitionNotice } from '@/components/RecognitionNotice'
import { ManualTmdbMatchForm } from '@/components/ManualTmdbMatchForm'
import { LocalMetadataGroupForm } from '@/components/LocalMetadataGroupForm'
import { OriginalFileInfo } from '@/components/OriginalFileInfo'
import {
  MATCH_DECISION,
  type LocalMetadataGroupInput,
  type ManualMatchInput,
  type MatchCandidate,
  type MediaMatch,
} from '@/types'
import { formatConfidence } from '@/utils/format'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { Field, FieldLabel } from '@/components/ui/field'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { cn } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

interface MatchInspectorProps {
  jobId: string
  mediaMatch: MediaMatch | null
  selectedCandidateId: number | null
  versionMatches: MediaMatch[]
  isSaving: boolean
  isRetrying: boolean
  isRetryingGroup: boolean
  onSelectCandidate: (candidateId: number) => void
  onApproveCandidate: (candidateId: number) => void
  onToggleIgnore: () => void
  onRetry: () => void
  onRetryGroup: () => void
  onManualMatch: (match: ManualMatchInput) => void
  onManualGroupMatch: (match: ManualMatchInput) => void
  onLocalGroupMatch?: (metadata: LocalMetadataGroupInput) => void
  onConfirmVersionGroup: (selectedMatchIds: string[]) => void
  onUpdateClassification: (
    category: MediaMatch['library_category'],
    region: MediaMatch['region_bucket'],
  ) => void
  position: number
  total: number
  canSelectPrevious: boolean
  canSelectNext: boolean
  onSelectPrevious: () => void
  onSelectNext: () => void
}

export function MatchInspector({
  jobId,
  mediaMatch,
  selectedCandidateId,
  versionMatches,
  isSaving,
  isRetrying,
  isRetryingGroup,
  onSelectCandidate,
  onApproveCandidate,
  onToggleIgnore,
  onRetry,
  onRetryGroup,
  onManualMatch,
  onManualGroupMatch,
  onLocalGroupMatch,
  onConfirmVersionGroup,
  onUpdateClassification,
  position,
  total,
  canSelectPrevious,
  canSelectNext,
  onSelectPrevious,
  onSelectNext,
}: MatchInspectorProps) {
  const [isOrganizeDetailsOpen, setIsOrganizeDetailsOpen] = useState(false)
  if (!mediaMatch) {
    return (
      <aside className="grid h-full place-items-center bg-card">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <FolderOutput aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>选择一个待审核文件</EmptyTitle>
            <EmptyDescription>候选元数据和目标路径会显示在这里。</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </aside>
    )
  }

  const selectedCandidate =
    mediaMatch.candidates.find((candidate) => candidate.tmdb_id === selectedCandidateId) ??
    mediaMatch.candidates[0] ??
    null

  return (
    <aside
      className="flex h-full min-h-0 flex-col overflow-hidden bg-card"
      aria-labelledby="inspector-title"
    >
      <div className="shrink-0 border-b px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            当前项 {position} / {total}
          </span>
          <div className="flex items-center gap-1" aria-label="切换审核项">
            <Button
              variant="ghost"
              size="icon-sm"
              type="button"
              aria-label="上一条审核项"
              disabled={!canSelectPrevious}
              onClick={onSelectPrevious}
            >
              <ChevronLeft aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              type="button"
              aria-label="下一条审核项"
              disabled={!canSelectNext}
              onClick={onSelectNext}
            >
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </div>
        <h2 id="inspector-title" className="mt-1 truncate text-sm font-medium" title={mediaMatch.filename}>
          {mediaMatch.filename}
        </h2>
        <p className="mt-1 truncate font-mono text-[0.65rem] text-muted-foreground" title={mediaMatch.source_path}>
          {mediaMatch.source_path}
        </p>
      </div>
      <ScrollArea key={mediaMatch.id} className="min-h-0 flex-1">
        <div className="flex flex-col gap-4 p-4">
          <RecognitionNotice mediaMatch={mediaMatch} />
          {mediaMatch.execution_error ? (
            <Alert variant="destructive">
              <CircleAlert aria-hidden="true" />
              <AlertTitle>执行失败</AlertTitle>
              <AlertDescription>{mediaMatch.execution_error}</AlertDescription>
            </Alert>
          ) : null}
          {mediaMatch.cleanup_error ? (
            <Alert variant="destructive">
              <CircleAlert aria-hidden="true" />
              <AlertTitle>源文件清理失败</AlertTitle>
              <AlertDescription>{mediaMatch.cleanup_error}</AlertDescription>
            </Alert>
          ) : null}

          <Field>
            <div className="flex items-center justify-between gap-2">
              <FieldLabel>选择匹配结果</FieldLabel>
              <Badge variant="secondary">{mediaMatch.candidates.length} 个候选</Badge>
            </div>
            {mediaMatch.candidates.length ? (
              <div className="flex flex-col gap-2">
                {mediaMatch.candidates.map((candidate) => (
                  <CandidateOption
                    candidate={candidate}
                    isSelected={candidate.tmdb_id === selectedCandidate?.tmdb_id}
                    key={candidate.tmdb_id}
                    disabled={isSaving}
                    onApprove={() => {
                      onSelectCandidate(candidate.tmdb_id)
                      onApproveCandidate(candidate.tmdb_id)
                    }}
                  />
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed p-3 text-xs leading-relaxed text-muted-foreground">
                自动识别没有返回候选。请直接搜索 TMDB，或重新识别整个作品分组。
              </p>
            )}
          </Field>

          {selectedCandidate ? (
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-medium">元数据预览</h3>
              <dl className="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-2 text-xs">
                <dt className="text-muted-foreground">类型</dt>
                <dd>{selectedCandidate.media_type === 'TV' ? '剧集' : '电影'}</dd>
                <dt className="text-muted-foreground">标题</dt>
                <dd>{selectedCandidate.title}</dd>
                <dt className="text-muted-foreground">原名</dt>
                <dd>{selectedCandidate.original_title || '—'}</dd>
                <dt className="text-muted-foreground">年份</dt>
                <dd>{selectedCandidate.year ?? '—'}</dd>
              </dl>
              <h3 className="text-sm font-medium">目标路径预览</h3>
              <code className="break-all rounded-lg border bg-muted/40 p-3 text-[0.68rem] leading-relaxed">
                {mediaMatch.target_path || '选择候选后生成目标路径'}
              </code>
            </div>
          ) : null}

          <ManualTmdbMatchForm
            key={mediaMatch.id}
            jobId={jobId}
            mediaMatch={mediaMatch}
            isSaving={isSaving}
            onSubmitCurrent={onManualMatch}
            onSubmitGroup={onManualGroupMatch}
          />
          {mediaMatch.candidates.length === 0 &&
          mediaMatch.media_type === 'TV' &&
          onLocalGroupMatch ? (
            <LocalMetadataGroupForm
              key={`local-${mediaMatch.id}`}
              mediaMatch={mediaMatch}
              isSaving={isSaving}
              onSubmit={onLocalGroupMatch}
            />
          ) : null}

          <Collapsible
            open={isOrganizeDetailsOpen}
            onOpenChange={setIsOrganizeDetailsOpen}
            className="rounded-lg border"
          >
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                type="button"
                className="h-auto w-full justify-between rounded-lg px-3 py-3"
              >
                <span className="flex items-center gap-2">
                  <FileCog aria-hidden="true" />
                  源文件与整理设置
                </span>
                <ChevronDown
                  className={cn('transition-transform', isOrganizeDetailsOpen && 'rotate-180')}
                  aria-hidden="true"
                />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="flex flex-col gap-4 border-t p-3">
                <section className="space-y-2" aria-labelledby="original-file-title">
                  <h3 id="original-file-title" className="text-sm font-medium">原始文件</h3>
                  <div className="rounded-lg bg-muted/30 p-3">
                    <OriginalFileInfo
                      filename={mediaMatch.filename}
                      sourcePath={mediaMatch.source_path}
                      variant="detail"
                    />
                  </div>
                </section>
                <ClassificationPanel
                  key={`classification-${mediaMatch.group_key}-${mediaMatch.library_category}-${mediaMatch.region_bucket}`}
                  mediaMatch={mediaMatch}
                  isSaving={isSaving}
                  onSave={onUpdateClassification}
                />
                {versionMatches.length > 1 ? (
                  <VersionDecisionPanel
                    key={`versions-${mediaMatch.version_group_key}-${versionMatches.map((item) => item.version_recommendation).join('-')}`}
                    matches={versionMatches}
                    isSaving={isSaving}
                    onConfirm={onConfirmVersionGroup}
                  />
                ) : (
                  <QualitySummary mediaMatch={mediaMatch} />
                )}
                <div className="flex flex-wrap items-center gap-2" aria-label="元数据识别来源">
                  <Badge variant="outline">来源：{matchOriginLabel(mediaMatch.match_origin)}</Badge>
                  {mediaMatch.metadata_provider ? (
                    <Badge variant="secondary">
                      {mediaMatch.metadata_provider}
                      {mediaMatch.provider_id ? ` · ${mediaMatch.provider_id}` : ''}
                    </Badge>
                  ) : null}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      </ScrollArea>
      <div className="grid shrink-0 grid-cols-[minmax(0,1fr)_auto] gap-2 border-t bg-card p-3">
        <Button
          variant="outline"
          type="button"
          className="hidden sm:inline-flex"
          disabled={isSaving || isRetryingGroup}
          onClick={onRetryGroup}
        >
          <RefreshCcw data-icon="inline-start" aria-hidden="true" />
          {isRetryingGroup ? '正在识别整组' : '重新识别整组'}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon" type="button" aria-label="更多审核操作">
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              className="sm:hidden"
              disabled={isSaving || isRetryingGroup}
              onSelect={onRetryGroup}
            >
              <RefreshCcw aria-hidden="true" />
              {isRetryingGroup ? '正在识别整组' : '重新识别整组'}
            </DropdownMenuItem>
            <DropdownMenuSeparator className="sm:hidden" />
            <DropdownMenuItem
              disabled={isSaving || isRetrying}
              onSelect={onRetry}
            >
              <RotateCcw aria-hidden="true" />
              {isRetrying ? '正在重新识别此文件' : '仅重新识别此文件'}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              disabled={isSaving}
              onSelect={onToggleIgnore}
            >
              {mediaMatch.decision === MATCH_DECISION.IGNORED ? (
                <Undo2 aria-hidden="true" />
              ) : (
                <CircleSlash aria-hidden="true" />
              )}
              {mediaMatch.decision === MATCH_DECISION.IGNORED ? '恢复审核' : '忽略此文件'}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  )
}

function ClassificationPanel({
  mediaMatch,
  isSaving,
  onSave,
}: {
  mediaMatch: MediaMatch
  isSaving: boolean
  onSave: MatchInspectorProps['onUpdateClassification']
}) {
  const [category, setCategory] = useState(mediaMatch.library_category)
  const [region, setRegion] = useState(mediaMatch.region_bucket)
  return (
    <section className="rounded-lg border p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">作品分类</h3>
        <Button size="sm" variant="outline" disabled={isSaving || (category === mediaMatch.library_category && region === mediaMatch.region_bucket)} onClick={() => onSave(category, region)}>保存整组分类</Button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Select value={category} onValueChange={(value) => setCategory(value as typeof category)}><SelectTrigger aria-label="作品分类" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="MOVIE">电影</SelectItem><SelectItem value="TV">电视剧</SelectItem><SelectItem value="ANIME">动漫</SelectItem><SelectItem value="DOCUMENTARY">纪录片</SelectItem><SelectItem value="VARIETY">综艺</SelectItem></SelectContent></Select>
        <Select value={region} onValueChange={(value) => setRegion(value as typeof region)}><SelectTrigger aria-label="作品地区" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="CN">中国大陆</SelectItem><SelectItem value="HK_TW">港澳台</SelectItem><SelectItem value="JP_KR">日韩</SelectItem><SelectItem value="EUROPE_US">欧美</SelectItem><SelectItem value="OTHER">其他</SelectItem></SelectContent></Select>
      </div>
      <p className="mt-2 text-[0.68rem] text-muted-foreground">
        {mediaMatch.classification_reasons
          .map((reason) => reason.message)
          .filter((message): message is string => typeof message === 'string')
          .join('；') || '未获得明确分类依据，可人工修正。'}
      </p>
    </section>
  )
}

function VersionDecisionPanel({
  matches,
  isSaving,
  onConfirm,
}: {
  matches: MediaMatch[]
  isSaving: boolean
  onConfirm: (selectedMatchIds: string[]) => void
}) {
  const initial = matches.filter((item) => item.version_recommendation === 'CONFIRMED').map((item) => item.id)
  const recommended = matches.find((item) => item.quality_profile.recommended)
  const hasPendingSelection = matches.some((item) => item.version_recommendation === 'PENDING')
  const automaticSelection = matches.some((item) => item.quality_profile.selection_mode === 'AUTO')
  const [selected, setSelected] = useState<Set<string>>(
    new Set(initial.length ? initial : recommended ? [recommended.id] : [matches[0]!.id]),
  )
  return (
    <section className="rounded-lg border border-primary/25 bg-primary/5 p-3">
      <h3 className="text-sm font-medium">多版本{automaticSelection ? '自动选择' : '选择'}</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        {hasPendingSelection
          ? '旧任务仍需确认一次，确认后即可执行。'
          : '系统已按任务规则自动选择；如有需要，可在执行前手动调整。'}
      </p>
      <div className="mt-3 space-y-2">
        {[...matches].sort((a, b) => b.version_score - a.version_score).map((item) => (
          <label key={item.id} className="flex cursor-pointer items-start gap-2 rounded-md border bg-card p-2 text-xs">
            <Checkbox checked={selected.has(item.id)} onCheckedChange={(checked) => setSelected((current) => { const next = new Set(current); if (checked) next.add(item.id); else next.delete(item.id); return next })} />
            <span className="min-w-0 flex-1"><strong className="block truncate">{item.filename}</strong><small className="text-muted-foreground">{qualityLabel(item)} · 得分 {item.version_score}</small></span>
            {item.quality_profile.selected ? <Badge>已选</Badge> : item.quality_profile.recommended ? <Badge variant="secondary">最优</Badge> : null}
          </label>
        ))}
      </div>
      <Button className="mt-3 w-full" size="sm" disabled={selected.size === 0 || isSaving} onClick={() => onConfirm([...selected])}>{hasPendingSelection ? '确认' : '保存调整'}：保留 {selected.size} 个版本</Button>
    </section>
  )
}

function QualitySummary({ mediaMatch }: { mediaMatch: MediaMatch }) {
  return <section className="rounded-lg border p-3"><h3 className="text-sm font-medium">质量信息</h3><p className="mt-2 text-xs text-muted-foreground">{qualityLabel(mediaMatch)} · 得分 {mediaMatch.version_score}</p><p className="mt-1 text-[0.68rem] text-muted-foreground">{mediaMatch.quality_profile.score_reason}</p></section>
}

function qualityLabel(mediaMatch: MediaMatch) {
  const quality = mediaMatch.quality_profile
  return [quality.resolution, quality.source, quality.hdr, quality.codec, quality.audio].filter((value) => value && value !== 'UNKNOWN').join(' · ') || '未从名称识别到质量标签'
}

function matchOriginLabel(origin: MediaMatch['match_origin']): string {
  return {
    PATH_ID: '路径 ID',
    NFO: '本地 NFO',
    TMDB: 'TMDB 搜索',
    AI: 'AI 辅助',
    LOCAL: '本地信息',
    MANUAL: '手动确认',
    RULE: '文件名规则',
  }[origin ?? 'RULE']
}

function CandidateOption({
  candidate,
  isSelected,
  disabled,
  onApprove,
}: {
  candidate: MatchCandidate
  isSelected: boolean
  disabled: boolean
  onApprove: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onApprove}
      className={cn(
        'grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 rounded-lg border p-2 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50',
        isSelected && 'border-primary/40 bg-primary/5',
      )}
      aria-label={`选择并批准 ${candidate.title}`}
    >
      <Poster src={candidate.poster_url} title={candidate.title} size="medium" />
      <span className="min-w-0">
        <strong className="block truncate text-xs font-medium">{candidate.title}</strong>
        <small className="block truncate text-[0.68rem] text-muted-foreground">
          {candidate.original_title} · {candidate.year ?? '年份未知'}
        </small>
      </span>
      <span className="flex flex-col items-end gap-1">
        <strong className="text-xs tabular-nums text-warning">
          {formatConfidence(candidate.score)}
        </strong>
        <small className="text-[0.65rem] text-primary">选择即批准</small>
      </span>
    </button>
  )
}
