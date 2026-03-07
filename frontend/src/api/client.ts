import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  withCredentials: true,
})

// Always hits the local backend via the Vite proxy — used for dev-only endpoints
// like /transactions/fetch-amex that read Chrome cookies and can't run on fly.dev.
export const localClient = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

export default client
