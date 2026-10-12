import { computed, onMounted, onUnmounted, ref } from 'vue'

/** 随当前时间更新问候语，组件卸载时清理计时器。 */
export function useGreeting() {
  const now = ref(new Date())
  let timer
  onMounted(() => {
    timer = setInterval(() => {
      now.value = new Date()
    }, 60000)
  })
  onUnmounted(() => clearInterval(timer))
  return computed(() => {
    const hour = now.value.getHours()
    return hour < 11 ? '早上好' : hour < 14 ? '中午好' : hour < 18 ? '下午好' : '晚上好'
  })
}
