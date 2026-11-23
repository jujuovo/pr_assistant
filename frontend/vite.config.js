import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const frontendRoot = fileURLToPath(new URL('.', import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  // Use the config file's canonical directory. The repository may be opened
  // through a Windows junction, while Vite resolves source files to the real
  // path; a relative root then rejects /src/main.js as outside the dev root.
  root: frontendRoot,
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // Vite 7.1's dependency optimizer crashes under the supported Node 24
  // runtime before serving the app. Dependencies can still be transformed
  // on demand; disabling discovery only affects development startup speed.
  optimizeDeps: {
    noDiscovery: true,
    include: []
  },
  build: {
    rollupOptions: {
      output: {
        // 把一个 1.8 MB 的单包拆成可并行的缓存块。不做这件事时首次加载要等
        // 一个巨型 JS 下载完才渲染，且任何一行业务代码变更都会让整包缓存失效。
        // `xlsx`（只在统计报表导出用）和整套 FontAwesome 图标是两个大件。
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('xlsx')) return 'vendor-xlsx'
          if (id.includes('@fortawesome')) return 'vendor-icons'
          if (id.includes('@vue/') || id.includes('/vue/') || id.includes('vue-router') || id.includes('pinia')) {
            return 'vendor-vue'
          }
          return 'vendor'
        }
      }
    }
  },
  test: {
    include: ['tests/*.mounted.test.js']
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        secure: false
      },
      '/uploads': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
