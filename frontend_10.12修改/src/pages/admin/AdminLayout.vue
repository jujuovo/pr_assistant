<template>
  <div class="container unified-system-shell">
    <Header
      :user-name="authStore.userName"
      :user-avatar="authStore.userAvatar"
      title="推免加分系统-管理端"
      @go-to-profile="goToProfile"
    />

    <div class="content-wrapper">
      <Sidebar
        :active-page="currentPage"
        @page-change="switchPage"
        @sidebar-toggle="handleSidebarToggle"
      />

      <main
        :class="['main-content', 'unified-content', { 'sidebar-collapsed': isSidebarCollapsed }]"
      >
        <!-- 动态显示当前页面 -->
        <RoleHome v-if="currentPage === 'home'" role="admin" @navigate="switchPage" /><component
          v-else
          :is="currentPageComponent"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { useToastStore } from '@/stores/toast.js'

import Header from '@/components/common/Header.vue'
import RoleHome from '@/components/common/RoleHome.vue'
import Sidebar from '@/components/common/Sidebar.vue'

// 导入管理员端组件
import UserManagement from '@/pages/admin/users/UserManagement.vue'
import ApplicationManagement from '@/pages/admin/applications/ApplicationManagement.vue'
import RuleManagement from '@/pages/admin/rules/RuleManagement.vue'
import StatisticsReport from '@/pages/common/statistics/StatisticsReport.vue'
import SystemSettings from '@/pages/admin/settings/SystemSettings.vue'
import Profile from '@/pages/common/profile/Profile.vue'
import FacultyManagement from '@/pages/admin/organization/FacultyManagement.vue'
import ScoreManagement from '@/pages/admin/scores/ScoreManagement.vue'
import GraduateFileManagement from '@/pages/admin/files/GraduateFileManagement.vue'

const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()

// 当前活动页面
const currentPage = ref('home')

// 页面组件映射
const pageComponents = {
  'user-management': UserManagement,
  'score-management': ScoreManagement,
  'data-management': ApplicationManagement,
  'rule-management': RuleManagement,
  'faculty-management': FacultyManagement,
  'statistics-report': StatisticsReport,
  'system-settings': SystemSettings,
  profile: Profile,
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

<style scoped src="@/assets/styles/layouts/management-layout.css"></style>
