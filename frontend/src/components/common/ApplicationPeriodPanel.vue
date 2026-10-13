<template>
  <section class="home-panel home-period-panel" aria-label="推免申请时间">
    <div class="workbench-section-head od-row">
      <h2 class="od-fill">申请时间</h2>
    </div>
    <p v-if="loading" role="status">正在获取申请时间…</p>
    <div v-else-if="error" class="home-error">
      {{ error }}
      <button class="home-link" @click="loadDates">重新加载</button>
    </div>
    <dl v-else class="home-dates">
      <div v-for="(date, index) in dateRows" :key="date.label" class="home-date-row">
        <dt>{{ date.label }}</dt>
        <dd class="home-date-value od-row">
          <span class="od-nowrap">{{ date.text }}</span>
          <button
            v-if="index === dateRows.length - 1"
            :class="['home-link', 'od-fixed', { 'home-link-emphasis': emphasizeAction }]"
            @click="emit('navigate', actionTarget)"
          >
            {{ actionLabel }}
          </button>
        </dd>
      </div>
    </dl>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '@/services/api.js'

const props = defineProps({
  actionLabel: {
    type: String,
    default: '查看推免条例'
  },
  actionTarget: {
    type: String,
    default: 'regulations'
  },
  emphasizeAction: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['navigate'])
const settings = ref({})
const loading = ref(true)
const error = ref('')

const dateLabel = (value) => {
  if (!value) return '尚未公布'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '日期暂不可用' : `${date.getMonth() + 1}月${date.getDate()}日`
}

const dateRows = computed(() =>
  [
    {
      label: '推免申请开放时间',
      value: settings.value.applicationStartTime || settings.value.applicationStart
    },
    {
      label: '推免申请截止时间',
      value: settings.value.applicationEndTime || settings.value.applicationEnd
    }
  ].map((row) => ({ ...row, text: dateLabel(row.value) }))
)

async function loadDates() {
  loading.value = true
  error.value = ''
  try {
    const response = await api.getPublicSystemInfo()
    settings.value = response.data || {}
  } catch {
    error.value = '申请时间暂时无法获取，请重试。'
  } finally {
    loading.value = false
  }
}

onMounted(loadDates)
</script>
