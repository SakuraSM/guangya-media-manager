import {
  Bird,
  Clapperboard,
  FolderKanban,
  LayoutDashboard,
  LogOut,
  Settings,
  Sparkles,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { PERCENT_SCALE } from '../constants'
import { formatBytes } from '../utils/format'

const NAVIGATION_ITEMS = [
  { to: '/', label: '总览', icon: LayoutDashboard, end: true },
  { to: '/jobs', label: '整理任务', icon: FolderKanban, end: false },
  { to: '/library', label: '媒体库', icon: Clapperboard, end: false },
  { to: '/review', label: '匹配审核', icon: Sparkles, end: false },
  { to: '/settings', label: '设置', icon: Settings, end: false },
] as const

const PAGE_TITLES: Record<string, string> = {
  '/': '媒体整理总览',
  '/jobs': '整理任务',
  '/review': '匹配审核',
  '/library': '媒体库',
  '/settings': '系统设置',
}

export function AppShell({ children }: { children: ReactNode }) {
  const currentPath = window.location.pathname.replace(/\/+$/, '') || '/'
  const queryClient = useQueryClient()
  const dashboardQuery = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.getDashboard,
    refetchInterval: 30_000,
  })
  const account = dashboardQuery.data?.account
  const storagePercentage =
    account && account.capacity_bytes > 0
      ? Math.round((account.used_bytes / account.capacity_bytes) * PERCENT_SCALE)
      : 0
  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.setQueryData(['session'], { is_authenticated: false })
    },
  })

  const handleLogout = () => {
    logoutMutation.mutate()
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Bird size={24} />
          </span>
          <span className="brand-name">光鸭媒体管家</span>
        </div>
        <nav className="primary-nav" aria-label="主导航">
          {NAVIGATION_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <a
                key={item.to}
                href={item.to}
                className={`nav-item${currentPath === item.to ? ' nav-item-active' : ''}`}
                aria-current={currentPath === item.to ? 'page' : undefined}
              >
                <Icon size={19} aria-hidden="true" />
                <span>{item.label}</span>
              </a>
            )
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="storage-mini">
            <div className="storage-mini-label">
              <span>光鸭云盘</span>
              <span>{account ? `${storagePercentage}%` : '—'}</span>
            </div>
            <div className="progress-track progress-track-small">
              <span style={{ width: `${storagePercentage}%` }} />
            </div>
            <small>
              {account
                ? `${formatBytes(account.used_bytes)} / ${formatBytes(account.capacity_bytes)}`
                : '尚未连接账号'}
            </small>
          </div>
          <button className="nav-item logout-button" type="button" onClick={handleLogout}>
            <LogOut size={19} aria-hidden="true" />
            <span>退出系统</span>
          </button>
        </div>
      </aside>
      <div className="app-content">
        <header className="topbar">
          <div>
            <p className="topbar-context">个人 NAS · 光鸭云盘</p>
            <h1>{PAGE_TITLES[currentPath] ?? '光鸭媒体管家'}</h1>
          </div>
          <div className="topbar-actions">
            <span className="live-indicator">
              <span aria-hidden="true" />
              服务正常
            </span>
            <div className="avatar" aria-label="当前用户：admin">
              A
            </div>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  )
}
