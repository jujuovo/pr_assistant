<template>
  <div class="page-content">
    <div class="page-title">
      <span>申请管理</span>
    </div>

    <!-- 搜索区域 - 修改为与用户管理组件相同样式 -->
    <div class="filters">
      <!-- 基本信息筛选 -->
      <div class="filter-group">
        <span class="filter-label">姓名:</span>
        <input
          type="text"
          class="form-control small"
          v-model="filters.studentName"
          placeholder="输入学生姓名"
        />
      </div>
      <div class="filter-group">
        <span class="filter-label">学号:</span>
        <input
          type="text"
          class="form-control small"
          v-model="filters.studentId"
          placeholder="输入学生学号"
        />
      </div>

      <!-- 添加学院筛选 -->
      <div class="filter-group">
        <span class="filter-label">当前学院:</span>
        <select v-model="filters.faculty">
          <option value="all">全部学院</option>
          <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">{{
            faculty.name
          }}</option>
        </select>
      </div>

      <!-- 系和专业筛选 -->
      <div class="filter-group">
        <span class="filter-label">所在系:</span>
        <select v-model="filters.department">
          <option value="all">全部系</option>
          <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{
            dept.name
          }}</option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">专业:</span>
        <select v-model="filters.major">
          <option value="all">全部专业</option>
          <option v-for="major in majors" :key="major.id" :value="major.id">{{
            major.name
          }}</option>
        </select>
      </div>

      <!-- 申请信息筛选 -->
      <div class="filter-group">
        <span class="filter-label">申请类型:</span>
        <select v-model="filters.applicationType">
          <option value="all">全部类型</option>
          <option value="academic">学术专长</option>
          <option value="comprehensive">综合表现</option>
        </select>
      </div>

      <!-- 添加学院规则筛选 -->
      <div class="filter-group">
        <span class="filter-label">规则:</span>
        <select v-model="filters.rule">
          <option value="all">全部规则</option>
          <option v-for="rule in availableRules" :key="rule.id" :value="rule.id">{{
            rule.name
          }}</option>
        </select>
      </div>

      <!-- 审核信息筛选 -->
      <div class="filter-group">
        <span class="filter-label">审核状态:</span>
        <select v-model="filters.status">
          <option value="all">全部状态</option>
          <option value="pending">待审核</option>
          <option value="approved">已通过</option>
          <option value="rejected">未通过</option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">审核人:</span>
        <input
          type="text"
          class="form-control small"
          v-model="filters.reviewedBy"
          placeholder="审核人姓名"
        />
      </div>
      <div class="filter-group checkbox-filter">
        <label>
          <input type="checkbox" v-model="filters.onlyMyReviews" />
          <span>只显示我审核的</span>
        </label>
      </div>

      <!-- 时间筛选 -->
      <div class="filter-group date-range-group">
        <span class="filter-label">申请时间:</span>
        <input type="date" class="form-control small" v-model="filters.startDate" />
        至 <input type="date" class="form-control small" v-model="filters.endDate" />
      </div>
      <div class="filter-group date-range-group">
        <span class="filter-label">审核时间:</span>
        <input type="date" class="form-control small" v-model="filters.reviewedStartDate" />
        至 <input type="date" class="form-control small" v-model="filters.reviewedEndDate" />
      </div>

      <!-- 操作按钮 -->
      <div class="filter-group">
        <button class="btn btn-outline" @click="filterApplications">查询</button>
        <button class="btn btn-outline" @click="resetFilters">清空筛选</button>
      </div>
    </div>

    <!-- 批量操作工具栏 -->
    <div class="batch-actions">
      <button
        class="btn btn-outline"
        @click="batchDelete"
        :disabled="selectedApplications.length === 0"
      >
        <font-awesome-icon :icon="['fas', 'trash']" /> 删除选中
      </button>
    </div>

    <!-- 数据表格 -->
    <div class="card">
      <!-- 加载状态指示器 -->
      <div v-if="isLoading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>
      <div class="table-container">
        <table class="application-table">
          <thead>
            <tr>
              <th><input type="checkbox" v-model="selectAll" @change="toggleSelectAll" /></th>
              <th>学生姓名</th>
              <th>学号</th>
              <th>专业</th>
              <th>申请类型</th>
              <th>规则</th>
              <th>申请时间</th>
              <th>审核时间</th>
              <th>审核人</th>
              <th>自评分数</th>
              <th>核定分数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="application in paginatedApplications"
              :key="application.id"
              class="table-row"
            >
              <td
                ><input type="checkbox" v-model="selectedApplications" :value="application.id"
              /></td>
              <td>{{ application.studentName }}</td>
              <td>{{ application.studentId }}</td>
              <td>{{ getMajorText(application.major) }}</td>
              <td>{{ getTypeText(application.applicationType) }}</td>
              <td>{{ getRuleText(application.ruleId) }}</td>
              <td>{{ formatDate(application.appliedAt) }}</td>
              <td>{{ formatDate(application.reviewedAt) }}</td>
              <td>{{ application.reviewedBy || '-' }}</td>
              <td>{{ application.selfScore }}</td>
              <td>{{
                application.finalScore !== null && application.finalScore !== undefined
                  ? application.finalScore
                  : '-'
              }}</td>
              <td>
                <span :class="`status-badge status-${application.status}`">
                  {{ getStatusText(application.status) }}
                </span>
              </td>
              <td>
                <div class="action-buttons">
                  <button
                    class="btn-outline btn small-btn"
                    @click="viewApplication(application)"
                    title="查看"
                  >
                    <font-awesome-icon :icon="['fas', 'eye']" />
                  </button>
                  <button
                    class="btn-outline btn small-btn"
                    @click="editApplication(application)"
                    title="编辑"
                  >
                    <font-awesome-icon :icon="['fas', 'edit']" />
                  </button>
                  <button
                    class="btn-outline btn small-btn"
                    @click="deleteApplication(application.id)"
                    title="删除"
                  >
                    <font-awesome-icon :icon="['fas', 'trash']" />
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="paginatedApplications.length === 0">
              <td colspan="13" class="no-data">暂无申请数据</td>
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
        <button class="btn-outline btn" :disabled="currentPage === 1" @click="prevPage">
          <font-awesome-icon :icon="['fas', 'chevron-left']" /> 上一页
        </button>
        <button class="btn-outline btn" :disabled="currentPage >= totalPages" @click="nextPage">
          下一页 <font-awesome-icon :icon="['fas', 'chevron-right']" />
        </button>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="editDialogVisible" class="dialog-overlay" @click="closeEditDialog">
      <div class="dialog-content" @click.stop>
        <div class="dialog-header">
          <h3>编辑申请</h3>
          <button class="close-btn" @click="closeEditDialog">
            <font-awesome-icon :icon="['fas', 'times']" />
          </button>
        </div>
        <div class="dialog-body">
          <form @submit.prevent="saveApplication">
            <div class="form-row">
              <div class="form-group">
                <label>学生姓名</label>
                <input type="text" v-model="editForm.studentName" required />
              </div>
              <div class="form-group">
                <label>学号</label>
                <input type="text" v-model="editForm.studentId" required />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>性别</label>
                <select v-model="editForm.gender" required>
                  <option value="">请选择</option>
                  <option value="男">男</option>
                  <option value="女">女</option>
                </select>
              </div>
              <div class="form-group">
                <label>年级</label>
                <input type="text" v-model="editForm.grade" required />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>申请类型</label>
                <select v-model="editForm.applicationType" required>
                  <option value="">请选择</option>
                  <option value="graduation">毕业申请</option>
                  <option value="internship">实习申请</option>
                  <option value="transfer">转学申请</option>
                  <option value="other">其他申请</option>
                </select>
              </div>
              <div class="form-group">
                <label>申请状态</label>
                <select v-model="editForm.status" required>
                  <option value="">请选择</option>
                  <option value="pending">待审核</option>
                  <option value="approved">已通过</option>
                  <option value="rejected">已拒绝</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>申请日期</label>
                <input type="date" v-model="editForm.applicationDate" required />
              </div>
              <div class="form-group">
                <label>审核日期</label>
                <input type="date" v-model="editForm.reviewDate" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group full-width">
                <label>审核意见</label>
                <textarea v-model="editForm.reviewerComments" rows="3"></textarea>
              </div>
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-outline" @click="closeEditDialog">取消</button>
              <button type="submit" class="btn btn-primary">保存</button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 查看详情模态框 -->
    <ApplicationDetailModal
      v-if="viewDetailModalVisible"
      :application="selectedApplication"
      @close="closeViewDetailModal"
      :is-review-mode="false"
    />

    <!-- 审核操作模态框 -->
    <ApplicationDetailModal
      v-if="reviewDetailModalVisible"
      :application="selectedApplication"
      @approve="handleApproveApplication"
      @reject="handleRejectApplication"
      @close="closeReviewDetailModal"
      :is-review-mode="true"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import ApplicationDetailModal from '@/components/common/ApplicationDetailModal.vue'
import { useApplicationsStore } from '@/stores/applications.js'
import { useAuthStore } from '@/stores/auth.js'
import { useToastStore } from '@/stores/toast.js'
import api from '@/services/api.js'

// 初始化store
const applicationsStore = useApplicationsStore()
const authStore = useAuthStore()
const toastStore = useToastStore()
const selectedApplication = ref(null)
const selectAll = ref(false)
const selectedApplications = ref([])
const currentPage = ref(1)
const pageSize = 10
const isLoading = ref(false)

// 学院、系和专业数据
const faculties = ref([])
const departments = ref([])
const majors = ref([])
const availableRules = ref([])
const loadingDepartments = ref(false)
const loadingMajors = ref(false)

// 编辑弹窗相关
const editDialogVisible = ref(false)
const editingApplication = ref(null)
const editForm = ref({
  studentName: '',
  studentId: '',
  gender: '',
  grade: '',
  applicationType: '',
  status: '',
  applicationDate: '',
  reviewDate: '',
  reviewerComments: ''
})

// 模态框显示状态
const viewDetailModalVisible = ref(false)
const reviewDetailModalVisible = ref(false)

const filters = reactive({
  studentName: '',
  studentId: '',
  faculty: 'all',
  department: 'all',
  major: 'all',
  applicationType: 'all',
  rule: 'all',
  status: 'all',
  reviewedBy: '',
  onlyMyReviews: false,
  startDate: '',
  endDate: '',
  reviewedStartDate: '',
  reviewedEndDate: ''
})

// 使用store中的applications数据
const applications = computed(() => applicationsStore.applications)

// 计算属性
const filteredApplications = computed(() => {
  // 获取当前登录用户姓名
  const currentUserName = authStore.user?.name

  let filtered = applications.value.filter((app) => {
    const nameMatch = !filters.studentName || app.studentName.includes(filters.studentName)
    const idMatch = !filters.studentId || app.studentId.includes(filters.studentId)
    const facultyMatch = filters.faculty === 'all' || app.facultyId === filters.faculty
    const departmentMatch = filters.department === 'all' || app.departmentId === filters.department
    const majorMatch = filters.major === 'all' || app.majorId === filters.major
    const typeMatch =
      filters.applicationType === 'all' || app.applicationType === filters.applicationType
    const ruleMatch = filters.rule === 'all' || app.ruleId === filters.rule
    const statusMatch = filters.status === 'all' || app.status === filters.status
    const reviewedByMatch = !filters.reviewedBy || app.reviewedBy?.includes(filters.reviewedBy)
    const onlyMyReviewsMatch =
      !filters.onlyMyReviews || (currentUserName && app.reviewedBy === currentUserName)

    // 申请日期筛选
    let dateMatch = true
    if (filters.startDate) {
      dateMatch = new Date(app.appliedAt) >= new Date(filters.startDate)
    }
    if (dateMatch && filters.endDate) {
      const endDate = new Date(filters.endDate)
      endDate.setHours(23, 59, 59, 999)
      dateMatch = new Date(app.appliedAt) <= endDate
    }

    // 审核日期筛选
    let reviewedDateMatch = true
    if (app.reviewedAt) {
      if (filters.reviewedStartDate) {
        reviewedDateMatch = new Date(app.reviewedAt) >= new Date(filters.reviewedStartDate)
      }
      if (reviewedDateMatch && filters.reviewedEndDate) {
        const reviewedEndDate = new Date(filters.reviewedEndDate)
        reviewedEndDate.setHours(23, 59, 59, 999)
        reviewedDateMatch = new Date(app.reviewedAt) <= reviewedEndDate
      }
    } else if (filters.reviewedStartDate || filters.reviewedEndDate) {
      reviewedDateMatch = false
    }

    return (
      nameMatch &&
      idMatch &&
      facultyMatch &&
      departmentMatch &&
      majorMatch &&
      typeMatch &&
      ruleMatch &&
      statusMatch &&
      reviewedByMatch &&
      onlyMyReviewsMatch &&
      dateMatch &&
      reviewedDateMatch
    )
  })

  // 按申请时间倒序排序
  filtered.sort((a, b) => {
    const dateA = new Date(a.appliedAt || 0)
    const dateB = new Date(b.appliedAt || 0)
    return dateB - dateA
  })

  return filtered
})

// 监听筛选结果变化，确保当前页码有效
watch(
  filteredApplications,
  () => {
    if (currentPage.value > totalPages.value && totalPages.value > 0) {
      currentPage.value = totalPages.value
    } else if (totalPages.value === 0) {
      currentPage.value = 1
    }
  },
  { deep: true }
)

const totalApplications = computed(() => filteredApplications.value.length)
const totalPages = computed(() => Math.ceil(totalApplications.value / pageSize))
const startIndex = computed(() => (currentPage.value - 1) * pageSize)
const endIndex = computed(() => Math.min(startIndex.value + pageSize, totalApplications.value))

const paginatedApplications = computed(() => {
  return filteredApplications.value.slice(startIndex.value, endIndex.value)
})

// 方法
const getTypeText = (type) => {
  return type === 'academic' ? '学术专长' : '综合表现'
}

const getDepartmentText = (department) => {
  const departments = { cs: '计算机科学系', se: '软件工程系', ai: '人工智能系' }
  return departments[department] || department
}

const getMajorText = (major) => {
  const majors = { cs: '计算机科学与技术', se: '软件工程', ai: '人工智能' }
  return majors[major] || major
}

const getStatusText = (status) => {
  const statusText = {
    pending: '待审核',
    approved: '已通过',
    rejected: '未通过'
  }
  return statusText[status] || status
}

// 根据规则ID获取规则名称
const getRuleText = (ruleId) => {
  if (!ruleId) return '-'
  // 使用类型转换确保ID匹配（处理字符串和数字类型不匹配的问题）
  const rule = availableRules.value.find((r) => r.id == ruleId)
  if (rule) {
    // 如果规则已禁用，添加提示信息
    return rule.status === 'disabled' ? `${rule.name} (当前已禁用)` : rule.name
  }
  return ruleId
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString('zh-CN')
}

const getApplicationTypeText = (type) => {
  const typeMap = {
    graduation: '毕业申请',
    internship: '实习申请',
    transfer: '转学申请',
    other: '其他申请'
  }
  return typeMap[type] || '未知类型'
}

// 监听筛选条件变化，自动更新列表
watch(
  () => [
    filters.studentName,
    filters.studentId,
    filters.faculty,
    filters.department,
    filters.major,
    filters.applicationType,
    filters.rule,
    filters.status,
    filters.reviewedBy,
    filters.onlyMyReviews,
    filters.startDate,
    filters.endDate,
    filters.reviewedStartDate,
    filters.reviewedEndDate
  ],
  () => {
    currentPage.value = 1
  },
  { deep: true }
)

const resetFilters = () => {
  // 保存当前学院选择（如果是管理员）
  const currentFaculty = filters.faculty
  Object.assign(filters, {
    studentName: '',
    studentId: '',
    faculty: currentFaculty, // 保持当前学院选择不变
    department: 'all',
    major: 'all',
    applicationType: 'all',
    rule: 'all',
    status: 'all',
    reviewedBy: '',
    onlyMyReviews: false,
    startDate: '',
    endDate: '',
    reviewedStartDate: '',
    reviewedEndDate: ''
  })
  currentPage.value = 1
}

// 主动应用筛选
const filterApplications = () => {
  currentPage.value = 1
}

const toggleSelectAll = () => {
  if (selectAll.value) {
    selectedApplications.value = filteredApplications.value.map((app) => app.id)
  } else {
    selectedApplications.value = []
  }
}

const batchDelete = async () => {
  if (confirm(`确定要删除选中的 ${selectedApplications.value.length} 个申请吗？`)) {
    isLoading.value = true
    let successCount = 0
    let failCount = 0

    try {
      // 循环删除每个选中的申请
      for (const id of selectedApplications.value) {
        const success = await applicationsStore.deleteApplication(id)
        if (success) {
          successCount++
        } else {
          failCount++
        }
      }

      // 清空选中列表
      selectedApplications.value = []
      selectAll.value = false

      // 显示结果
      toastStore.success(`批量删除完成：成功 ${successCount} 条，失败 ${failCount} 条`)
    } catch (error) {
      console.error('批量删除失败:', error)
      toastStore.error('批量删除过程中发生错误，请重试')
    } finally {
      isLoading.value = false
    }
  }
}

const viewApplication = (application) => {
  selectedApplication.value = application
  viewDetailModalVisible.value = true
}

const closeViewDetailModal = () => {
  viewDetailModalVisible.value = false
  selectedApplication.value = null
}

const handleApproveApplication = async (reviewData) => {
  try {
    isLoading.value = true
    const success = await applicationsStore.updateApplicationStatus(
      reviewData.applicationId,
      'approved',
      reviewData.approveComment,
      reviewData.finalScore,
      authStore.userName
    )
    if (success) {
      toastStore.success('审核通过成功')
      reviewDetailModalVisible.value = false
      selectedApplication.value = null
    } else {
      toastStore.error('审核通过失败')
    }
  } catch (error) {
    console.error('审核通过失败:', error)
    toastStore.error('审核通过失败，请重试')
  } finally {
    isLoading.value = false
  }
}

const handleRejectApplication = async (reviewData) => {
  try {
    isLoading.value = true
    const success = await applicationsStore.updateApplicationStatus(
      reviewData.applicationId,
      'rejected',
      reviewData.rejectComment,
      0,
      authStore.userName
    )
    if (success) {
      toastStore.success('驳回成功')
      reviewDetailModalVisible.value = false
      selectedApplication.value = null
    } else {
      toastStore.error('驳回失败')
    }
  } catch (error) {
    console.error('驳回失败:', error)
    toastStore.error('驳回失败，请重试')
  } finally {
    isLoading.value = false
  }
}

const editApplication = (application) => {
  selectedApplication.value = application
  reviewDetailModalVisible.value = true
}

const deleteApplication = async (applicationId) => {
  if (confirm('确定要删除这条申请记录吗？')) {
    try {
      const success = await applicationsStore.deleteApplication(applicationId)
      if (success) {
        toastStore.success('删除成功')
      } else {
        toastStore.error('删除失败')
      }
    } catch (error) {
      console.error('删除申请失败:', error)
      toastStore.error('删除失败，请重试')
    }
  }
}

const closeDetailModal = () => {
  selectedApplication.value = null
}

const closeReviewDetailModal = () => {
  reviewDetailModalVisible.value = false
  selectedApplication.value = null
}

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

// 加载学院数据
const loadFaculties = async () => {
  try {
    // 使用管理员版本的API获取学院列表
    const response = await api.getFacultiesAdmin()
    // 从response.faculties字段提取数组
    faculties.value = response.faculties || []

    // 将管理员所在的学院设置为默认选中值
    const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    if (adminFacultyId) {
      filters.faculty = adminFacultyId
      // 根据默认学院加载系
      await loadDepartments(adminFacultyId)
    } else {
      // 如果没有默认学院，加载所有系
      await loadDepartments()
    }
  } catch (error) {
    console.error('获取学院列表失败:', error)
    faculties.value = []
  }
}

// 加载系数据
const loadDepartments = async (facultyId = '') => {
  try {
    loadingDepartments.value = true
    // 强制使用管理员所在的学院ID，确保只显示当前学院的系
    const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    if (adminFacultyId && adminFacultyId !== 'all') {
      // 根据管理员学院ID获取系
      const response = await api.getDepartmentsAdmin(adminFacultyId)
      departments.value = response.departments || []
    } else if (facultyId && facultyId !== 'all') {
      // 作为备选，使用传入的学院ID获取系
      const response = await api.getDepartmentsAdmin(facultyId)
      departments.value = response.departments || []
    } else {
      // 获取所有系（仅当管理员没有学院ID时）
      const response = await api.getDepartmentsAdmin()
      departments.value = response.departments || []
    }

    // 重置专业选择和列表
    filters.major = 'all'

    // 如果有系被选中但不在新列表中，重置系选择
    if (
      filters.department !== 'all' &&
      !departments.value.some((dept) => dept.id === filters.department)
    ) {
      filters.department = 'all'
    }

    // 根据当前选择的系加载专业
    if (filters.department !== 'all') {
      await loadMajors(filters.department)
    } else {
      // 加载当前学院下所有系的专业
      await loadMajors()
    }
  } catch (error) {
    console.error('获取系列表失败:', error)
    departments.value = []
    majors.value = []
  } finally {
    loadingDepartments.value = false
  }
}

// 加载专业数据
const loadMajors = async (departmentId = '') => {
  try {
    loadingMajors.value = true
    // 强制使用管理员所在的学院ID，确保只显示当前学院的专业
    const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId

    // 如果指定了系ID，获取该系下的专业
    if (departmentId && departmentId !== 'all') {
      const response = await api.getMajorsAdmin(departmentId)
      majors.value = response.majors || []
    } else if (adminFacultyId) {
      // 如果没有指定系ID，但有管理员学院ID，获取该学院下所有系的专业
      // 遍历当前系列表，获取所有系的专业
      const allDepartmentIds = departments.value.map((dept) => dept.id)
      const promises = allDepartmentIds.map((deptId) =>
        api.getMajorsAdmin(deptId).catch(() => ({ majors: [] }))
      )
      const results = await Promise.all(promises)
      // 合并所有专业数据
      const allMajors = results.flatMap((result) => result.majors || [])
      // 去重
      const uniqueMajors = Array.from(new Map(allMajors.map((major) => [major.id, major])).values())
      majors.value = uniqueMajors
    } else {
      // 获取所有专业（仅当管理员没有学院ID时）
      const response = await api.getMajorsAdmin()
      majors.value = response.majors || []
    }

    // 如果有专业被选中但不在新列表中，重置专业选择
    if (filters.major !== 'all' && !majors.value.some((major) => major.id === filters.major)) {
      filters.major = 'all'
    }
  } catch (error) {
    console.error('获取专业列表失败:', error)
    majors.value = []
  } finally {
    loadingMajors.value = false
  }
}

// 加载规则数据
const loadRules = async () => {
  try {
    // 获取管理员学院ID
    const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    // 根据api.js中的定义，getRules需要传递filters参数（可选）
    // 只有当adminFacultyId存在时，才传递faculty_id参数筛选当前学院的规则
    const filters = adminFacultyId ? { faculty_id: adminFacultyId } : {}
    const response = await api.getRules(filters)
    // 检查并转换数据格式
    if (Array.isArray(response)) {
      availableRules.value = response
    } else if (response && Array.isArray(response.rules)) {
      // 从response.rules字段提取数组
      availableRules.value = response.rules
    } else if (response && response.data && Array.isArray(response.data)) {
      availableRules.value = response.data
    } else {
      availableRules.value = []
    }

    // 如果选中的规则不在当前规则列表中，重置选择
    if (filters.rule && !availableRules.value.some((rule) => rule.id === filters.rule)) {
      filters.rule = 'all'
    }
  } catch (error) {
    console.error('获取规则列表失败:', error)
    availableRules.value = []
  }
}

// 加载申请数据
const loadApplications = async () => {
  isLoading.value = true
  try {
    await applicationsStore.fetchApplications()
    // 数据加载完成后，确保当前页码有效
    if (currentPage.value > totalPages.value && totalPages.value > 0) {
      currentPage.value = totalPages.value
    } else if (totalPages.value === 0) {
      currentPage.value = 1
    }
  } catch (error) {
    console.error('加载申请数据失败:', error)
  } finally {
    isLoading.value = false
  }
}

// 生命周期
onMounted(async () => {
  try {
    // 先加载学院数据，以便后续根据学院加载系和专业
    await loadFaculties()
    // 加载其他数据
    await Promise.all([loadApplications(), loadRules()])
  } catch (error) {
    console.error('数据加载失败:', error)
  }
})

// 监听学院变化，重新加载系数据
watch(
  () => filters.faculty,
  async (newFacultyId) => {
    const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    if ((newFacultyId && newFacultyId !== 'all') || (!adminFacultyId && newFacultyId === 'all')) {
      // 如果选择了特定学院，或超级管理员选择了全部学院，加载对应的系和专业
      await loadDepartments(newFacultyId)
      // 加载对应学院下的所有专业
      await loadMajors()
    } else {
      departments.value = []
      majors.value = []
    }
    // 重置系和专业筛选条件
    filters.department = 'all'
    filters.major = 'all'
    // 重新加载规则和应用数据
    currentPage.value = 1
    await Promise.all([loadRules(), loadApplications()])
  }
)

// 监听系变化，重新加载专业数据
watch(
  () => filters.department,
  async (newDepartmentId) => {
    if (newDepartmentId && newDepartmentId !== 'all') {
      await loadMajors(newDepartmentId)
    } else {
      // 如果没有选择系，但有学院选择，加载该学院下所有专业
      if (filters.faculty && filters.faculty !== 'all') {
        await loadMajors()
      } else {
        majors.value = []
      }
    }
    // 重置专业筛选条件
    filters.major = 'all'
    // 重新加载应用数据
    currentPage.value = 1
    await loadApplications()
  }
)

// 监听专业变化，重新加载应用数据
watch(
  () => filters.major,
  async () => {
    currentPage.value = 1
    await loadApplications()
  }
)
</script>

<style scoped src="@/assets/styles/pages/admin/applications/ApplicationManagement.css"></style>
