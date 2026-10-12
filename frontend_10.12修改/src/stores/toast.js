import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  // toast列表状态
  const toasts = ref([])
  // 定时器Map，用于存储每个toast的定时器
  const timers = new Map()

  // 生成唯一ID
  const generateId = () => {
    return Date.now() + Math.random().toString(36).substr(2, 9)
  }

  // 添加toast
  const addToast = (options) => {
    const { type = 'success', message = '', duration = 1500 } = options

    const id = generateId()
    const toast = {
      id,
      type,
      message,
      duration,
      visible: false,
      createdAt: Date.now()
    }

    // 添加到列表
    toasts.value.push(toast)

    // 延迟显示，确保DOM已更新
    setTimeout(() => {
      const toastIndex = toasts.value.findIndex((t) => t.id === id)
      if (toastIndex !== -1) {
        toasts.value[toastIndex].visible = true
      }
    }, 0)

    // 设置自动消失定时器
    if (duration > 0) {
      const timer = setTimeout(() => {
        removeToast(id)
      }, duration)
      timers.set(id, timer)
    }

    return id
  }

  // 移除toast
  const removeToast = (id) => {
    const toastIndex = toasts.value.findIndex((toast) => toast.id === id)

    if (toastIndex !== -1) {
      // 从数组中直接移除，TransitionGroup会自动处理离开动画
      toasts.value.splice(toastIndex, 1)
    }

    // 清除定时器
    const timer = timers.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.delete(id)
    }
  }

  // 清除所有toast
  const clearAllToasts = () => {
    // 清除所有定时器
    timers.forEach((timer) => clearTimeout(timer))
    timers.clear()

    // 清空toast列表
    toasts.value = []
  }

  // 显示成功toast的快捷方法
  const success = (message, duration = 1500) => {
    return addToast({ type: 'success', message, duration })
  }

  // 显示错误toast的快捷方法
  const error = (message, duration = 1500) => {
    return addToast({ type: 'error', message, duration })
  }

  // 显示警告toast的快捷方法
  const warning = (message, duration = 1500) => {
    return addToast({ type: 'warning', message, duration })
  }

  // 显示信息toast的快捷方法
  const info = (message, duration = 1500) => {
    return addToast({ type: 'info', message, duration })
  }

  return {
    toasts,
    addToast,
    removeToast,
    clearAllToasts,
    success,
    error,
    warning,
    info
  }
})
