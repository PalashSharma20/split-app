import { Button, Card, H2, Icon } from '@blueprintjs/core'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && user) navigate('/dashboard', { replace: true })
  }, [user, loading, navigate])

  return (
    <div className="page-center">
      <Card style={{ width: 360, textAlign: 'center', padding: '40px 32px' }}>
        <Icon icon="credit-card" size={40} color="#1c6faf" style={{ marginBottom: 16 }} />
        <H2 style={{ marginTop: 0, marginBottom: 8 }}>Split App</H2>
        <p style={{ color: '#738091', marginBottom: 32 }}>
          AMEX&nbsp;→ Splitwise, automatically.
        </p>
        <Button
          intent="primary"
          large
          fill
          icon="log-in"
          onClick={() => {
            const base = import.meta.env.VITE_API_DIRECT_URL ?? import.meta.env.VITE_API_BASE_URL ?? ''
            const next = import.meta.env.DEV ? `?next=${encodeURIComponent(window.location.origin)}` : ''
            window.location.href = `${base}/auth/login${next}`
          }}
        >
          Sign in with Google
        </Button>
      </Card>
    </div>
  )
}
