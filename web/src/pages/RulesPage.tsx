import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Play, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { OrganizeRuleForm } from '@/components/OrganizeRuleForm'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LoadingScreen } from '@/components/LoadingScreen'
import type { CreateOrganizeRuleInput, OrganizeRule } from '@/types'
import { formatDateTime } from '@/utils/format'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export function RulesPage() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<OrganizeRule | null>(null)
  const rulesQuery = useQuery({ queryKey: ['organize-rules'], queryFn: api.getOrganizeRules, refetchInterval: 15_000 })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['organize-rules'] })
  const createMutation = useMutation({ mutationFn: api.createOrganizeRule, onSuccess: async () => { setCreating(false); await refresh(); toast.success('持续整理规则已创建') } })
  const runMutation = useMutation({ mutationFn: api.runOrganizeRule, onSuccess: async (result) => { await refresh(); await queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast.success(result.coalesced ? '目录已有任务运行，本次触发已合并' : '增量扫描已启动') } })
  const updateMutation = useMutation({ mutationFn: ({ rule, input }: { rule: OrganizeRule; input: CreateOrganizeRuleInput }) => api.updateOrganizeRule(rule.id, input), onSuccess: refresh })
  const deleteMutation = useMutation({ mutationFn: api.deleteOrganizeRule, onSuccess: async () => { setDeleting(null); await refresh(); toast.success('规则已删除，历史任务保留') } })

  if (rulesQuery.isPending) return <LoadingScreen label="正在加载整理规则" />
  if (rulesQuery.isError) return <ErrorNotice message={rulesQuery.error.message} />
  const rules = rulesQuery.data

  return (
    <div className="flex h-[calc(100svh-7rem)] min-h-[36rem] flex-col gap-4">
      <section className="flex items-center justify-between gap-4">
        <div><h2 className="text-xl font-semibold tracking-tight">持续整理</h2><p className="mt-1 text-sm text-muted-foreground">定时检查目录，仅为新增或变化内容创建整理任务。</p></div>
        <Button onClick={() => setCreating(true)}><Plus aria-hidden="true" />新建规则</Button>
      </section>
      <Card className="min-h-0 flex-1 gap-0 overflow-hidden py-0">
        <CardHeader className="border-b"><CardTitle>整理规则</CardTitle><CardDescription>{rules.length} 条规则</CardDescription></CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-auto p-0">
          {rules.length ? (
            <Table className="min-w-[960px]"><TableHeader className="sticky top-0 bg-card"><TableRow><TableHead>规则</TableHead><TableHead>源目录 → 目标目录</TableHead><TableHead>计划</TableHead><TableHead>最近运行</TableHead><TableHead>启用</TableHead><TableHead className="text-right">操作</TableHead></TableRow></TableHeader>
              <TableBody>{rules.map((rule) => <TableRow key={rule.id}>
                <TableCell><strong className="block">{rule.name}</strong><Badge className="mt-2" variant="outline">{rule.config.output_layout === 'CLASSIFIED' ? '分类布局' : '标准布局'}</Badge></TableCell>
                <TableCell><code className="block max-w-80 truncate text-xs">{rule.source_directory_path}</code><code className="mt-1 block max-w-80 truncate text-xs text-muted-foreground">→ {rule.target_directory_path}</code></TableCell>
                <TableCell className="text-xs">{scheduleLabel(rule)}<span className="mt-1 block text-muted-foreground">下次：{rule.next_run_at ? formatDateTime(rule.next_run_at) : '手动触发'}</span></TableCell>
                <TableCell className="text-xs">{rule.last_run_at ? formatDateTime(rule.last_run_at) : '尚未运行'}{rule.last_error ? <span className="mt-1 block text-destructive">{rule.last_error}</span> : null}{rule.retry_count > 0 ? <Badge className="mt-2" variant="destructive">重试 {rule.retry_count}/{rule.retry_limit}</Badge> : null}</TableCell>
                <TableCell><Switch checked={rule.enabled} aria-label={`${rule.name}启用状态`} onCheckedChange={(enabled) => updateMutation.mutate({ rule, input: ruleInput(rule, enabled) })} /></TableCell>
                <TableCell><div className="flex justify-end gap-2"><Button size="sm" variant="outline" disabled={runMutation.isPending} onClick={() => runMutation.mutate(rule.id)}><Play aria-hidden="true" />运行</Button><Button size="icon-sm" variant="ghost" aria-label="删除规则" onClick={() => setDeleting(rule)}><Trash2 aria-hidden="true" /></Button></div></TableCell>
              </TableRow>)}</TableBody>
            </Table>
          ) : <Empty className="h-full"><EmptyHeader><EmptyMedia variant="icon"><CalendarClock /></EmptyMedia><EmptyTitle>还没有持续整理规则</EmptyTitle><EmptyDescription>创建规则后，系统会按计划增量检查云盘目录。</EmptyDescription></EmptyHeader></Empty>}
        </CardContent>
      </Card>
      <Dialog open={creating} onOpenChange={setCreating}><DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-3xl"><DialogHeader><DialogTitle>新建持续整理规则</DialogTitle><DialogDescription>保存目录和整理策略，后续运行仍生成可审核的普通任务。</DialogDescription></DialogHeader><OrganizeRuleForm isSaving={createMutation.isPending} onCancel={() => setCreating(false)} onSubmit={(input) => createMutation.mutate(input)} /></DialogContent></Dialog>
      <AlertDialog open={deleting !== null} onOpenChange={(open) => { if (!open) setDeleting(null) }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>删除这条整理规则？</AlertDialogTitle><AlertDialogDescription>规则和增量快照会删除，既有任务、媒体库和云盘文件不会被删除。</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>取消</AlertDialogCancel><AlertDialogAction variant="destructive" onClick={() => deleting && deleteMutation.mutate(deleting.id)}>删除规则</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  )
}

function scheduleLabel(rule: OrganizeRule) { if (rule.schedule_type === 'MANUAL') return '手动'; if (rule.schedule_type === 'INTERVAL') return `每 ${rule.interval_minutes} 分钟`; return rule.cron_expression ?? 'Cron' }
function ruleInput(rule: OrganizeRule, enabled: boolean): CreateOrganizeRuleInput { return { name: rule.name, enabled, source_directory_id: rule.source_directory_id, source_directory_path: rule.source_directory_path, target_directory_id: rule.target_directory_id, target_directory_path: rule.target_directory_path, config: rule.config, schedule_type: rule.schedule_type, interval_minutes: rule.interval_minutes, cron_expression: rule.cron_expression, timezone: rule.timezone, retry_limit: rule.retry_limit, retry_backoff_minutes: rule.retry_backoff_minutes } }
