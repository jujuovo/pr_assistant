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
