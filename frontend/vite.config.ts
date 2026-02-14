import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/',  // ✅ Critical: Set base path for deployment
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server:{
     allowedHosts: [
      "furtive-chrissy-reparably.ngrok-free.dev",
      "https://allocate-1.onrender.com"
    ]
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
})