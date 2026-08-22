import { Button, Card, H2 } from '@blueprintjs/core'
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
        <img src="/icons/icon-128x128.png" alt="" width={64} height={64} style={{ marginBottom: 12 }} />
        <H2 style={{ marginTop: 0, marginBottom: 8 }}>Split</H2>
        <p style={{ color: '#738091', marginBottom: 32 }}>
          Track shared expenses and settle up.
        </p>
        <Button
          intent="primary"
          size="large"
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
