/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// The backend runs on :8000 in development; /api is proxied so the browser only talks to one origin.
const backend = process.env.TENDERFLOW_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: backend, changeOrigin: false } },
    // Serve this folder plus ../branding.json (shared with the backend) and nothing else from the
    // repository: backend/data holds uploaded tenders and quotations.
    fs: { allow: [__dirname, path.resolve(__dirname, '../branding.json')] },
  },
  preview: {
    port: 4173,
    proxy: { '/api': { target: backend, changeOrigin: false } },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
  },
})
