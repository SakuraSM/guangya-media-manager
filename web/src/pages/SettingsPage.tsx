import { useCallback, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Cloud, DatabaseZap, KeyRound, Save, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { CloudLoginDialog } from '@/components/CloudLoginDialog'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LoadingScreen } from '@/components/LoadingScreen'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'

interface SettingsFormState {
  tmdb_api_token: string
  ai_base_url: string
  ai_api_key: string
  ai_model: string
}

const EMPTY_FORM: SettingsFormState = {
  tmdb_api_token: '',
  ai_base_url: '',
  ai_api_key: '',
  ai_model: '',
}

export function SettingsPage() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<SettingsFormState | null>(null)
  const [showCloudLogin, setShowCloudLogin] = useState(false)
  const settingsQuery = useQuery({ queryKey: ['settings'], queryFn: api.getSettings })
  const accountQuery = useQuery({ queryKey: ['cloud-account'], queryFn: api.getDashboard })
  const updateMutation = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: async () => {
      setForm((current) =>
        current ? { ...current, tmdb_api_token: '', ai_api_key: '' } : current,
      )
      await queryClient.invalidateQueries({ queryKey: ['settings'] })
      toast.success('设置已安全保存')
    },
  })

  const handleCloudLoginClose = useCallback(() => setShowCloudLogin(false), [])
  const handleCloudConnected = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['cloud-account'] })
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    toast.success('光鸭云盘授权成功')
  }, [queryClient])

  if (settingsQuery.isPending || accountQuery.isPending) {
    return <LoadingScreen label="正在加载设置" />
  }
  if (settingsQuery.isError || accountQuery.isError) {
    return (
      <ErrorNotice
        message={settingsQuery.error?.message ?? accountQuery.error?.message ?? '设置加载失败'}
      />
    )
  }

  const formValues = form ?? {
    ...EMPTY_FORM,
    ai_base_url: settingsQuery.data.ai_base_url,
    ai_model: settingsQuery.data.ai_model,
  }
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...formValues, [event.target.name]: event.target.value })
  }
  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    updateMutation.mutate(buildSettingsPayload(formValues))
  }

  const account = accountQuery.data.account

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      <Card>
        <CardHeader>
          <span className="mb-1 grid size-9 place-items-center rounded-xl bg-accent text-accent-foreground">
            <Cloud aria-hidden="true" />
          </span>
          <CardTitle>光鸭账号</CardTitle>
          <CardDescription>
            首次扫码后保存加密 refresh token，后续自动续期。
          </CardDescription>
          <CardAction>
            <Button variant="outline" type="button" onClick={() => setShowCloudLogin(true)}>
              重新授权
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 rounded-xl border bg-muted/30 p-4">
            <span className="grid size-10 place-items-center rounded-full bg-success/10 text-success">
              <CheckCircle2 aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <strong className="block truncate font-medium">
                {account?.display_name ?? '尚未连接账号'}
              </strong>
              <span className="text-sm text-muted-foreground">
                {account ? '账号已连接' : '需要扫码登录'}
              </span>
            </div>
            <Badge variant="outline">
              {account ? account.status : '未连接'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <span className="mb-1 grid size-9 place-items-center rounded-xl bg-accent text-accent-foreground">
              <DatabaseZap aria-hidden="true" />
            </span>
            <CardTitle>元数据与智能识别</CardTitle>
            <CardDescription>密钥只在后端加密保存，前端不会回显。</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <FieldGroup className="grid gap-5 md:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="tmdb-token">TMDB v3 API Key / v4 读取令牌</FieldLabel>
                <InputGroup>
                  <InputGroupAddon>
                    <KeyRound aria-hidden="true" />
                  </InputGroupAddon>
                  <InputGroupInput
                    id="tmdb-token"
                    name="tmdb_api_token"
                    type="password"
                    autoComplete="off"
                    value={formValues.tmdb_api_token}
                    onChange={handleChange}
                    placeholder={settingsQuery.data.tmdb_configured ? '已配置 · 输入新值可替换' : '输入 Token'}
                  />
                </InputGroup>
              </Field>
              <Field>
                <FieldLabel htmlFor="ai-key">AI API Key</FieldLabel>
                <InputGroup>
                  <InputGroupAddon>
                    <KeyRound aria-hidden="true" />
                  </InputGroupAddon>
                  <InputGroupInput
                    id="ai-key"
                    name="ai_api_key"
                    type="password"
                    autoComplete="off"
                    value={formValues.ai_api_key}
                    onChange={handleChange}
                    placeholder={settingsQuery.data.ai_configured ? '已配置 · 输入新值可替换' : '输入 API Key'}
                  />
                </InputGroup>
              </Field>
              <Field>
                <FieldLabel htmlFor="ai-base-url">兼容 OpenAI API 地址</FieldLabel>
                <Input
                  id="ai-base-url"
                  name="ai_base_url"
                  type="url"
                  value={formValues.ai_base_url}
                  onChange={handleChange}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="ai-model">模型</FieldLabel>
                <Input
                  id="ai-model"
                  name="ai_model"
                  type="text"
                  value={formValues.ai_model}
                  onChange={handleChange}
                />
              </Field>
            </FieldGroup>
            <Alert>
              <ShieldCheck aria-hidden="true" />
              <AlertTitle>隐私说明</AlertTitle>
              <AlertDescription>
                只有低置信度文件名和父目录名会发送给 AI，不上传媒体内容。
              </AlertDescription>
            </Alert>
            {updateMutation.isError ? <ErrorNotice message={updateMutation.error.message} /> : null}
            <div className="flex justify-end">
              <Button type="submit" disabled={updateMutation.isPending}>
                <Save data-icon="inline-start" aria-hidden="true" />
                {updateMutation.isPending ? '正在保存…' : '保存设置'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>

      {settingsQuery.data.demo_mode ? (
        <Alert>
          <ShieldCheck aria-hidden="true" />
          <AlertTitle>演示模式已启用</AlertTitle>
          <AlertDescription>
            当前所有云盘写操作均为模拟执行，关闭 DEMO_MODE 后才会调用真实光鸭接口。
          </AlertDescription>
        </Alert>
      ) : null}
      <CloudLoginDialog
        open={showCloudLogin}
        onClose={handleCloudLoginClose}
        onConnected={handleCloudConnected}
      />
    </div>
  )
}

function buildSettingsPayload(form: SettingsFormState): Record<string, string> {
  const payload: Record<string, string> = {}
  if (form.tmdb_api_token.trim()) payload.tmdb_api_token = form.tmdb_api_token
  if (form.ai_api_key.trim()) payload.ai_api_key = form.ai_api_key
  if (form.ai_base_url.trim()) payload.ai_base_url = form.ai_base_url
  if (form.ai_model.trim()) payload.ai_model = form.ai_model
  return payload
}
