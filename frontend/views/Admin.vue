<template>
  <div class="container">
    <Header :user-name="authStore.userName" :user-avatar="authStore.userAvatar" title="推免加分系统-管理端"
      @go-to-profile="goToProfile" />

    <div class="content-wrapper">
      <Sidebar :active-page="currentPage" @page-change="switchPage" @sidebar-toggle="handleSidebarToggle" />

      <main :class="['main-content', { 'sidebar-collapsed': isSidebarCollapsed }]">
        <!-- 动态显示当前页面 -->
        <component :is="currentPageComponent" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'

import Header from '../components/common/Header.vue'
import Sidebar from '../components/common/Sidebar.vue'

// 导入管理员端组件
import UserManagement from '../components/admin/UserManagement.vue'
import ApplicationManagement from '../components/admin/ApplicationManagement.vue'
import RuleManagement from '../components/admin/RuleManagement.vue'
import StatisticsReport from '../components/common/StatisticsReport.vue'
import SystemSettings from '../components/admin/SystemSettings.vue'
import Profile from '../components/common/Profile.vue'
import FacultyManagement from '../components/admin/FacultyManagement.vue'
import ScoreManagement from '../components/admin/ScoreManagement.vue'
import GraduateFileManagement from '../components/admin/GraduateFileManagement.vue'

const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()

// 当前活动页面
const currentPage = ref('user-management')

// 页面组件映射
const pageComponents = {
  'user-management': UserManagement,
  'score-management': ScoreManagement,
  'data-management': ApplicationManagement,
  'rule-management': RuleManagement,
  'faculty-management': FacultyManagement,
  'statistics-report': StatisticsReport,
  'system-settings': SystemSettings,
  'profile': Profile,
  'graduate-file-management': GraduateFileManagement
}

const currentPageComponent = computed(() => pageComponents[currentPage.value])

// 用户信息
const userInfo = computed(() => ({
  name: authStore.userName,
  faculty: authStore.user?.faculty || '信息学院',
  roleName: authStore.user?.roleName || '系统管理员'
}))

// 侧边栏收起状态
const isSidebarCollapsed = ref(false)

// 处理侧边栏切换事件
const handleSidebarToggle = (isOpen) => {
  isSidebarCollapsed.value = !isOpen
  // 移除直接操作DOM的代码，改为通过CSS选择器和类名切换
}

// 切换页面
const switchPage = (page) => {
  currentPage.value = page
}

// 切换到个人信息页面
const goToProfile = () => {
  currentPage.value = 'profile'
}

// 权限验证
onMounted(() => {
  if (authStore.role !== 'admin') {
    toastStore.error('您没有权限访问管理员端')
    router.push('/login')
  }
})
</script>

<style scoped>
.container {
  display: flex;
  flex-direction: column;
  height: 100vh !important;
  width: 100vw !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.content-wrapper {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
  width: 100%;
}

.main-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background-color: #f5f7fa;
  min-height: 0;
  width: 100%;
}
</style>