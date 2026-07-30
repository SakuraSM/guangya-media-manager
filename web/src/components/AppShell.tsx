import {
  Clapperboard,
  FolderKanban,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Settings,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { PERCENT_SCALE } from '@/constants'
import { formatBytes } from '@/utils/format'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Progress } from '@/components/ui/progress'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'

const NAVIGATION_ITEMS = [
  { to: '/', label: '总览', icon: LayoutDashboard },
  { to: '/jobs', label: '整理任务', icon: FolderKanban },
  { to: '/library', label: '媒体库', icon: Clapperboard },
  { to: '/review', label: '匹配审核', icon: ListChecks },
  { to: '/settings', label: '设置', icon: Settings },
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

  return (
    <SidebarProvider
      style={
        {
          '--sidebar-width': '15rem',
          '--sidebar-width-icon': '3.75rem',
        } as React.CSSProperties
      }
    >
      <a
        className="fixed top-2 left-2 -translate-y-20 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus:translate-y-0"
        href="#main-content"
      >
        跳到主要内容
      </a>
      <Sidebar collapsible="icon" className="border-sidebar-border">
        <SidebarHeader className="px-3 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <img
              src="/logo.png"
              alt=""
              className="size-9 shrink-0 rounded-xl object-cover shadow-xs"
              aria-hidden="true"
            />
            <span className="min-w-0 group-data-[collapsible=icon]:hidden">
              <strong className="block truncate text-sm font-semibold tracking-tight">
                光鸭媒体管家
              </strong>
              <small className="block text-[0.6rem] font-semibold tracking-[0.14em] text-muted-foreground">
                MEDIA ORGANIZER
              </small>
            </span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu className="gap-1">
                {NAVIGATION_ITEMS.map((item) => {
                  const Icon = item.icon
                  const isActive = currentPath === item.to
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton
                        asChild
                        isActive={isActive}
                        tooltip={item.label}
                        className="h-10 font-medium"
                      >
                        <a href={item.to} aria-current={isActive ? 'page' : undefined}>
                          <Icon aria-hidden="true" />
                          <span>{item.label}</span>
                        </a>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="gap-3 p-3">
          <div className="rounded-xl border border-sidebar-border bg-background/60 p-3 group-data-[collapsible=icon]:hidden">
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="font-medium">光鸭云盘</span>
              <span className="tabular-nums">{account ? `${storagePercentage}%` : '—'}</span>
            </div>
            <Progress value={storagePercentage} aria-label={`云盘已使用 ${storagePercentage}%`} />
            <small className="mt-2 block truncate text-[0.7rem] text-muted-foreground">
              {account
                ? `${formatBytes(account.used_bytes)} / ${formatBytes(account.capacity_bytes)}`
                : '尚未连接账号'}
            </small>
          </div>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip="退出系统"
                onClick={() => logoutMutation.mutate()}
                disabled={logoutMutation.isPending}
              >
                <LogOut aria-hidden="true" />
                <span>{logoutMutation.isPending ? '正在退出' : '退出系统'}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset className="min-w-0 bg-background">
        <header className="sticky top-0 flex h-16 shrink-0 items-center justify-between gap-4 border-b bg-background/95 px-4 backdrop-blur-sm md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <SidebarTrigger className="-ml-1" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden sm:inline-flex">
                  <span>个人 NAS</span>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden sm:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage className="truncate font-medium">
                    {PAGE_TITLES[currentPath] ?? '光鸭媒体管家'}
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <span
              className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex"
              role="status"
            >
              <span
                className={
                  dashboardQuery.isError
                    ? 'size-2 rounded-full bg-destructive'
                    : 'size-2 rounded-full bg-success'
                }
                aria-hidden="true"
              />
              {dashboardQuery.isError
                ? '服务连接异常'
                : account
                  ? '云盘已连接'
                  : '等待连接云盘'}
            </span>
            <ThemeToggle />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="rounded-full outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  aria-label="打开用户菜单"
                >
                  <Avatar className="size-8">
                    <AvatarFallback className="bg-secondary text-xs font-semibold">A</AvatarFallback>
                  </Avatar>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuLabel>管理员</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuItem
                    variant="destructive"
                    disabled={logoutMutation.isPending}
                    onSelect={() => logoutMutation.mutate()}
                  >
                    <LogOut aria-hidden="true" />
                    退出系统
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main
          id="main-content"
          className="min-h-0 flex-1 overflow-auto p-4 md:p-6"
          tabIndex={-1}
        >
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
