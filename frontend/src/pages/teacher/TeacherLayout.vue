<template>
  <div class="container unified-system-shell">
    <Header
      :user-name="authStore.userName"
      :user-avatar="authStore.userAvatar"
      title="厦门大学推免加分系统"
      @go-to-profile="goToProfile"
    />

    <div class="content-wrapper">
      <Sidebar
        :active-page="currentPage === 'rankings' ? 'statistics-report' : currentPage"
        @page-change="switchPage"
        @sidebar-toggle="handleSidebarToggle"
      />

      <main
        :class="['main-content', 'unified-content', { 'sidebar-collapsed': isSidebarCollapsed }]"
      >
        <!-- 动态显示当前页面 -->
        <RoleHome v-if="currentPage === 'home'" role="teacher" @navigate="switchPage" /><component
          v-else
          :is="currentPageComponent"
          @new-application="switchToPendingReview"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { useToastStore } from '@/stores/toast.js'

import Header from '@/components/common/Header.vue'
import RoleHome from '@/components/common/RoleHome.vue'
import Sidebar from '@/components/common/Sidebar.vue'

// 导入教师端组件
import PendingReview from '@/pages/teacher/reviews/PendingReview.vue'
import ReviewHistory from '@/pages/teacher/reviews/ReviewHistory.vue'
import Profile from '@/pages/common/profile/Profile.vue'
import TeacherRanking from '@/pages/teacher/rankings/TeacherRanking.vue'
import TeacherStudentSummary from '@/pages/teacher/students/TeacherStudentSummary.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const toastStore = useToastStore()

// 当前活动页面
const currentPage = ref(route.query.page || 'home')

// 页面组件映射
const pageComponents = {
  'pending-review': PendingReview,
  'review-history': ReviewHistory,
  'statistics-report': TeacherRanking,
  'student-summary': TeacherStudentSummary,
  profile: Profile,
  rankings: TeacherRanking
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
  if (page === currentPage.value) return
  currentPage.value = page
  const query = { ...route.query, page }
  delete query.ranking_only
  delete query.batch_id
  router.push({ query })
}
watch(() => route.query.page, page => { if (page) currentPage.value = page })

// 切换到待审核页面（用于从其他页面跳转）
const switchToPendingReview = () => {
  if (currentPage.value === 'pending-review') return
  currentPage.value = 'pending-review'
  router.push({ query: { ...route.query, page: 'pending-review' } })
}

// 切换到个人信息页面
const goToProfile = () => {
  if (currentPage.value === 'profile') return
  currentPage.value = 'profile'
  router.push({ query: { ...route.query, page: 'profile' } })
}

// 权限验证和数据加载
onMounted(() => {
  if (authStore.role !== 'teacher') {
    toastStore.error('您没有权限访问教师端')
    router.push('/login')
  }
})
</script>

<style scoped src="@/assets/styles/layouts/management-layout.css"></style>
