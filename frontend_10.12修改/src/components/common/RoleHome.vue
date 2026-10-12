<template>
  <section class="home-page"
    ><h1>{{ greeting }}，{{ auth.userName }}</h1
    ><p class="home-subtitle"
      >{{ role === 'teacher' ? '教师主页' : '管理员主页' }} · 厦门大学推免加分系统</p
    ><section class="home-panel"
      ><h2>工作概览</h2
      ><p>{{
        role === 'teacher'
          ? '在这里集中查看待审核申请与审核记录。'
          : '在这里组织用户、申请、成绩与规则管理工作。'
      }}</p
      ><p class="home-note">主页框架已建立，概览内容将在后续补充。</p></section
    ><section class="home-panel"
      ><h2>常用入口</h2
      ><div class="home-shortcuts"
        ><button
          v-for="i in items"
          :key="i.key"
          class="home-shortcut"
          @click="$emit('navigate', i.key)"
          ><span>{{ i.title }}</span
          ><small>{{ i.desc }}</small></button
        ></div
      ></section
    ><p v-if="isDemo" class="home-note">当前为前端演示，使用本地示例数据。</p></section
  >
</template>
<script setup>
import { computed } from 'vue'
import { useGreeting } from '@/composables/useGreeting.js'
import { useAuthStore } from '@/stores/auth.js'
const props = defineProps({ role: String })
defineEmits(['navigate'])
const auth = useAuthStore()
const isDemo = import.meta.env.MODE === 'demo'
const greeting = useGreeting()
const items = computed(() =>
  props.role === 'teacher'
    ? [
        { key: 'pending-review', title: '待审核申请', desc: '进入申请审核列表' },
        { key: 'review-history', title: '审核记录', desc: '查看已处理申请' },
        { key: 'statistics-report', title: '统计报表', desc: '查看专业成绩报表' }
      ]
    : [
        { key: 'user-management', title: '用户管理', desc: '维护学生与教师账号' },
        { key: 'data-management', title: '申请管理', desc: '查看申请与审核结果' },
        { key: 'score-management', title: '成绩管理', desc: '维护成绩与比例设置' },
        { key: 'rule-management', title: '规则管理', desc: '维护学院加分规则' },
        { key: 'faculty-management', title: '学院管理', desc: '维护学院、系与专业' },
        { key: 'graduate-file-management', title: '推免文件管理', desc: '维护推免相关文件' }
      ]
)
</script>
