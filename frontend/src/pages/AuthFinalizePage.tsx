import { Spinner } from '@blueprintjs/core'
import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import client from '../api/client'

export default function AuthFinalizePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const called = useRef(false)

  useEffect(() => {
    if (called.current) return
    called.current = true

    const token = params.get('token')
    if (!token) { navigate('/login', { replace: true }); return }

    // Call through the proxy (Vite in dev, Netlify in prod) so the auth_session
    // cookie is set on the frontend's own origin — avoids cross-site cookie blocks.
    client.get(`/auth/finalize?token=${encodeURIComponent(token)}`)
      .then(() => { window.location.replace('/dashboard') })
      .catch(() => navigate('/login', { replace: true }))
  }, [])

  return <div className="page-center"><Spinner /></div>
}
