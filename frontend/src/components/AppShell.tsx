import { Button } from '@blueprintjs/core'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <>
      <nav className="app-navbar">
        <span className="app-navbar-brand" onClick={() => navigate('/dashboard')}>
          <img src="/icons/favicon-48x48.png" alt="" width={24} height={24} style={{ verticalAlign: 'middle', marginRight: 8 }} />
          Split
        </span>
        <div className="app-navbar-right">
          {user && <span className="app-navbar-email">{user.email}</span>}
          <Button minimal small icon="log-out" onClick={logout}>
            Sign out
          </Button>
        </div>
      </nav>
      <div className="page-shell">
        {children}
      </div>
    </>
  )
}
