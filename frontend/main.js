import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { library } from '@fortawesome/fontawesome-svg-core'

// 引入整个 solid 图标包
import { fas } from '@fortawesome/free-solid-svg-icons'

// 添加所有 solid 图标到库
library.add(fas)

// 全局样式
import './assets/styles/main.css'

// 引入stores
import { useAuthStore } from './stores/auth'
import { useApplicationsStore } from './stores/applications'

const app = createApp(App)
const pinia = createPinia()

async function bootstrap() {
  if (import.meta.env.MODE === 'demo') {
    const { installDemo } = await import('./demo/mock')
    installDemo()
  }
  app.use(pinia)
  app.component('font-awesome-icon', FontAwesomeIcon)
  const authStore = useAuthStore()
  await authStore.initialize()
  app.use(router)
  await router.isReady()
  app.mount('#app')
}
bootstrap()
