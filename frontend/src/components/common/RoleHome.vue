<template>
  <section :class="['home-page', { 'student-home-reference': ['teacher', 'admin'].includes(role) }]"
    ><WelcomeHeader
      :name="auth.userName"
      :subtitle="role === 'teacher' ? 'TEACHER DASHBOARD' : 'ADMIN DASHBOARD'"
    /><WorkbenchAction v-if="role === 'teacher'" title="有材料需要你审核" aria-label="待审核材料">
      <template #description>
        <p v-if="competitionLoading || materialLoading" role="status">正在读取待审核材料数量…</p>
        <p v-else-if="competitionError || materialError" role="alert">暂时无法获取待审核材料总数。</p>
        <p v-else>
          <strong class="action-count od-nowrap">{{ pendingCount }} 份竞赛材料待审核。</strong>
        </p>
      </template>
      <template #action>
        <button class="workbench-primary od-fixed" @click="$emit('navigate', 'pending-review')">
          去审核 <span aria-hidden="true">→</span>
        </button>
      </template>
    </WorkbenchAction>
    <ApplicationPeriodPanel v-if="role === 'teacher'" hide-action />
    <template v-if="role === 'admin'"
      ><ApplicationPeriodPanel
        action-label="查看规则"
        action-target="rule-management"
        emphasize-action
        @navigate="$emit('navigate', $event)"
      /><section class="home-panel"
      ><h2>常用入口</h2
      ><div class="home-shortcuts admin-home-shortcuts"
        ><button
          v-for="i in adminItems"
          :key="i.key"
          class="home-shortcut"
          @click="$emit('navigate', i.key)"
          ><span>{{ i.title }}</span
          ><small>{{ i.desc }}</small></button
        ></div
      ></section
    ></template
    ><p v-if="isDemo" class="home-note">当前为前端演示，使用本地示例数据。</p></section
  >
</template>
<script setup>
import { useAuthStore } from '@/stores/auth.js'
import WelcomeHeader from '@/components/common/WelcomeHeader.vue'
import WorkbenchAction from '@/components/common/WorkbenchAction.vue'
import ApplicationPeriodPanel from '@/components/common/ApplicationPeriodPanel.vue'
import { computed, onMounted, ref } from 'vue'
import materialApi from '@/services/materialApi.js'
const props = defineProps({ role: String })
defineEmits(['navigate'])
const auth = useAuthStore()
const isDemo = import.meta.env.MODE === 'demo'
const competitionSummary = ref({}), competitionLoading = ref(props.role === 'teacher'), competitionError = ref('')
const materialSummary = ref({}), materialLoading = ref(props.role === 'teacher'), materialError = ref('')
const pendingCount = computed(() =>
  (competitionSummary.value.pending_count ?? 0) + (materialSummary.value.pending_count ?? 0)
)
const adminItems = [
  { key: 'faculty-management', title: '学院管理', desc: '维护学院、系与专业' },
  { key: 'user-management', title: '用户管理', desc: '维护学生与教师账号' },
  { key: 'data-management', title: '申请管理', desc: '查看申请与审核结果' },
  { key: 'score-management', title: '成绩管理', desc: '维护成绩与比例设置' }
]
onMounted(async () => {
  if (props.role !== 'teacher') return
  try { competitionSummary.value = await materialApi.getCompetitionWorkbenchSummary() }
  catch (error) { competitionError.value = error.message || '竞赛待审数暂不可用' }
  finally { competitionLoading.value = false }
  try { materialSummary.value = await materialApi.getTeacherMaterialSummary() }
  catch (error) { materialError.value = error.message || '非竞赛待审数暂不可用' }
  finally { materialLoading.value = false }
})
</script>
