<template>
  <div class="toast-container" ref="toastContainer">
    <TransitionGroup name="toast" tag="div">
      <div
        v-for="toast in visibleToasts"
        :key="toast.id"
        :class="['toast', `toast-${toast.type || 'success'}`]"
        @click="removeToast(toast.id)"
      >
        <div class="toast-icon">
          {{ getToastIcon(toast.type) }}
        </div>
        <div class="toast-content">{{ toast.message }}</div>
        <button class="toast-close" @click.stop="removeToast(toast.id)"> × </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { ref, computed, inject, provide, onMounted, onUnmounted } from 'vue'
import { useToastStore } from '@/stores/toast.js'

// 使用Toast store
const toastStore = useToastStore()
const toastContainer = ref(null)

// 从store获取toasts
const toasts = computed(() => toastStore.toasts)

// 只显示可见的toast
const visibleToasts = computed(() => {
  return toasts.value.filter((toast) => toast.visible)
})

// 获取toast图标
const getToastIcon = (type) => {
  switch (type) {
    case 'success':
      return '✓'
    case 'error':
      return '✕'
    case 'warning':
      return '!'
    case 'info':
      return 'ℹ'
    default:
      return '✓'
  }
}

// 移除指定toast
const removeToast = (id) => {
  toastStore.removeToast(id)
}

// 注入并提供toast方法到全局
const toast = {
  success: (message, duration = 2000) => {
    toastStore.addToast({ type: 'success', message, duration })
  },
  error: (message, duration = 3000) => {
    toastStore.addToast({ type: 'error', message, duration })
  },
  warning: (message, duration = 2500) => {
    toastStore.addToast({ type: 'warning', message, duration })
  },
  info: (message, duration = 2000) => {
    toastStore.addToast({ type: 'info', message, duration })
  }
}

// 提供给全局使用
provide('toast', toast)
</script>

<style scoped src="@/assets/styles/components/common/Toast.css"></style>
