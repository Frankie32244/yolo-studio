import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  define: { 'import.meta.env.VITE_BROWSER_MODE': JSON.stringify(mode === 'pages' ? 'true' : 'false') },
  base: mode === 'pages' ? '/yolo-studio/' : '/',
  build: { outDir: mode === 'pages' ? 'dist-pages' : 'dist' },
  server: { port: 5173, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8000' } }
}))
