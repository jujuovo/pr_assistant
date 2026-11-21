<template>
  <section class="home-page student-home-reference">
    <WelcomeHeader :name="auth.userName" subtitle="STUDENT DASHBOARD" />
    <p v-if="materialLoading" role="status">正在获取材料进度…</p>
    <WorkbenchAction
      v-else
      :title="correctionCount ? '有材料需要你修改' : '当前没有待修改材料'"
      aria-label="待办材料"
    >
      <template #description>
        <p v-if="correctionCount">
          <strong class="action-count od-nowrap">{{ correctionCount }} 份待修改</strong>
          · 请查看教师审核意见并补充材料
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
    <section class="home-panel home-material-panel" aria-label="材料审核进度">
      <div class="workbench-section-head od-row"
        ><h2 class="od-fill">材料审核进度</h2
        ><button class="home-link" @click="$emit('navigate', 'application-record')"
          >查看我的材料</button
        ></div
      >
      <p v-if="materialLoading" role="status">正在加载…</p>
      <template v-else
        ><p class="workbench-total">已提交 {{ submittedCount }} 份材料</p
        ><div class="home-statuses"
          ><div
            v-for="status in statuses"
            :key="status.key"
            class="od-stat"
            :class="'status-' + status.key"
            ><strong class="workbench-number od-nowrap"
              >{{ materialCount(status.key) }}<small>份</small></strong
            ><span class="status-caption"><i aria-hidden="true"></i>{{ status.label }}</span></div
          ></div
        ><p v-if="materialError" class="home-note" role="alert"
          >{{ materialError }}
          <button class="home-link" @click="loadMaterialSummary">重试</button></p
        ><p v-else class="home-note"
          >包含学业竞赛、创业创新、学术论文、社会工作、志愿服务、社会实践与文体活动。</p
        ><p v-if="!submittedCount" class="home-note"
          >还没有提交材料，可前往“提交材料”创建。</p
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
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import WelcomeHeader from '@/components/common/WelcomeHeader.vue'
import WorkbenchAction from '@/components/common/WorkbenchAction.vue'
import ApplicationPeriodPanel from '@/components/common/ApplicationPeriodPanel.vue'
import materialApi from '@/services/materialApi.js'
const emit = defineEmits(['navigate'])
const auth = useAuthStore()
const isDemo = import.meta.env.MODE === 'demo'
const materialSummary = ref({}),
  materialLoading = ref(true),
  materialError = ref('')
const materialNeedsAttention = computed(
  () =>
    Number(materialSummary.value.needs_correction_count || 0) +
    Number(materialSummary.value.rejected_count || 0)
)
const correctionCount = computed(
  () => materialNeedsAttention.value
)
function navigateCorrection() {
  emit('navigate', 'application-record')
}
const statuses = [
  { key: 'approved', label: '已通过' },
  { key: 'pending', label: '审核中' },
  { key: 'rejected', label: '待修改' }
]
const submittedCount = computed(() => Number(materialSummary.value.submitted_count || 0))
const materialCount = (status) => {
  if (status === 'approved') return Number(materialSummary.value.approved_count || 0)
  if (status === 'pending') return Number(materialSummary.value.pending_count || 0)
  return (
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
    materialError.value = error.message || '材料统计暂不可用'
  } finally {
    materialLoading.value = false
  }
}
onMounted(async () => {
  await loadMaterialSummary()
})
</script>
