import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Local-only endpoints (fetch-amex) — go to the local uvicorn instance.
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // All other API traffic is proxied to the prod backend so the auth
      // cookie is set same-origin (localhost) and avoids cross-site cookie blocks.
      '/auth': { target: 'https://split-app-api.fly.dev', changeOrigin: true },
      '/transactions': { target: 'https://split-app-api.fly.dev', changeOrigin: true },
    },
  },
})
