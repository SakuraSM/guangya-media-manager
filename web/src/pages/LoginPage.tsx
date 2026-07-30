import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bird, LoaderCircle, LockKeyhole, ShieldCheck } from 'lucide-react'
import { api } from '@/api/client'
import { ErrorNotice } from '@/components/ErrorNotice'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/components/ui/input-group'

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
    <main className="relative grid min-h-svh place-items-center bg-background p-4">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <Card className="w-full max-w-md">
        <CardHeader className="items-center text-center">
          <span className="mb-2 grid size-12 place-items-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
            <Bird aria-hidden="true" />
          </span>
          <CardTitle className="text-xl">光鸭媒体管家</CardTitle>
          <CardDescription>
            安全地扫描、识别和整理你的影视资源。源目录始终保持不变。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <FieldGroup>
              <Field data-invalid={loginMutation.isError || undefined}>
                <FieldLabel htmlFor="admin-password">管理员密码</FieldLabel>
                <InputGroup>
                  <InputGroupAddon>
                    <LockKeyhole aria-hidden="true" />
                  </InputGroupAddon>
                  <InputGroupInput
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
                </InputGroup>
              </Field>
              {loginMutation.isError ? (
                <div id="login-error">
                  <ErrorNotice message={loginMutation.error.message} />
                </div>
              ) : null}
              <Button type="submit" size="lg" disabled={loginMutation.isPending}>
                {loginMutation.isPending ? (
                  <LoaderCircle data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                ) : null}
                {loginMutation.isPending ? '正在验证…' : '进入控制台'}
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
        <CardFooter className="justify-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck aria-hidden="true" />
          单用户内网模式 · HttpOnly 会话 · Token 加密存储
        </CardFooter>
      </Card>
    </main>
  )
}
