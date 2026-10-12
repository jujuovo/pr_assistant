import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 独立主页构建输出留在项目内，避免覆盖上级目录文件。
export default defineConfig({
  plugins: [vue()],
  base: './',
  root: fileURLToPath(new URL('.', import.meta.url)),
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  build: { outDir: 'dist-homepage', assetsDir: 'homepage-assets' }
})
