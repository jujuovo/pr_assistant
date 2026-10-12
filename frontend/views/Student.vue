<template>
  <div class="container">
    <Header :user-name="authStore.userName" :user-avatar="authStore.userAvatar" title="推免加分系统"
      @go-to-profile="goToProfile" />

    <div class="content-wrapper">
      <Sidebar :active-page="currentPage" @page-change="switchPage" @sidebar-toggle="handleSidebarToggle" />

      <main :class="['main-content', { 'sidebar-collapsed': isSidebarCollapsed }]">
        <component :is="currentPageComponent" @switch-page="switchPage" @edit-application="handleEditApplication"
          :edit-application-id="editApplicationId" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useApplicationsStore } from '../stores/applications'
import Header from '../components/common/Header.vue'
import Sidebar from '../components/common/Sidebar.vue'
import ApplicationForm from '../components/student/ApplicationForm.vue'
import ApplicationHistory from '../components/student/ApplicationHistory.vue'
import Statistics from '../components/student/Statistics.vue'
import Profile from '../components/common/Profile.vue'

const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()
const applicationsStore = useApplicationsStore()

const currentPage = ref('application-form')
const editApplicationId = ref(null)

const pageComponents = {
  'application-form': ApplicationForm,
  'application-record': ApplicationHistory,
  'statistics': Statistics,
  'profile': Profile
}

const currentPageComponent = computed(() => pageComponents[currentPage.value])

const userInfo = computed(() => ({
  name: authStore.userName,
  faculty: authStore.user?.faculty?.name || '信息学院',
  major: authStore.user?.major?.name || '计算机科学与技术',
  studentId: authStore.user?.studentId || ''
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

  // 当切换到申请表单页面时，默认重置编辑ID
  if (page === 'application-form') {
    editApplicationId.value = null
  }
}

// 切换到申请表单页面
const switchToApplicationForm = () => {
  currentPage.value = 'application-form'
}

// 切换到个人信息页面
const goToProfile = () => {
  currentPage.value = 'profile'
}

// 处理编辑申请
const handleEditApplication = (applicationId) => {
  editApplicationId.value = applicationId
  currentPage.value = 'application-form'
}

// 权限验证和数据加载
onMounted(() => {
  if (authStore.role !== 'student') {
    toastStore.error('您没有权限访问学生端')
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