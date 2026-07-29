import { useEffect, useRef, useState } from 'react'
import { ExternalLink, LoaderCircle, RefreshCw, X } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../api/client'
import { MILLISECONDS_PER_SECOND } from '../constants'
import type { CloudLoginStart } from '../types'

interface CloudLoginDialogProps {
  open: boolean
  onClose: () => void
  onConnected: () => void
}

export function CloudLoginDialog({
  open,
  onClose,
  onConnected,
}: CloudLoginDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [challenge, setChallenge] = useState<CloudLoginStart | null>(null)
  const [status, setStatus] = useState<'STARTING' | 'PENDING' | 'ERROR'>('STARTING')
  const [message, setMessage] = useState('正在创建安全登录会话…')
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

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
              poll,
              login.poll_interval_seconds * MILLISECONDS_PER_SECOND,
            )
          } catch (error) {
            if (canceled) return
            setStatus('ERROR')
            setMessage(error instanceof Error ? error.message : '登录状态查询失败')
          }
        }
        timer = window.setTimeout(
          poll,
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
    <dialog
      ref={dialogRef}
      className="cloud-login-dialog"
      aria-labelledby="cloud-login-title"
      onCancel={onClose}
      onClose={onClose}
    >
      <button className="dialog-close" type="button" onClick={onClose} aria-label="关闭">
        <X size={18} aria-hidden="true" />
      </button>
      <div className="dialog-heading">
        <span className="eyebrow">安全授权</span>
        <h2 id="cloud-login-title">连接光鸭云盘</h2>
        <p>扫码只用于获取授权，账号凭证会在服务端加密保存。</p>
      </div>

      <div className="qr-shell" aria-live="polite">
        {challenge ? (
          <QRCodeSVG
            value={challenge.verification_uri}
            size={184}
            bgColor="#ffffff"
            fgColor="#0b1422"
            level="M"
            title="光鸭登录二维码"
          />
        ) : (
          <LoaderCircle className="spin" size={32} aria-hidden="true" />
        )}
      </div>
      <div className={`login-poll-status login-poll-${status.toLowerCase()}`}>
        {status === 'PENDING' || status === 'STARTING' ? (
          <LoaderCircle className="spin" size={16} aria-hidden="true" />
        ) : null}
        <span>{message}</span>
      </div>

      {challenge ? (
        <a
          className="button button-secondary"
          href={challenge.verification_uri}
          target="_blank"
          rel="noreferrer"
        >
          无法扫码？打开授权页面
          <ExternalLink size={15} aria-hidden="true" />
        </a>
      ) : null}
      {status === 'ERROR' ? (
        <button
          className="button button-primary"
          type="button"
          onClick={() => setRetryCount((count) => count + 1)}
        >
          <RefreshCw size={15} aria-hidden="true" />
          重新生成
        </button>
      ) : null}
    </dialog>
  )
}
