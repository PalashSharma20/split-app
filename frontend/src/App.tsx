import { Center, Loader } from '@mantine/core'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import AppShell from './components/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import AuthFinalizePage from './pages/AuthFinalizePage'

const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ReviewPage = lazy(() => import('./pages/ReviewPage'))
const ActivityPage = lazy(() => import('./pages/ActivityPage'))
const MorePage = lazy(() => import('./pages/MorePage'))

function ProtectedShell({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<Center mih="100dvh"><Loader /></Center>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/finalize" element={<AuthFinalizePage />} />
          <Route path="/overview" element={<ProtectedShell><DashboardPage /></ProtectedShell>} />
          <Route path="/review" element={<ProtectedShell><ReviewPage /></ProtectedShell>} />
          <Route path="/activity" element={<ProtectedShell><ActivityPage /></ProtectedShell>} />
          <Route path="/more" element={<ProtectedShell><MorePage /></ProtectedShell>} />
          <Route path="/dashboard" element={<Navigate to="/overview" replace />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}
