<template>
  <div id="app">
    <router-view />
    <!-- 全局Toast组件 -->
    <Toast />
    <DemoToolbar v-if="isDemo" />
  </div>
</template>

<script setup>
import { defineAsyncComponent } from 'vue'
const isDemo = import.meta.env.MODE === 'demo'
const DemoToolbar = isDemo ? defineAsyncComponent(() => import('./demo/DemoToolbar.vue')) : null
import { useAuthStore } from './stores/auth'
import { useApplicationsStore } from './stores/applications'
import Toast from './components/common/Toast.vue'

const authStore = useAuthStore()
const applicationsStore = useApplicationsStore()

// 认证状态初始化已在main.js中处理，无需在此处重复调用
</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body {
  height: 100%;
  width: 100%;
  overflow: hidden;
}

#app {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.3s;
}

.page-enter-from,
.page-leave-to {
  opacity: 0;
}
</style>