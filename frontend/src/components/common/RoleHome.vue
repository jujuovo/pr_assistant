<template>
  <section :class="['home-page', { 'student-home-reference': ['teacher', 'admin'].includes(role) }]"
    ><WelcomeHeader
      :name="auth.userName"
      :subtitle="role === 'teacher' ? 'TEACHER DASHBOARD' : 'ADMIN DASHBOARD'"
    /><WorkbenchAction v-if="role === 'teacher'" title="有材料需要你审核" aria-label="待审核材料">
      <template #description>
        <p>
          <strong class="action-count od-nowrap">
            {{ applicationsStore.pendingApplications.length }} 份待审核
          </strong>
        </p>
      </template>
      <template #action>
        <button class="workbench-primary od-fixed" @click="$emit('navigate', 'pending-review')">
          去审核 <span aria-hidden="true">→</span>
        </button>
      </template>
    </WorkbenchAction>
    <template v-else
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
import { useApplicationsStore } from '@/stores/applications.js'
import WelcomeHeader from '@/components/common/WelcomeHeader.vue'
import WorkbenchAction from '@/components/common/WorkbenchAction.vue'
import ApplicationPeriodPanel from '@/components/common/ApplicationPeriodPanel.vue'
const props = defineProps({ role: String })
defineEmits(['navigate'])
const auth = useAuthStore()
const applicationsStore = useApplicationsStore()
const isDemo = import.meta.env.MODE === 'demo'
const adminItems = [
  { key: 'faculty-management', title: '学院管理', desc: '维护学院、系与专业' },
  { key: 'user-management', title: '用户管理', desc: '维护学生与教师账号' },
  { key: 'data-management', title: '申请管理', desc: '查看申请与审核结果' },
  { key: 'score-management', title: '成绩管理', desc: '维护成绩与比例设置' }
]
</script>
