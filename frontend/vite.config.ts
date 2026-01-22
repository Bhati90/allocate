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
  server: {
    port: 5174,       // ✅ Run on port 5174
    strictPort: true, // ✅ Fail if port is already in use
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
})
