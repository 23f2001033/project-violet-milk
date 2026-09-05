import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Phase 4: with this proxy the frontend calls same-origin "/api/..." paths,
    // so flipping USE_MOCKS to false needs no URL changes anywhere.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Phase 7: FastAPI serves this directory, giving one process on one port.
    outDir: 'dist',
    emptyOutDir: true,
  },
})
