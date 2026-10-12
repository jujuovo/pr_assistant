import { createApp } from 'vue'
import App from '@/App.vue'
import router from '@/router/index.js'
import { createPinia } from 'pinia'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { library } from '@fortawesome/fontawesome-svg-core'

// 引入整个 solid 图标包
import { fas } from '@fortawesome/free-solid-svg-icons'

// 添加所有 solid 图标到库
library.add(fas)

// 全局样式
import '@/assets/styles/global/homepage.css'
import '@/assets/styles/global/main.css'
import '@/assets/styles/global/system-theme.css'

// 引入stores
import { useAuthStore } from '@/stores/auth.js'

const app = createApp(App)
const pinia = createPinia()

async function bootstrap() {
  if (import.meta.env.MODE === 'demo') {
    const { installDemo } = await import('@/demo/mock.js')
    installDemo()
  }
  app.use(pinia)
  app.component('font-awesome-icon', FontAwesomeIcon)
  const authStore = useAuthStore()
  await authStore.initialize()
  if (import.meta.env.MODE === 'demo') {
    const requested = location.hash.match(/^#\/(student|teacher|admin)/)?.[1]
    const isLoginRoute = location.hash.startsWith('#/login')
    if (!isLoginRoute) {
      const role = requested || 'student'
      await authStore.login(`${role}001`, 'demo123', '1234', 'demo')
    }
  }
  app.use(router)
  await router.isReady()
  app.mount('#app')
}
bootstrap()
