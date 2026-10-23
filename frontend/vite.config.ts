import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The dev server proxies /api to FastAPI, so the browser sees one origin and the
// HttpOnly session cookie + CSRF double-submit cookie work without any CORS setup.
const backend = process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': { target: backend, changeOrigin: false } } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
