<template>
  <section class="home-page student-home-reference">
    <WelcomeHeader :name="auth.userName" subtitle="STUDENT DASHBOARD" />
    <p v-if="store.loading || materialLoading" role="status">正在获取材料进度…</p>
    <div v-else-if="store.error" class="home-error">
      {{ store.error }}
      <button class="home-link" @click="store.fetchApplications()">重新加载</button>
    </div>
    <WorkbenchAction
      v-else
      :title="correctionCount ? '有材料需要你修改' : '当前没有待修改材料'"
      aria-label="待办材料"
    >
      <template #description>
        <p v-if="correctionCount">
          <strong class="action-count od-nowrap">{{ correctionCount }} 份待修改</strong>
          · 包含竞赛新材料、非竞赛新材料与兼容申请，请查看审核意见
        </p>
        <p v-else>可以查看审核进度，或继续准备新的加分申请。</p>
      </template>
      <template #action>
        <button
          v-if="correctionCount"
          class="workbench-primary od-fixed"
          @click="navigateCorrection"
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
        ><h2 class="od-fill">非竞赛材料审核进度</h2
        ><button class="home-link" @click="$emit('navigate', 'application-record')"
          >查看申请记录</button
        ></div
      >
      <p v-if="store.loading || materialLoading" role="status">正在加载…</p
      ><p v-else-if="store.error">进度暂不可用，请在上方重新加载。</p>
      <template v-else
        ><p class="workbench-total">已提交 {{ combinedSubmittedCount }} 份加分材料</p
        ><div class="home-statuses"
          ><div
            v-for="status in statuses"
            :key="status.key"
            class="od-stat"
            :class="'status-' + status.key"
            ><strong class="workbench-number od-nowrap"
              >{{ combinedCount(status.key) }}<small>份</small></strong
            ><span class="status-caption"><i aria-hidden="true"></i>{{ status.label }}</span></div
          ></div
        ><p v-if="materialError" class="home-note" role="alert"
          >{{ materialError }}
          <button class="home-link" @click="loadMaterialSummary">重试</button></p
        ><p v-else class="home-note">包含旧兼容申请与新材料记录。</p
        ><p v-if="!combinedSubmittedCount" class="home-note"
          >还没有提交非竞赛材料，可前往“提交材料”创建。</p
        ></template
      >
    </section>
    <section class="home-panel" aria-label="竞赛新链路进度">
      <div class="workbench-section-head od-row"
        ><h2 class="od-fill">竞赛材料（新链路）</h2
        ><button class="home-link" @click="$emit('navigate', 'materials')"
          >进入竞赛申报</button
        ></div
      >
      <p v-if="competitionLoading" role="status">正在读取权威竞赛进度…</p>
      <p v-else-if="competitionError" role="alert">{{ competitionError }}</p>
      <div v-else class="home-statuses">
        <div class="od-stat status-pending"
          ><strong class="workbench-number"
            >{{ competitionSummary.pending_count || 0 }}<small>份</small></strong
          ><span class="status-caption">待审核</span></div
        >
        <div class="od-stat status-rejected"
          ><strong class="workbench-number"
            >{{ competitionSummary.needs_correction_count || 0 }}<small>份</small></strong
          ><span class="status-caption">待修改</span></div
        >
        <div class="od-stat status-approved"
          ><strong class="workbench-number"
            >{{ competitionSummary.completed_count || 0 }}<small>份</small></strong
          ><span class="status-caption">已完成</span></div
        >
      </div>
      <p class="home-note">以上来自 MaterialRecord 权威状态；下方旧申请数据仅用于非竞赛兼容。</p>
    </section>
    <ApplicationPeriodPanel @navigate="$emit('navigate', $event)" />
    <p v-if="isDemo" class="home-note"
      >演示数据，仅保存在当前浏览器，不代表正式申请记录或开放日期。</p
    >
  </section>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useApplicationsStore } from '@/stores/applications.js'
import WelcomeHeader from '@/components/common/WelcomeHeader.vue'
import WorkbenchAction from '@/components/common/WorkbenchAction.vue'
import ApplicationPeriodPanel from '@/components/common/ApplicationPeriodPanel.vue'
import materialApi from '@/services/materialApi.js'
import { isNonCompetitionCompatibilityApplication } from '@/services/teacherApplicationBoundary.js'
const emit = defineEmits(['navigate'])
const auth = useAuthStore()
const store = useApplicationsStore()
const isDemo = import.meta.env.MODE === 'demo'
const competitionSummary = ref({}),
  competitionLoading = ref(true),
  competitionError = ref('')
const materialSummary = ref({}),
  materialLoading = ref(true),
  materialError = ref('')
const materialNeedsAttention = computed(
  () =>
    Number(materialSummary.value.needs_correction_count || 0) +
    Number(materialSummary.value.rejected_count || 0)
)
const correctionCount = computed(
  () =>
    count('rejected') +
    Number(competitionSummary.value.needs_correction_count || 0) +
    materialNeedsAttention.value
)
function navigateCorrection() {
  const competitionNeedsCorrection = Number(
    competitionSummary.value.needs_correction_count || 0
  )
  emit(
    'navigate',
    competitionNeedsCorrection || materialNeedsAttention.value ? 'materials' : 'submit-revision'
  )
}
const submitted = computed(() =>
  store.applications
    .filter(
      (a) =>
        String(a.studentId || a.student_id) ===
        String(auth.user?.studentId || auth.user?.student_id || auth.user?.username)
    )
    .filter(isNonCompetitionCompatibilityApplication)
    .filter((a) => ['approved', 'pending', 'rejected'].includes(a.status))
)
const statuses = [
  { key: 'approved', label: '已通过' },
  { key: 'pending', label: '审核中' },
  { key: 'rejected', label: '待修改' }
]
const count = (s) => submitted.value.filter((a) => a.status === s).length
const combinedSubmittedCount = computed(
  () => submitted.value.length + Number(materialSummary.value.submitted_count || 0)
)
const combinedCount = (status) => {
  const base = count(status)
  if (status === 'approved') return base + Number(materialSummary.value.approved_count || 0)
  if (status === 'pending') return base + Number(materialSummary.value.pending_count || 0)
  return (
    base +
    Number(materialSummary.value.needs_correction_count || 0) +
    Number(materialSummary.value.rejected_count || 0)
  )
}
async function loadMaterialSummary() {
  materialLoading.value = true
  materialError.value = ''
  try {
    materialSummary.value = await materialApi.getStudentMaterialSummary()
  } catch (error) {
    materialError.value = error.message || '非竞赛新材料统计暂不可用'
  } finally {
    materialLoading.value = false
  }
}
onMounted(async () => {
  store.fetchApplications()
  loadMaterialSummary()
  try {
    competitionSummary.value = await materialApi.getCompetitionWorkbenchSummary()
  } catch (error) {
    competitionError.value = error.message || '竞赛进度暂不可用'
  } finally {
    competitionLoading.value = false
  }
})
</script>
