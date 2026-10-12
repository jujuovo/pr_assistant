<template>
  <section class="home-page student-home-reference">
    <header class="workbench-welcome"
      ><h1>{{ greeting }}，演示同学</h1><p>STUDENT DASHBOARD</p></header
    >
    <section class="workbench-action od-row" aria-label="待办材料">
      <p v-if="store.loading" role="status">正在获取材料进度…</p>
      <div v-else-if="store.error" class="home-error"
        >{{ store.error }}
        <button class="home-link" @click="store.fetchApplications()">重新加载</button></div
      >
      <template v-else
        ><svg class="workbench-alert od-fixed" viewBox="0 0 64 64" fill="none" aria-hidden="true">
          <circle cx="32" cy="32" r="28" stroke="currentColor" stroke-width="3" />
          <path d="M32 18v18" stroke="currentColor" stroke-width="6" stroke-linecap="round" />
          <circle cx="32" cy="46" r="3" fill="currentColor" /></svg
        ><div class="od-field od-fill"
          ><h2>{{ count('rejected') ? '有材料需要你修改' : '当前没有待修改材料' }}</h2
          ><p v-if="count('rejected')"
            ><strong class="action-count od-nowrap">{{ count('rejected') }} 份待修改</strong> ·
            请查看审核意见并补充材料</p
          ><p v-else>可以查看审核进度，或继续准备新的加分申请。</p></div
        ><button
          v-if="count('rejected')"
          class="workbench-primary od-fixed"
          @click="$emit('navigate', 'submit-revision')"
          >去修改 <span aria-hidden="true">→</span></button
        ><button v-else class="home-link od-fixed" @click="$emit('navigate', 'my-forms')"
          >准备申请</button
        ></template
      >
    </section>
    <section class="home-panel home-material-panel" aria-label="加分材料进度">
      <div class="workbench-section-head od-row"
        ><h2 class="od-fill">材料审核进度</h2
        ><button class="home-link" @click="$emit('navigate', 'application-record')"
          >查看申请记录</button
        ></div
      >
      <p v-if="store.loading" role="status">正在加载…</p
      ><p v-else-if="store.error">进度暂不可用，请在上方重新加载。</p>
      <template v-else
        ><p class="workbench-total">已提交 {{ submitted.length }} 份加分材料</p
        ><div class="home-statuses"
          ><div
            v-for="status in statuses"
            :key="status.key"
            class="od-stat"
            :class="'status-' + status.key"
            ><strong class="workbench-number od-nowrap"
              >{{ count(status.key) }}<small>份</small></strong
            ><span class="status-caption"><i aria-hidden="true"></i>{{ status.label }}</span></div
          ></div
        ><p v-if="!submitted.length" class="home-note"
          >还没有提交材料，可前往“我的表单”创建申请。</p
        ></template
      >
    </section>
    <section class="home-panel home-period-panel" aria-label="推免申请时间"
      ><div class="workbench-section-head od-row"><h2 class="od-fill">申请时间</h2></div
      ><p v-if="dateLoading" role="status">正在获取申请时间…</p
      ><div v-else-if="dateError" class="home-error"
        >{{ dateError }} <button class="home-link" @click="loadDates">重新加载</button></div
      ><dl v-else class="home-dates"
        ><div v-for="(date, index) in dateRows" :key="date.label" class="home-date-row"
          ><dt>{{ date.label }}</dt
          ><dd class="home-date-value od-row"
            ><span class="od-nowrap">{{ date.text }}</span
            ><button
              v-if="index === dateRows.length - 1"
              class="home-link od-fixed"
              @click="$emit('navigate', 'regulations')"
              >查看推免条例</button
            ></dd
          ></div
        ></dl
      ></section
    >
    <p v-if="isDemo" class="home-note"
      >演示数据，仅保存在当前浏览器，不代表正式申请记录或开放日期。</p
    >
  </section>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useGreeting } from '@/composables/useGreeting.js'
import { useAuthStore } from '@/stores/auth.js'
import { useApplicationsStore } from '@/stores/applications.js'
import api from '@/services/api.js'
defineEmits(['navigate'])
const auth = useAuthStore()
const store = useApplicationsStore()
const isDemo = import.meta.env.MODE === 'demo'
const greeting = useGreeting()
const submitted = computed(() =>
  store.applications
    .filter(
      (a) =>
        String(a.studentId || a.student_id) ===
        String(auth.user?.studentId || auth.user?.student_id || auth.user?.username)
    )
    .filter((a) => ['approved', 'pending', 'rejected'].includes(a.status))
)
const statuses = [
  { key: 'approved', label: '已通过' },
  { key: 'pending', label: '审核中' },
  { key: 'rejected', label: '待修改' }
]
const count = (s) => submitted.value.filter((a) => a.status === s).length
const settings = ref({})
const dateLoading = ref(true)
const dateError = ref('')
const dateLabel = (value) => {
  if (!value) return '尚未公布'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '日期暂不可用' : `${d.getMonth() + 1}月${d.getDate()}日`
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
  ].map((row) => {
    const d = new Date(row.value)
    const valid = Boolean(row.value) && !Number.isNaN(d.getTime())
    return {
      ...row,
      text: dateLabel(row.value),
      parts: valid
        ? {
            month: String(d.getMonth() + 1)
              .padStart(2, '0')
              .split(''),
            day: String(d.getDate()).padStart(2, '0').split('')
          }
        : null
    }
  })
)
async function loadDates() {
  dateLoading.value = true
  dateError.value = ''
  try {
    const r = await api.getPublicSystemInfo()
    settings.value = r.data || {}
  } catch {
    dateError.value = '申请时间暂时无法获取，请重试。'
  } finally {
    dateLoading.value = false
  }
}
onMounted(() => {
  loadDates()
  store.fetchApplications()
})
</script>
