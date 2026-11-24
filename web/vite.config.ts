import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Dev only: forward API calls to FastAPI so the browser sees one origin
    // and CORS never comes up. In production FastAPI serves the built app.
    proxy: { '/api': 'http://localhost:8000' },
  },
})
