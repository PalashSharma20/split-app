import { Spinner } from '@blueprintjs/core'
import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import axios from 'axios'

// Finalize must always call fly.dev directly so the cookie is set on the
// fly.dev domain — even in dev where VITE_API_BASE_URL might point elsewhere.
const finalizeBase = import.meta.env.VITE_API_DIRECT_URL ?? import.meta.env.VITE_API_BASE_URL ?? ''

export default function AuthFinalizePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const called = useRef(false)

  useEffect(() => {
    if (called.current) return
    called.current = true

    const token = params.get('token')
    if (!token) { navigate('/login', { replace: true }); return }

    axios.get(`${finalizeBase}/auth/finalize?token=${encodeURIComponent(token)}`, { withCredentials: true })
      .then(() => { window.location.replace('/dashboard') })
      .catch(() => navigate('/login', { replace: true }))
  }, [])

  return <div className="page-center"><Spinner /></div>
}
