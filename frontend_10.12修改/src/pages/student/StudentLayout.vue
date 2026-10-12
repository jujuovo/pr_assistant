<template>
  <div class="container student-workbench-shell unified-system-shell">
    <Header
      :user-name="authStore.userName"
      :user-avatar="authStore.userAvatar"
      title="厦门大学推免加分系统"
      @go-to-profile="goToProfile"
    />

    <div class="content-wrapper">
      <StudentNavigation :active-page="navigationActivePage" @page-change="switchPage" />

      <main
        :class="[
          'main-content',
          { 'unified-content': currentPage !== 'home', 'sidebar-collapsed': isSidebarCollapsed }
        ]"
      >
        <Home v-if="currentPage === 'home'" @navigate="switchPage" />
        <HomeSections
          v-else-if="sectionPages.includes(currentPage)"
          :page="currentPage"
          @navigate="switchPage"
          @edit="handleEditApplication"
        />
        <ApplicationCategories
          v-else-if="currentPage === 'application-categories'"
          @select="openApplicationForm"
          @navigate="switchPage"
        />
        <AcademicPerformance
          v-else-if="currentPage === 'academic-performance'"
          @back-to-categories="backToApplicationCategories"
        />
        <ApplicationForm
          v-else-if="currentPage === 'application-form'"
          :edit-application-id="editApplicationId"
          :selected-category="selectedCategory"
          @back-to-categories="backToApplicationCategories"
        />
        <component
          v-else
          :is="currentPageComponent"
          @switch-page="switchPage"
          @edit-application="handleEditApplication"
          :edit-application-id="editApplicationId"
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
import { useApplicationsStore } from '@/stores/applications.js'
import Header from '@/components/common/Header.vue'
import StudentNavigation from '@/components/student/StudentNavigation.vue'
import Home from '@/pages/student/home/Home.vue'
import HomeSections from '@/pages/student/home/HomeSections.vue'
import ApplicationCategories from '@/pages/student/applications/ApplicationCategories.vue'
import AcademicPerformance from '@/pages/student/applications/AcademicPerformance.vue'
const sectionPages = ['regulations', 'my-forms', 'submit-revision', 'feedback']
import ApplicationForm from '@/pages/student/applications/ApplicationForm.vue'
import ApplicationHistory from '@/pages/student/applications/ApplicationHistory.vue'
import Statistics from '@/pages/student/statistics/Statistics.vue'
import Profile from '@/pages/common/profile/Profile.vue'

const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()
const applicationsStore = useApplicationsStore()

const currentPage = ref('home')
const editApplicationId = ref(null)
const selectedCategory = ref(null)

const pageComponents = {
  'application-record': ApplicationHistory,
  statistics: Statistics,
  profile: Profile
}

const currentPageComponent = computed(() => pageComponents[currentPage.value])
const navigationActivePage = computed(() =>
  ['application-categories', 'academic-performance', 'application-form'].includes(currentPage.value)
    ? 'application-form'
    : currentPage.value
)

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
  if (page === 'application-form') {
    editApplicationId.value = null
    selectedCategory.value = null
    currentPage.value = 'application-categories'
    return
  }
  currentPage.value = page
}

const openApplicationForm = (category) => {
  selectedCategory.value = category
  editApplicationId.value = null
  if (category.key === 'academic-performance') {
    currentPage.value = 'academic-performance'
    return
  }
  currentPage.value = 'application-form'
}

const backToApplicationCategories = () => {
  selectedCategory.value = null
  editApplicationId.value = null
  currentPage.value = 'application-categories'
}

// 切换到个人信息页面
const goToProfile = () => {
  currentPage.value = 'profile'
}

// 处理编辑申请
const handleEditApplication = (applicationId) => {
  editApplicationId.value = applicationId
  selectedCategory.value = null
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

<style scoped src="@/assets/styles/pages/student/StudentLayout.css"></style>
