import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import { AppShell } from './components/AppShell'
import { LoadingScreen } from './components/LoadingScreen'
import { DashboardPage } from './pages/DashboardPage'
import { JobsPage } from './pages/JobsPage'
import { LibraryPage } from './pages/LibraryPage'
import { LoginPage } from './pages/LoginPage'
import { ReviewPage } from './pages/ReviewPage'
import { SettingsPage } from './pages/SettingsPage'

export function App() {
  const sessionQuery = useQuery({
    queryKey: ['session'],
    queryFn: api.getSession,
    staleTime: Number.POSITIVE_INFINITY,
  })

  if (sessionQuery.isPending) {
    return <LoadingScreen label="正在初始化媒体管家" />
  }

  if (!sessionQuery.data?.is_authenticated) {
    return <LoginPage />
  }

  return <AppShell>{resolvePage(window.location.pathname)}</AppShell>
}

function resolvePage(pathname: string) {
  const path = pathname.replace(/\/+$/, '') || '/'
  switch (path) {
    case '/jobs':
      return <JobsPage />
    case '/review':
      return <ReviewPage />
    case '/library':
      return <LibraryPage />
    case '/settings':
      return <SettingsPage />
    default:
      return <DashboardPage />
  }
}
