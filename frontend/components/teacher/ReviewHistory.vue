<template>
  <div class="page-content">
    <div class="page-title">
      <span>审核记录</span>
    </div>
    <!-- 筛选区域 -->
    <div class="filters">
      <div class="filter-group">
        <span class="filter-label">姓名:</span>
        <input type="text" class="form-control small" v-model="filters.studentName" placeholder="输入学生姓名"
          @input="filterApplications">
      </div>
      <div class="filter-group">
        <span class="filter-label">学号:</span>
        <input type="text" class="form-control small" v-model="filters.studentId" placeholder="输入学生学号"
          @input="filterApplications">
      </div>
      <div class="filter-group">
        <span class="filter-label">学院:</span>
        <select v-model="filters.faculty" @change="handleFacultyChange" :disabled="authStore.user?.faculty_id||authStore.user?.facultyId">
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
            {{ rule.name }} {{ rule.status === 'disabled' ? '(当前已禁用)' : '' }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">审核状态:</span>
        <select v-model="filters.status" @change="filterApplications">
          <option value="all">全部</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">审核人:</span>
        <input type="text" class="form-control small" v-model="filters.reviewedBy" placeholder="输入审核人姓名"
          @input="filterApplications">
      </div>
      <div class="filter-group checkbox-filter">
        <label>
          <input type="checkbox" v-model="filters.myReviewsOnly" @change="filterApplications">
          <span>只显示我审核的</span>
        </label>
      </div>
      <!-- 申请时间和审核时间放在第二行 -->
      <div class="filter-group date-range-group">
        <span class="filter-label">申请时间:</span>
        <input type="date" class="form-control small" v-model="filters.startDate" @change="filterApplications">
        至 <input type="date" class="form-control small" v-model="filters.endDate" @change="filterApplications">
      </div>
      <div class="filter-group date-range-group">
        <span class="filter-label">审核时间:</span>
        <input type="date" class="form-control small" v-model="filters.reviewedStartDate" @change="filterApplications">
        至 <input type="date" class="form-control small" v-model="filters.reviewedEndDate" @change="filterApplications">
      </div>
      <div class="filter-group">
        <button class="btn btn-outline" @click="clearFilters">清空筛选</button>
      </div>
    </div>
    <!-- 审核记录表格 -->
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
              <th>专业</th>
              <th>申请类型</th>
              <th>规则</th>
              <th>申请时间</th>
              <th>审核时间</th>
              <th>自评分数</th>
              <th>核定分数</th>
              <th>审核状态</th>
              <th class="action-column">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="application in paginatedApplications" :key="application.id">
              <td>{{ application.studentName }}</td>
              <td>{{ application.studentId }}</td>
              <td>{{ getMajorText(application.major) }}</td>
              <td>{{ getTypeText(application.applicationType) }}</td>
              <td>{{ getRuleText(application.ruleId) }}</td>
              <td>{{ formatDate(application.appliedAt) }}</td>
              <td>{{ formatDate(application.reviewedAt) }}</td>
              <td>{{ application.selfScore }}</td>
              <td>{{ application.finalScore ?? '-' }}</td>
              <td>
                <span :class="`status-badge status-${application.status}`">
                  {{ getStatusText(application.status) }}
                </span>
              </td>
              <td class="action-column">
                <div class="action-buttons">
                  <button class="btn btn-outline small-btn" @click="viewApplication(application)" title="查看">
                    <font-awesome-icon :icon="['fas', 'eye']" />
                  </button>
                  <button class="btn btn-outline small-btn" @click="editApplication(application)" title="编辑">
                    <font-awesome-icon :icon="['fas', 'edit']" />
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="paginatedApplications.length === 0">
              <td colspan="11" class="no-data">暂无审核记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <!-- 分页控件 -->
    <div class="pagination">
      <div class="pagination-info">显示 {{ startIndex + 1 }}-{{ endIndex }} 条，共 {{ totalApplications }} 条记录</div>
      <div class="pagination-controls">
        <button class="btn btn-outline" :disabled="pagination.currentPage === 1" @click="prevPage">
          <font-awesome-icon :icon="['fas', 'chevron-left']" /> 上一页
        </button>
        <button class="btn btn-outline" :disabled="pagination.currentPage >= totalPages" @click="nextPage">
          下一页 <font-awesome-icon :icon="['fas', 'chevron-right']" />
        </button>
      </div>
    </div>
    <!-- 查看申请详情模态框 -->
    <ApplicationDetailModal v-if="selectedApplication" :application="selectedApplication" @close="closeDetailModal"
      :is-review-mode="false" />
    <!-- 编辑申请详情模态框 -->
    <ApplicationDetailModal v-if="editingApplication" :application="editingApplication" @close="closeEditDialog"
      @approve="handleApproveApplication" @reject="handleRejectApplication" :is-review-mode="true" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ApplicationDetailModal from '../common/ApplicationDetailModal.vue'
import { useApplicationsStore } from '../../stores/applications'
import { useAuthStore } from '../../stores/auth'
import { useToastStore } from '../../stores/toast'
import api from '../../utils/api'

const applicationsStore = useApplicationsStore()
const authStore = useAuthStore()
const toastStore = useToastStore()
const selectedApplication = ref(null)

// 编辑弹窗相关
const editingApplication = ref(null)

// 筛选条件
const filters = ref({
  faculty: 'all',
  department: 'all',
  major: 'all',
  type: 'all',
  rule: 'all',
  status: 'all',
  startDate: '',
  endDate: '',
  reviewedStartDate: '',
  reviewedEndDate: '',
  reviewedBy: '',
  myReviewsOnly: false,
  studentId: '',
  studentName: ''
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

// 加载状态
const loading = computed(() => applicationsStore.loading)

// 筛选和分页处理后的申请数据
const paginatedApplications = computed(() => {
  // 获取当前登录教师姓名
  const currentTeacherName = authStore.user?.name
  // 先筛选
  let filtered = applicationsStore.filterApplications({
    faculty: filters.value.faculty !== 'all' ? filters.value.faculty : undefined,
    department: filters.value.department !== 'all' ? filters.value.department : undefined,
    major: filters.value.major !== 'all' ? filters.value.major : undefined,
    type: filters.value.type !== 'all' ? filters.value.type : undefined,
    rule: filters.value.rule !== 'all' ? filters.value.rule : undefined,
    startDate: filters.value.startDate,
    endDate: filters.value.endDate,
    reviewedBy: filters.value.reviewedBy || undefined,
    myReviewsOnly: filters.value.myReviewsOnly ? currentTeacherName : undefined,
    studentId: filters.value.studentId || undefined,
    studentName: filters.value.studentName || undefined
  })

  // 只保留已审核的
  filtered = filtered.filter(app => app.status === 'approved' || app.status === 'rejected')

  // 如果有状态筛选
  if (filters.value.status !== 'all') {
    filtered = filtered.filter(app => app.status === filters.value.status)
  }
  // 如果有审核时间筛选
  if (filters.value.reviewedStartDate) {
    const startDate = new Date(filters.value.reviewedStartDate)
    filtered = filtered.filter(app => {
      if (!app.reviewedAt) return false
      return new Date(app.reviewedAt) >= startDate
    })
  }
  if (filters.value.reviewedEndDate) {
    const endDate = new Date(filters.value.reviewedEndDate)
    endDate.setHours(23, 59, 59, 999) // 设置为当天结束时间
    filtered = filtered.filter(app => {
      if (!app.reviewedAt) return false
      return new Date(app.reviewedAt) <= endDate
    })
  }

  // 按审核时间倒序排序
  filtered.sort((a, b) => {
    const dateA = new Date(a.reviewedAt || 0)
    const dateB = new Date(b.reviewedAt || 0)
    return dateB - dateA
  })

  // 再分页
  const startIndex = (pagination.value.currentPage - 1) * pagination.value.pageSize
  const endIndex = startIndex + pagination.value.pageSize
  return filtered.slice(startIndex, endIndex)
})

// 总记录数
const totalApplications = computed(() => {
  // 获取当前登录教师姓名
  const currentTeacherName = authStore.user?.name

  let filtered = applicationsStore.filterApplications({
    faculty: filters.value.faculty !== 'all' ? filters.value.faculty : undefined,
    department: filters.value.department !== 'all' ? filters.value.department : undefined,
    major: filters.value.major !== 'all' ? filters.value.major : undefined,
    type: filters.value.type !== 'all' ? filters.value.type : undefined,
    rule: filters.value.rule !== 'all' ? filters.value.rule : undefined,
    startDate: filters.value.startDate,
    endDate: filters.value.endDate,
    reviewedBy: filters.value.reviewedBy || undefined,
    myReviewsOnly: filters.value.myReviewsOnly ? currentTeacherName : undefined,
    studentId: filters.value.studentId || undefined,
    studentName: filters.value.studentName || undefined
  })

  filtered = filtered.filter(app => app.status === 'approved' || app.status === 'rejected')

  if (filters.value.status !== 'all') {
    filtered = filtered.filter(app => app.status === filters.value.status)
  }

  // 如果有审核时间筛选
  if (filters.value.reviewedStartDate) {
    const startDate = new Date(filters.value.reviewedStartDate)
    filtered = filtered.filter(app => {
      if (!app.reviewedAt) return false
      return new Date(app.reviewedAt) >= startDate
    })
  }
  if (filters.value.reviewedEndDate) {
    const endDate = new Date(filters.value.reviewedEndDate)
    endDate.setHours(23, 59, 59, 999) // 设置为当天结束时间
    filtered = filtered.filter(app => {
      if (!app.reviewedAt) return false
      return new Date(app.reviewedAt) <= endDate
    })
  }
  return filtered.length
})

const totalPages = computed(() => Math.ceil(totalApplications.value / pagination.value.pageSize))
const startIndex = computed(() => (pagination.value.currentPage - 1) * pagination.value.pageSize)
const endIndex = computed(() => Math.min(startIndex.value + pagination.value.pageSize, totalApplications.value))

const getMajorText = (major) => {
  return majors[major] || major
}

const getTypeText = (type) => {
  return type === 'academic' ? '学术专长' : '综合表现'
}

const getStatusText = (status) => {
  const statusText = {
    approved: '已通过',
    rejected: '已驳回'
  }
  return statusText[status] || status
}

// 根据规则ID获取规则名称
const getRuleText = (ruleId) => {
  if (!ruleId) return '-'
  // 使用类型转换确保ID匹配（处理字符串和数字类型不匹配的问题）
  const rule = availableRules.value.find(r => r.id == ruleId)
  if (rule) {
    // 如果规则已禁用，添加提示信息
    return rule.status === 'disabled' ? `${rule.name} (当前已禁用)` : rule.name
  }
  return ruleId
}

// 格式化日期
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
    status: 'all',
    startDate: '',
    endDate: '',
    reviewedStartDate: '',
    reviewedEndDate: '',
    reviewedBy: '',
    myReviewsOnly: false,
    studentId: '',
    studentName: ''
  }
  // 重置到第一页
  pagination.value.currentPage = 1
  // 重新加载所有数据
  await Promise.all([
    loadDepartments(filters.value.faculty), // 根据当前学院加载系
    loadMajors(filters.value.department), // 根据当前系加载专业
    applicationsStore.fetchApplications()
  ])
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

const viewApplication = async (application) => {
  // 从store获取完整的申请详情
  selectedApplication.value = await applicationsStore.getApplicationById(application.id) || application
}

const closeDetailModal = () => {
  selectedApplication.value = null
}

// 编辑功能方法
const editApplication = async (application) => {
  // 从store获取完整的申请详情
  editingApplication.value = await applicationsStore.getApplicationById(application.id) || application
}

const closeEditDialog = () => {
  editingApplication.value = null
}

// 审核操作处理
const handleApproveApplication = async (approveData) => {
  try {
    const { applicationId, finalScore, approveComment } = approveData
    const success = await applicationsStore.approveApplication(applicationId, finalScore, approveComment, authStore.userName)
    if (success) {
      toastStore.success('审核通过成功')
      closeEditDialog()
    } else {
      toastStore.error('审核通过失败')
    }
  } catch (error) {
    console.error('审核通过失败:', error)
    toastStore.error('审核通过失败，请重试')
  }
}

const handleRejectApplication = async (rejectData) => {
  try {
    const { applicationId, rejectComment } = rejectData
    const success = await applicationsStore.rejectApplication(applicationId, rejectComment, authStore.userName)
    if (success) {
      toastStore.success('驳回成功')
      closeEditDialog()
    } else {
      toastStore.error('驳回失败')
    }
  } catch (error) {
    console.error('驳回失败:', error)
    toastStore.error('驳回失败，请重试')
  }
}

// 生命周期
onMounted(async () => {
  try {
    // 先获取学院，学院加载完成后会自动加载对应系
    await loadFaculties()
    // 根据当前系加载专业
    await loadMajors(filters.value.department)
    // 并行获取其他数据
    await Promise.all([
      loadApplications(),
      fetchRules()
    ])
  } catch (error) {
    console.error('数据加载失败:', error)
    toastStore.error('数据加载失败，请稍后重试')
  }
})

// 加载已审核申请
const loadApplications = async () => {
  try {
    await applicationsStore.fetchApplications()
  } catch (error) {
    console.error('获取已审核申请失败:', error)
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
    if (filters.value.department !== 'all' && !departments.value.some(dept => dept.id === filters.value.department)) {
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
    // 如果都失败，使用默认值
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
    if (filters.value.major !== 'all' && !majors.value.some(major => major.id === filters.value.major)) {
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
    availableRules.value = response.rules
  } catch (error) {
    console.error('获取规则列表失败:', error)
    availableRules.value = []
  }
}
</script>

<style scoped>
/* 引入共享样式 */
@import '../common/shared-styles.css';
</style>