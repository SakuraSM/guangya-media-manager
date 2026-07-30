import { useEffect, useState } from 'react'
import { ExternalLink, LoaderCircle, RefreshCw } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '@/api/client'
import { MILLISECONDS_PER_SECOND } from '@/constants'
import type { CloudLoginStart } from '@/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface CloudLoginDialogProps {
  open: boolean
  onClose: () => void
  onConnected: () => void
}

export function CloudLoginDialog({ open, onClose, onConnected }: CloudLoginDialogProps) {
  const [challenge, setChallenge] = useState<CloudLoginStart | null>(null)
  const [status, setStatus] = useState<'STARTING' | 'PENDING' | 'ERROR'>('STARTING')
  const [message, setMessage] = useState('正在创建安全登录会话…')
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!open) return
    let canceled = false
    let timer: number | undefined

    const start = async () => {
      setChallenge(null)
      setStatus('STARTING')
      setMessage('正在创建安全登录会话…')
      try {
        const login = await api.startCloudLogin()
        if (canceled) return
        setChallenge(login)
        setStatus('PENDING')
        setMessage('请使用光鸭 App 扫码确认')

        const poll = async () => {
          try {
            const result = await api.pollCloudLogin(login.login_id)
            if (canceled) return
            if (result.status === 'CONNECTED') {
              onConnected()
              onClose()
              return
            }
            if (result.status === 'EXPIRED') {
              setStatus('ERROR')
              setMessage(result.error_message ?? '二维码已过期，请重新生成')
              return
            }
            timer = window.setTimeout(
              () => void poll(),
              login.poll_interval_seconds * MILLISECONDS_PER_SECOND,
            )
          } catch (error) {
            if (canceled) return
            setStatus('ERROR')
            setMessage(error instanceof Error ? error.message : '登录状态查询失败')
          }
        }
        timer = window.setTimeout(
          () => void poll(),
          login.poll_interval_seconds * MILLISECONDS_PER_SECOND,
        )
      } catch (error) {
        if (canceled) return
        setStatus('ERROR')
        setMessage(error instanceof Error ? error.message : '无法创建登录会话')
      }
    }

    void start()
    return () => {
      canceled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [open, onClose, onConnected, retryCount])

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => (nextOpen ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>连接光鸭云盘</DialogTitle>
          <DialogDescription>
            扫码只用于获取授权，账号凭证会在服务端加密保存。
          </DialogDescription>
        </DialogHeader>
        <div className="mx-auto grid size-56 place-items-center rounded-2xl border bg-white p-4 shadow-xs">
          {challenge ? (
            <QRCodeSVG
              value={challenge.verification_uri}
              size={184}
              bgColor="#ffffff"
              fgColor="#102a2e"
              level="M"
              title="光鸭登录二维码"
            />
          ) : (
            <LoaderCircle className="animate-spin text-primary" aria-hidden="true" />
          )}
        </div>
        <div
          className={
            status === 'ERROR'
              ? 'flex items-center justify-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive'
              : 'flex items-center justify-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm text-accent-foreground'
          }
          aria-live="polite"
        >
          {status === 'PENDING' || status === 'STARTING' ? (
            <LoaderCircle className="animate-spin" aria-hidden="true" />
          ) : null}
          <span>{message}</span>
        </div>
        <DialogFooter className="sm:justify-between">
          {challenge ? (
            <Button variant="outline" asChild>
              <a href={challenge.verification_uri} target="_blank" rel="noreferrer">
                打开授权页面
                <ExternalLink data-icon="inline-end" aria-hidden="true" />
              </a>
            </Button>
          ) : <span />}
          {status === 'ERROR' ? (
            <Button type="button" onClick={() => setRetryCount((count) => count + 1)}>
              <RefreshCw data-icon="inline-start" aria-hidden="true" />
              重新生成
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
