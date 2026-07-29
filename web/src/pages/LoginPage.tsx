import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bird, LockKeyhole, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'
import { ErrorNotice } from '../components/ErrorNotice'

export function LoginPage() {
  const [password, setPassword] = useState('')
  const queryClient = useQueryClient()
  const loginMutation = useMutation({
    mutationFn: api.login,
    onSuccess: (session) => {
      queryClient.setQueryData(['session'], session)
    },
  })

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    loginMutation.mutate(password)
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand">
          <span className="brand-mark brand-mark-large" aria-hidden="true">
            <Bird size={30} />
          </span>
          <div>
            <p>PERSONAL NAS MEDIA OPS</p>
            <h1 id="login-title">光鸭媒体管家</h1>
          </div>
        </div>
        <p className="login-intro">
          安全地扫描、识别和整理你的影视资源。源目录始终保持不变。
        </p>
        <form onSubmit={handleSubmit} className="login-form">
          <label htmlFor="admin-password">管理员密码</label>
          <div className="input-with-icon">
            <LockKeyhole size={17} aria-hidden="true" />
            <input
              id="admin-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="输入管理员密码"
              required
              aria-invalid={loginMutation.isError}
              aria-describedby={loginMutation.isError ? 'login-error' : undefined}
            />
          </div>
          {loginMutation.isError ? (
            <div id="login-error">
              <ErrorNotice message={loginMutation.error.message} />
            </div>
          ) : null}
          <button className="button button-primary button-full" type="submit">
            {loginMutation.isPending ? '正在验证…' : '进入控制台'}
          </button>
        </form>
        <div className="login-security">
          <ShieldCheck size={16} aria-hidden="true" />
          <span>单用户内网模式 · HttpOnly 会话 · Token 加密存储</span>
        </div>
      </section>
    </main>
  )
}
