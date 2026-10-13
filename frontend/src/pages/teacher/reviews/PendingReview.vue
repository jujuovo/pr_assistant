<template>
  <div class="page-content">
    <div class="page-title">
      <span>待审核申请</span>
    </div>
    <!-- 筛选区域 -->
    <div class="filters primary-section-frame">
      <div class="filter-group">
        <span class="filter-label">姓名:</span>
        <input
          type="text"
          class="form-control small"
          v-model="filters.studentName"
          placeholder="请输入姓名"
          @input="filterApplications"
        />
      </div>
      <div class="filter-group">
        <span class="filter-label">学号:</span>
        <input
          type="text"
          class="form-control small"
          v-model="filters.studentId"
          placeholder="请输入学号"
          @input="filterApplications"
        />
      </div>
      <div class="filter-group">
        <span class="filter-label">学院:</span>
        <select
          v-model="filters.faculty"
          @change="handleFacultyChange"
          :disabled="authStore.user?.faculty_id || authStore.user?.facultyId"
        >
          <option value="all">全部</option>
          <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">
            {{ faculty.name }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">所在系:</span>
        <select v-model="filters.department" @change="handleDepartmentChange">
          <option value="all">全部</option>
          <option v-for="department in departments" :key="department.id" :value="department.id">
            {{ department.name }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">专业:</span>
        <select v-model="filters.major" @change="filterApplications">
          <option value="all">全部</option>
          <option v-for="major in majors" :key="major.id" :value="major.id">
            {{ major.name }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">类型:</span>
        <select v-model="filters.type" @change="filterApplications">
          <option value="all">全部</option>
          <option value="academic">学术专长</option>
          <option value="comprehensive">综合表现</option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">学院规则:</span>
        <select v-model="filters.rule" @change="filterApplications">
          <option value="all">全部规则</option>
          <option v-for="rule in availableRules" :key="rule.id" :value="rule.id">
            {{ rule.name }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">申请时间:</span>
        <input
          type="date"
          class="form-control small"
          v-model="filters.startDate"
          @change="filterApplications"
        />
        至
        <input
          type="date"
          class="form-control small"
          v-model="filters.endDate"
          @change="filterApplications"
        />
      </div>
      <button class="btn btn-outline" @click="clearFilters">清空筛选</button>
    </div>
    <!-- 待审核申请表格 -->
    <div class="card">
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">正在加载中...</div>
      </div>
      <div class="table-container">
        <table class="application-table">
          <thead>
            <tr>
              <th>学生姓名</th>
              <th>学号</th>
              <th>所在系</th>
              <th>专业</th>
              <th>申请类型</th>
              <th>选择规则</th>
              <th>申请时间</th>
              <th>自评分数</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="application in paginatedApplications" :key="application.id">
              <td>{{ application.studentName }}</td>
              <td>{{ application.studentId }}</td>
              <td>{{ getDepartmentText(application.department) }}</td>
              <td>{{ getMajorText(application.major) }}</td>
              <td>{{ getTypeText(application.applicationType) }}</td>
              <td>{{ application.rule?.name || '未选择' }}</td>
              <td>{{ formatDate(application.appliedAt) }}</td>
              <td>{{ application.selfScore }}</td>
              <td>
                <button class="btn btn-outline small-btn" @click="reviewApplication(application)">
                  <font-awesome-icon :icon="['fas', 'eye']" /> 审核
                </button>
              </td>
            </tr>
            <tr v-if="paginatedApplications.length === 0">
              <td colspan="9" class="no-data">暂无待审核申请</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <!-- 分页控件 -->
    <div class="pagination">
      <div class="pagination-info"
        >显示 {{ startIndex + 1 }}-{{ endIndex }} 条，共 {{ totalApplications }} 条记录</div
      >
      <div class="pagination-controls">
        <button class="btn btn-outline" :disabled="pagination.currentPage === 1" @click="prevPage">
          <font-awesome-icon :icon="['fas', 'chevron-left']" /> 上一页
        </button>
        <button
          class="btn btn-outline"
          :disabled="pagination.currentPage >= totalPages"
          @click="nextPage"
        >
          下一页 <font-awesome-icon :icon="['fas', 'chevron-right']" />
        </button>
      </div>
    </div>
    <!-- 审核详情模态框 -->
    <ApplicationDetailModal
      v-if="selectedApplication"
      :application="selectedApplication"
      @approve="handleApprove"
      @reject="handleReject"
      @close="closeReviewModal"
      :is-review-mode="true"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useApplicationsStore } from '@/stores/applications.js'
import { useToastStore } from '@/stores/toast.js'
import ApplicationDetailModal from '@/components/common/ApplicationDetailModal.vue'
import api from '@/services/api.js'

const authStore = useAuthStore()
const applicationsStore = useApplicationsStore()
const toastStore = useToastStore()

// 筛选条件
const filters = ref({
  faculty: 'all',
  department: 'all',
  major: 'all',
  type: 'all',
  rule: 'all',
  studentId: '',
  studentName: '',
  startDate: '',
  endDate: ''
})

// 学院、系和专业数据
const faculties = ref([])
const departments = ref([])
const majors = ref([])
const loadingDepartments = ref(false)
const loadingMajors = ref(false)

// 规则列表
const availableRules = ref([])

// 分页
const pagination = ref({
  currentPage: 1,
  pageSize: 10
})

// 当前选中的申请
const selectedApplication = ref(null)

// 加载状态
const loading = computed(() => applicationsStore.loading)

// 筛选和分页处理后的申请数据
const filteredAndPaginatedApplications = computed(() => {
  // 先筛选
  let filterParams = {
    faculty: filters.value.faculty !== 'all' ? filters.value.faculty : undefined,
    department: filters.value.department !== 'all' ? filters.value.department : undefined,
    major: filters.value.major !== 'all' ? filters.value.major : undefined,
    type: filters.value.type !== 'all' ? filters.value.type : undefined,
    rule: filters.value.rule !== 'all' ? filters.value.rule : undefined,
    studentId: filters.value.studentId,
    studentName: filters.value.studentName,
    startDate: filters.value.startDate,
    endDate: filters.value.endDate
  }
  let filtered = applicationsStore.filterApplications(filterParams)

  // 只保留待审核的
  filtered = filtered.filter((app) => app.status === 'pending')

  // 再分页
  const start = (pagination.value.currentPage - 1) * pagination.value.pageSize
  const end = start + pagination.value.pageSize
  return filtered.slice(start, end)
})

// 总记录数
const totalApplications = computed(() => {
  let filtered = applicationsStore.filterApplications({
    faculty: filters.value.faculty !== 'all' ? filters.value.faculty : undefined,
    department: filters.value.department !== 'all' ? filters.value.department : undefined,
    major: filters.value.major !== 'all' ? filters.value.major : undefined,
    type: filters.value.type !== 'all' ? filters.value.type : undefined,
    rule: filters.value.rule !== 'all' ? filters.value.rule : undefined,
    studentId: filters.value.studentId,
    studentName: filters.value.studentName,
    startDate: filters.value.startDate,
    endDate: filters.value.endDate
  })
  return filtered.filter((app) => app.status === 'pending').length
})

// 计算属性
const totalPages = computed(() => {
  return Math.ceil(totalApplications.value / pagination.value.pageSize)
})

const startIndex = computed(() => (pagination.value.currentPage - 1) * pagination.value.pageSize)
const endIndex = computed(() =>
  Math.min(startIndex.value + pagination.value.pageSize, totalApplications.value)
)

const paginatedApplications = computed(() => {
  return filteredAndPaginatedApplications.value
})

// 方法
const getDepartmentText = (department) => {
  return departments[department] || department
}

const getMajorText = (major) => {
  return majors[major] || major
}

const getTypeText = (type) => {
  return type === 'academic' ? '学术专长' : '综合表现'
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString('zh-CN')
}

// 处理学院选择变化
const handleFacultyChange = async () => {
  await loadDepartments(filters.value.faculty)
  filterApplications()
}

// 处理系选择变化
const handleDepartmentChange = async () => {
  await loadMajors(filters.value.department)
  filterApplications()
}

// 清空筛选条件
const clearFilters = async () => {
  // 保存当前学院选择
  const currentFaculty = filters.value.faculty

  filters.value = {
    faculty: currentFaculty, // 保持当前学院选择不变
    department: 'all',
    major: 'all',
    type: 'all',
    rule: 'all',
    studentId: '',
    studentName: '',
    startDate: '',
    endDate: ''
  }
  // 重置到第一页
  pagination.value.currentPage = 1
  // 重新加载所有数据
  await Promise.all([
    loadDepartments(filters.value.faculty), // 根据当前学院加载系
    loadMajors(filters.value.department) // 根据当前系加载专业
  ])
  // 重新加载申请数据
  await applicationsStore.fetchApplications()
}

const filterApplications = () => {
  pagination.value.currentPage = 1
  // 重新加载申请数据以应用新的筛选条件
  applicationsStore.fetchApplications()
}

const prevPage = () => {
  if (pagination.value.currentPage > 1) {
    pagination.value.currentPage--
  }
}

const nextPage = () => {
  if (pagination.value.currentPage < totalPages.value) {
    pagination.value.currentPage++
  }
}

const reviewApplication = (application) => {
  selectedApplication.value = { ...application }
}

const handleApprove = async (approveData) => {
  try {
    // 从对象参数中提取需要的字段
    const { applicationId, finalScore, approveComment } = approveData
    // 调用API批准申请
    await applicationsStore.approveApplication(
      applicationId,
      finalScore,
      approveComment,
      authStore.userName || '当前教师'
    )
    // 重新加载数据
    await applicationsStore.fetchApplications()
    closeReviewModal()
    toastStore.success('申请已通过审核')
  } catch (error) {
    console.error('批准申请失败:', error)
    toastStore.error('批准申请失败，请稍后重试')
  }
}

const handleReject = async (rejectData) => {
  try {
    // 从对象参数中提取需要的字段
    const { applicationId, rejectComment } = rejectData
    // 调用API拒绝申请
    await applicationsStore.rejectApplication(
      applicationId,
      rejectComment,
      authStore.userName || '当前教师'
    )
    // 重新加载数据
    await applicationsStore.fetchApplications()
    closeReviewModal()
    toastStore.success('申请已驳回')
  } catch (error) {
    console.error('拒绝申请失败:', error)
    toastStore.error('拒绝申请失败，请稍后重试')
  }
}

const closeReviewModal = () => {
  selectedApplication.value = null
}

// 生命周期
onMounted(async () => {
  try {
    // 先获取学院，学院加载完成后会自动加载对应系
    await loadFaculties()
    // 根据当前系加载专业
    await loadMajors(filters.value.department)
    // 并行获取其他数据
    await Promise.all([loadPendingApplications(), fetchRules()])
  } catch (error) {
    console.error('数据加载失败:', error)
    toastStore.error('数据加载失败，请稍后重试')
  }
})

// 加载待审核申请
const loadPendingApplications = async () => {
  try {
    await applicationsStore.fetchPendingApplications()
  } catch (error) {
    console.error('获取待审核申请失败:', error)
    throw error
  }
}

// 从后端获取系（根据学院ID）
const loadDepartments = async (facultyId = null) => {
  try {
    loadingDepartments.value = true
    let response
    if (facultyId && facultyId !== 'all') {
      // 根据学院ID获取系
      response = await api.getDepartmentsByFaculty(facultyId)
    } else {
      // 获取所有系
      response = await api.getDepartmentsAdmin()
    }
    departments.value = response.departments || []

    // 重置专业选择和列表
    filters.value.major = 'all'
    majors.value = []

    // 如果有系被选中但不在新列表中，重置系选择
    if (
      filters.value.department !== 'all' &&
      !departments.value.some((dept) => dept.id === filters.value.department)
    ) {
      filters.value.department = 'all'
    }
  } catch (error) {
    console.error('获取系列表失败:', error)
    departments.value = []
  } finally {
    loadingDepartments.value = false
  }
}

// 从后端获取所有学院
const loadFaculties = async () => {
  try {
    // 获取所有学院
    const response = await api.getFaculties()
    faculties.value = response.faculties || []

    // 将老师所在的学院设置为默认选中值
    const teacherFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    if (teacherFacultyId) {
      filters.value.faculty = teacherFacultyId
      // 根据默认学院加载系
      await loadDepartments(filters.value.faculty)
    } else {
      // 如果没有默认学院，加载所有系
      await loadDepartments()
    }
  } catch (error) {
    console.error('获取学院列表失败:', error)
    faculties.value = []
  }
}

// 从后端获取专业（根据系ID或学院ID）
const loadMajors = async (departmentId = null) => {
  try {
    loadingMajors.value = true
    let response
    if (departmentId && departmentId !== 'all') {
      // 根据系ID获取专业
      response = await api.getMajorsByDepartment(departmentId)
    } else if (filters.value.faculty && filters.value.faculty !== 'all') {
      // 根据学院ID获取专业
      response = await api.getMajorsAdmin('', filters.value.faculty)
    } else {
      // 获取所有专业
      response = await api.getMajors()
    }
    majors.value = response.majors || []

    // 如果有专业被选中但不在新列表中，重置专业选择
    if (
      filters.value.major !== 'all' &&
      !majors.value.some((major) => major.id === filters.value.major)
    ) {
      filters.value.major = 'all'
    }
  } catch (error) {
    console.error('获取专业列表失败:', error)
    majors.value = []
  } finally {
    loadingMajors.value = false
  }
}

// 从后端获取规则列表
const fetchRules = async () => {
  try {
    // 获取教师所在学院ID
    const teacherFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    // 使用正确的API方法获取规则，传递学院ID
    const response = await api.getRules({ faculty_id: teacherFacultyId })
    availableRules.value = response.rules.filter((rule) => rule.status === 'active')
  } catch (error) {
    console.error('获取规则列表失败:', error)
    availableRules.value = []
  }
}
</script>

<style scoped src="@/assets/styles/pages/teacher/reviews/PendingReview.css"></style>
