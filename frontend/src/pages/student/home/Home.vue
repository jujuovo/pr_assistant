<template>
  <section class="home-page student-home-reference">
    <WelcomeHeader :name="auth.userName" subtitle="STUDENT DASHBOARD" />
    <p v-if="store.loading" role="status">正在获取材料进度…</p>
    <div v-else-if="store.error" class="home-error">
      {{ store.error }}
      <button class="home-link" @click="store.fetchApplications()">重新加载</button>
    </div>
    <WorkbenchAction
      v-else
      :title="count('rejected') ? '有材料需要你修改' : '当前没有待修改材料'"
      aria-label="待办材料"
    >
      <template #description>
        <p v-if="count('rejected')">
          <strong class="action-count od-nowrap">{{ count('rejected') }} 份待修改</strong>
          · 请查看审核意见并补充材料
        </p>
        <p v-else>可以查看审核进度，或继续准备新的加分申请。</p>
      </template>
      <template #action>
        <button
          v-if="count('rejected')"
          class="workbench-primary od-fixed"
          @click="$emit('navigate', 'submit-revision')"
        >
          去修改 <span aria-hidden="true">→</span>
        </button>
        <button v-else class="home-link od-fixed" @click="$emit('navigate', 'my-forms')">
          准备申请
        </button>
      </template>
    </WorkbenchAction>
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
    <ApplicationPeriodPanel @navigate="$emit('navigate', $event)" />
    <p v-if="isDemo" class="home-note"
      >演示数据，仅保存在当前浏览器，不代表正式申请记录或开放日期。</p
    >
  </section>
</template>
<script setup>
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useApplicationsStore } from '@/stores/applications.js'
import WelcomeHeader from '@/components/common/WelcomeHeader.vue'
import WorkbenchAction from '@/components/common/WorkbenchAction.vue'
import ApplicationPeriodPanel from '@/components/common/ApplicationPeriodPanel.vue'
defineEmits(['navigate'])
const auth = useAuthStore()
const store = useApplicationsStore()
const isDemo = import.meta.env.MODE === 'demo'
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
onMounted(() => {
  store.fetchApplications()
})
</script>
