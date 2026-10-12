<template>
  <div class="container">
    <Header :user-name="authStore.userName" :user-avatar="authStore.userAvatar" title="推免加分系统-审核端"
      @go-to-profile="goToProfile" />

    <div class="content-wrapper">
      <Sidebar :active-page="currentPage" @page-change="switchPage" @sidebar-toggle="handleSidebarToggle" />

      <main :class="['main-content', { 'sidebar-collapsed': isSidebarCollapsed }]">
        <!-- 动态显示当前页面 -->
        <component :is="currentPageComponent" @new-application="switchToPendingReview" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useApplicationsStore } from '../stores/applications'
import { useToastStore } from '../stores/toast'

import Header from '../components/common/Header.vue'
import Sidebar from '../components/common/Sidebar.vue'

// 导入教师端组件
import PendingReview from '../components/teacher/PendingReview.vue'
import ReviewHistory from '../components/teacher/ReviewHistory.vue'
import StatisticsReport from '../components/common/StatisticsReport.vue'
import Profile from '../components/common/Profile.vue'

const router = useRouter()
const authStore = useAuthStore()
const applicationsStore = useApplicationsStore()
const toastStore = useToastStore()

// 当前活动页面
const currentPage = ref('pending-review')

// 页面组件映射
const pageComponents = {
  'pending-review': PendingReview,
  'review-history': ReviewHistory,
  'statistics-report': StatisticsReport,
  'profile': Profile
}

const currentPageComponent = computed(() => pageComponents[currentPage.value])

// 用户信息
const userInfo = computed(() => ({
  name: authStore.userName,
  faculty: authStore.user?.faculty?.name || '信息学院',
  roleName: authStore.user?.roleName || '审核员'
}))

// 侧边栏收起状态
const isSidebarCollapsed = ref(false)

// 处理侧边栏切换事件
const handleSidebarToggle = (isOpen) => {
  isSidebarCollapsed.value = !isOpen
}

// 切换页面
const switchPage = (page) => {
  currentPage.value = page
}

// 切换到待审核页面（用于从其他页面跳转）
const switchToPendingReview = () => {
  currentPage.value = 'pending-review'
}

// 切换到个人信息页面
const goToProfile = () => {
  currentPage.value = 'profile'
}

// 权限验证和数据加载
onMounted(() => {
  if (authStore.role !== 'teacher') {
    toastStore.error('您没有权限访问教师端')
    router.push('/login')
  } else {
    // 确保数据已加载
    if (applicationsStore.applications.length === 0) {
      applicationsStore.fetchApplications()
    }
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