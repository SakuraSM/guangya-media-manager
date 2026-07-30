import { useCallback, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Cloud, DatabaseZap, KeyRound, Save, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'
import { CloudLoginDialog } from '../components/CloudLoginDialog'
import { ErrorNotice } from '../components/ErrorNotice'
import { LoadingScreen } from '../components/LoadingScreen'

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
    },
  })

  const handleCloudLoginClose = useCallback(() => setShowCloudLogin(false), [])
  const handleCloudConnected = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['cloud-account'] })
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
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
  return (
    <div className="settings-layout">
      <section className="settings-section">
        <div className="settings-title">
          <Cloud size={21} aria-hidden="true" />
          <div>
            <h2>光鸭账号</h2>
            <p>首次扫码后保存加密 refresh token，后续自动续期。</p>
          </div>
        </div>
        <div className="connection-row">
          <span className="account-check" aria-hidden="true">
            <CheckCircle2 size={20} />
          </span>
          <div>
            <strong>{accountQuery.data.account?.display_name ?? '尚未连接账号'}</strong>
            <span>{accountQuery.data.account ? '账号已连接' : '需要扫码登录'}</span>
          </div>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => setShowCloudLogin(true)}
          >
            重新授权
          </button>
        </div>
      </section>

      <form className="settings-section" onSubmit={handleSubmit}>
        <div className="settings-title">
          <DatabaseZap size={21} aria-hidden="true" />
          <div>
            <h2>元数据与智能识别</h2>
            <p>密钥只在后端加密保存，前端不会回显。</p>
          </div>
        </div>
        <div className="settings-grid">
          <label className="field" htmlFor="tmdb-token">
            <span>TMDB v3 API Key / v4 读取令牌</span>
            <div className="input-with-icon">
              <KeyRound size={16} aria-hidden="true" />
              <input
                id="tmdb-token"
                name="tmdb_api_token"
                type="password"
                autoComplete="off"
                value={formValues.tmdb_api_token}
                onChange={handleChange}
                placeholder={settingsQuery.data.tmdb_configured ? '已配置 · 输入新值可替换' : '输入 Token'}
              />
            </div>
          </label>
          <label className="field" htmlFor="ai-key">
            <span>AI API Key</span>
            <div className="input-with-icon">
              <KeyRound size={16} aria-hidden="true" />
              <input
                id="ai-key"
                name="ai_api_key"
                type="password"
                autoComplete="off"
                value={formValues.ai_api_key}
                onChange={handleChange}
                placeholder={settingsQuery.data.ai_configured ? '已配置 · 输入新值可替换' : '输入 API Key'}
              />
            </div>
          </label>
          <label className="field" htmlFor="ai-base-url">
            <span>兼容 OpenAI API 地址</span>
            <input
              id="ai-base-url"
              name="ai_base_url"
              type="url"
              value={formValues.ai_base_url}
              onChange={handleChange}
            />
          </label>
          <label className="field" htmlFor="ai-model">
            <span>模型</span>
            <input
              id="ai-model"
              name="ai_model"
              type="text"
              value={formValues.ai_model}
              onChange={handleChange}
            />
          </label>
        </div>
        <div className="safe-operation-note">
          <ShieldCheck size={19} aria-hidden="true" />
          <div>
            <strong>隐私说明</strong>
            <span>只有低置信度文件名和父目录名会发送给 AI，不上传媒体内容。</span>
          </div>
        </div>
        {updateMutation.isError ? <ErrorNotice message={updateMutation.error.message} /> : null}
        <div className="panel-actions">
          <button className="button button-primary" type="submit">
            <Save size={16} aria-hidden="true" />
            {updateMutation.isPending ? '正在保存…' : '保存设置'}
          </button>
        </div>
      </form>

      {settingsQuery.data.demo_mode ? (
        <section className="demo-banner">
          <ShieldCheck size={19} aria-hidden="true" />
          <div>
            <strong>演示模式已启用</strong>
            <span>当前所有云盘写操作均为模拟执行，关闭 DEMO_MODE 后才会调用真实光鸭接口。</span>
          </div>
        </section>
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
