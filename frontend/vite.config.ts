import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  base: '/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    host: true,
  },

preview: {
  host: true,
  allowedHosts: true,   // ✅ correct
}
,

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
})
