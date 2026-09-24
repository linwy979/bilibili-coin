import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../dist',   // 直接輸出到 Flask 的靜態資料夾 bilibili/dist
    emptyOutDir: true
  },
  server: {
    host: true,
    allowedHosts: [
      ".ngrok-free.app"  // 允許所有 ngrok 子網域
    ],
    headers: {
      'X-Frame-Options': 'ALLOWALL',
      'Content-Security-Policy': 'frame-ancestors *'
    }
  }
})
