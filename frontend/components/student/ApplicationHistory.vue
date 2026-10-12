<template>
  <div class="page-content">
    <div class="page-title">
      <span>申请记录</span>
      <div class="page-title-actions">
        <button class="btn btn-outline" @click="refreshData" :disabled="loading" :class="{ 'refreshing': loading }">
          <font-awesome-icon :icon="['fas', 'sync']" :spin="loading" />
          {{ loading ? '加载中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <!-- 高级筛选区域 -->
    <div class="filters">

      <div class="filter-group">
        <span class="filter-label">申请类型：</span>
        <select v-model="filters.type" class="form-control">
          <option value="all">全部类型</option>
          <option value="academic">学术专长</option>
          <option value="comprehensive">综合表现</option>
        </select>
      </div>

      <div class="filter-group" style="flex: 1; min-width: 200px;">
        <span class="filter-label">项目名称：</span>
        <input type="text" v-model="filters.searchQuery" class="form-control" style="width: 100%;"
          placeholder="输入项目名称关键词" />
      </div>

      <div class="filter-group">
        <span class="filter-label">规则：</span>
        <select v-model="filters.rule" class="form-control">
          <option value="all">全部规则</option>
          <option v-for="rule in availableRules" :key="rule.id" :value="rule.id">
            {{ rule.name }}
          </option>
        </select>
      </div>


      <div class="filter-group">
        <span class="filter-label">时间范围：</span>
        <div style="display: flex; gap: 8px; align-items: center;">
          <input type="date" v-model="filters.dateRange.start" class="form-control" style="width: 140px;" />
          <span>至</span>
          <input type="date" v-model="filters.dateRange.end" class="form-control" style="width: 140px;" />
        </div>
      </div>

      <div class="filter-group">
        <span class="filter-label">状态筛选：</span>
        <select v-model="filters.status" class="form-control">
          <option value="all">全部状态</option>
          <option value="draft">草稿</option>
          <option value="pending">待审核</option>
          <option value="approved">已通过</option>
          <option value="rejected">已拒绝</option>
        </select>
      </div>

      <div class="filter-group">
        <button class="btn btn-outline" @click="clearFilters">清空筛选</button>
      </div>
    </div>
    <!-- 申请列表 -->
    <div class="card">
      <!-- 加载遮罩 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">正在加载中...</div>
      </div>
      <div v-if="paginatedApplications.length === 0">
        <div style="font-size: 16px; color: #333; text-align: center; color: #999;">暂无申请记录</div>
      </div>
      <div v-else class="table-container" :class="{ 'content-loaded': !loading }">
        <table class="application-table">
          <thead>
            <tr>
              <th @click="sortBy('applicationType')" class="sortable">
                申请类型 <font-awesome-icon :icon="getSortIcon('applicationType')" />
              </th>
              <th @click="sortBy('projectName')" class="sortable">
                项目名称 <font-awesome-icon :icon="getSortIcon('projectName')" />
              </th>
              <th @click="sortBy('ruleId')" class="sortable">
                规则 <font-awesome-icon :icon="getSortIcon('ruleId')" />
              </th>
              <th @click="sortBy('appliedAt')" class="sortable">
                申请时间 <font-awesome-icon :icon="getSortIcon('appliedAt')" />
              </th>
              <th @click="sortBy('selfScore')" class="sortable">
                自评分数 <font-awesome-icon :icon="getSortIcon('selfScore')" />
              </th>
              <th @click="sortBy('finalScore')" class="sortable">
                核定分数 <font-awesome-icon :icon="getSortIcon('finalScore')" />
              </th>
              <th @click="sortBy('status')" class="sortable">
                状态 <font-awesome-icon :icon="getSortIcon('status')" />
              </th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="application in paginatedApplications" :key="application.id">
              <td>{{ getApplicationTypeText(application.applicationType || application.type) }}</td>
              <td style="white-space: normal; max-width: 200px; word-break: break-word;">{{ application.eventName ||
                application.projectName || '未命名' }}</td>
              <td>{{ getRuleName(application.ruleId) }}</td>
              <td>{{ formatDate(application.appliedAt || application.createdAt) }}</td>
              <td>{{ application.selfScore || '-' }}</td>
              <td>{{ application.finalScore ?? '-' }}</td>
              <td>
                <span :class="['status-badge', getStatusClass(application.status)]">
                  {{ getStatusText(application.status) }}
                </span>
              </td>
              <td>
                <div class="action-buttons">
                  <button class="btn btn-outline small-btn btn-view" @click="viewApplicationDetails(application)"
                    title="查看详情">
                    <font-awesome-icon :icon="['fas', 'eye']" />
                  </button>
                  <button v-if="application.status === 'draft'" class="btn btn-outline small-btn btn-edit"
                    @click="editApplication(application)" title="编辑草稿">
                    <font-awesome-icon :icon="['fas', 'edit']" />
                  </button>
                  <button v-if="application.status === 'draft' || application.status === 'pending'"
                    class="btn btn-outline small-btn btn-delete" @click="deleteApplication(application)" title="删除申请">
                    <font-awesome-icon :icon="['fas', 'trash']" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <!-- 分页控件 -->
    <div class="pagination">
      <div class="pagination-info">显示 {{ startItemIndex }}-{{ endItemIndex }} 条，共 {{ totalItems }} 条记录</div>
      <div class="pagination-controls">
        <button class="btn btn-outline" :disabled="currentPage === 1" @click="currentPage--">
          <font-awesome-icon :icon="['fas', 'chevron-left']" /> 上一页
        </button>
        <button class="btn btn-outline" :disabled="currentPage >= totalPages" @click="currentPage++">
          下一页 <font-awesome-icon :icon="['fas', 'chevron-right']" />
        </button>
      </div>
    </div>
    <!-- 详情模态框 -->
    <Teleport to="body">
      <ApplicationDetailModal v-if="selectedApplication" :application="selectedApplication"
        @close="selectedApplication = null" />
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useApplicationsStore } from '../../stores/applications'
import { useToastStore } from '../../stores/toast'
import ApplicationDetailModal from '../common/ApplicationDetailModal.vue'
import api from '../../utils/api'

// 定义事件，用于通知父组件切换页面和编辑申请
const emit = defineEmits(['switch-page', 'edit-application'])

const authStore = useAuthStore()
const applicationsStore = useApplicationsStore()
const toastStore = useToastStore()

// 筛选条件
const filters = ref({
  status: 'all',
  type: 'all',
  rule: 'all',
  searchQuery: '',
  dateRange: {
    start: '',
    end: ''
  }
})

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const sortField = ref('appliedAt')
const sortOrder = ref('desc')
const selectedApplication = ref(null)

// 规则列表
const availableRules = ref([])

// 从后端获取规则列表
const fetchRules = async () => {
  try {
    // 获取学生所在学院ID
    const studentFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    // 使用正确的API方法获取规则，传递学院ID
    const response = await api.getRules({ faculty_id: studentFacultyId })
    availableRules.value = response.rules.filter(rule => rule.status === 'active')
  } catch (error) {
    console.error('获取规则列表失败:', error)
    availableRules.value = []
  }
}

// 加载状态
const loading = computed(() => applicationsStore.loading)

// 根据筛选条件获取当前用户的申请列表
const filteredApplications = computed(() => {
  let applications = applicationsStore.applications.filter(
    app => app.studentId === authStore.user?.studentId || app.name === authStore.userName
  )

  // 筛选状态
  if (filters.value.status !== 'all') {
    applications = applications.filter(app => app.status === filters.value.status)
  }

  // 筛选类型
  if (filters.value.type !== 'all') {
    applications = applications.filter(app =>
      app.applicationType === filters.value.type || app.type === filters.value.type
    )
  }

  // 筛选规则
  if (filters.value.rule !== 'all') {
    applications = applications.filter(app => app.ruleId === filters.value.rule)
  }

  // 搜索项目名称
  if (filters.value.searchQuery.trim()) {
    const query = filters.value.searchQuery.toLowerCase().trim()
    applications = applications.filter(app =>
      (app.projectName && app.projectName.toLowerCase().includes(query)) ||
      (app.eventName && app.eventName.toLowerCase().includes(query))
    )
  }

  // 筛选日期范围
  if (filters.value.dateRange.start) {
    const startDate = new Date(filters.value.dateRange.start)
    startDate.setHours(0, 0, 0, 0)
    applications = applications.filter(app => {
      const appDate = app.appliedAt || app.createdAt
      if (!appDate) return false

      // 处理时区问题
      const date = new Date(appDate)
      const hasTimezone = /(Z|[+-]\d{2}:\d{2})$/.test(appDate)
      if (!hasTimezone) {
        // 如果日期字符串没有包含时区信息，假设它是UTC时间
        date.setTime(date.getTime() + date.getTimezoneOffset() * 60 * 1000)
      }

      return date >= startDate
    })
  }

  if (filters.value.dateRange.end) {
    const endDate = new Date(filters.value.dateRange.end)
    endDate.setHours(23, 59, 59, 999)
    applications = applications.filter(app => {
      const appDate = app.appliedAt || app.createdAt
      if (!appDate) return false

      // 处理时区问题
      const date = new Date(appDate)
      const hasTimezone = /(Z|[+-]\d{2}:\d{2})$/.test(appDate)
      if (!hasTimezone) {
        // 如果日期字符串没有包含时区信息，假设它是UTC时间
        date.setTime(date.getTime() + date.getTimezoneOffset() * 60 * 1000)
      }

      return date <= endDate
    })
  }

  // 排序
  applications.sort((a, b) => {
    let aVal = a[sortField.value]
    let bVal = b[sortField.value]

    // 处理日期类型
    if (sortField.value === 'appliedAt' || sortField.value === 'createdAt') {
      if (aVal) {
        const aDate = new Date(aVal)
        const hasTimezoneA = /(Z|[+-]\d{2}:\d{2})$/.test(aVal)
        if (!hasTimezoneA) {
          // 如果日期字符串没有包含时区信息，假设它是UTC时间
          aDate.setTime(aDate.getTime() + aDate.getTimezoneOffset() * 60 * 1000)
        }
        aVal = aDate.getTime()
      } else {
        aVal = 0
      }

      if (bVal) {
        const bDate = new Date(bVal)
        const hasTimezoneB = /(Z|[+-]\d{2}:\d{2})$/.test(bVal)
        if (!hasTimezoneB) {
          // 如果日期字符串没有包含时区信息，假设它是UTC时间
          bDate.setTime(bDate.getTime() + bDate.getTimezoneOffset() * 60 * 1000)
        }
        bVal = bDate.getTime()
      } else {
        bVal = 0
      }
    }

    // 处理数字类型
    if (sortField.value === 'selfScore' || sortField.value === 'finalScore') {
      aVal = parseFloat(aVal) || 0
      bVal = parseFloat(bVal) || 0
    }

    // 处理字符串类型
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }

    if (aVal < bVal) return sortOrder.value === 'asc' ? -1 : 1
    if (aVal > bVal) return sortOrder.value === 'asc' ? 1 : -1
    return 0
  })

  return applications
})

// 分页后的申请列表
const paginatedApplications = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredApplications.value.slice(start, end)
})

// 总页数
const totalPages = computed(() => {
  return Math.ceil(filteredApplications.value.length / pageSize.value)
})

// 总记录数
const totalItems = computed(() => {
  return filteredApplications.value.length
})

// 当前页起始和结束记录索引
const startItemIndex = computed(() => {
  return filteredApplications.value.length === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1
})

const endItemIndex = computed(() => {
  return Math.min(currentPage.value * pageSize.value, filteredApplications.value.length)
})

// 排序功能
const sortBy = (field) => {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
  // 重置到第一页
  currentPage.value = 1
}

// 获取排序图标
const getSortIcon = (field) => {
  if (sortField.value !== field) return ['fas', 'sort']
  return sortOrder.value === 'asc' ? ['fas', 'sort-up'] : ['fas', 'sort-down']
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return '-'

  // 直接使用本地时间显示，因为后端返回的已经是上海时间
  const date = new Date(dateString)

  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取状态文本
const getStatusText = (status) => {
  const statusMap = {
    draft: '草稿',
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝'
  }
  return statusMap[status] || status
}

// 获取状态样式类
const getStatusClass = (status) => {
  return `status-${status}`
}

// 获取申请类型文本
const getApplicationTypeText = (type) => {
  if (!type) return '其他'
  const typeMap = {
    academic: '学术专长',
    comprehensive: '综合表现'
  }
  return typeMap[type] || type
}

// 获取规则名称
const getRuleName = (ruleId) => {
  if (!ruleId) return '-'
  const rule = availableRules.value.find(r => r.id === ruleId)
  return rule ? rule.name : '-'
}

// 查看申请详情
const viewApplicationDetails = (application) => {
  selectedApplication.value = application
}

// 编辑申请
const editApplication = (application) => {
  // 通知父组件切换到申请表单页面并传递申请ID
  emit('edit-application', application.id)
}

// 删除申请
const deleteApplication = async (application) => {
  if (confirm(`确定要删除申请「${application.projectName || application.eventName || '未命名'}」吗？`)) {
    try {
      // 调用store中的删除方法
      const success = await applicationsStore.deleteApplication(application.id)
      if (success) {
        // 显示删除成功的toast提示
        toastStore.success('申请删除成功')
        // 重置到第一页
        if (paginatedApplications.value.length === 0 && currentPage.value > 1) {
          currentPage.value--
        }
      } else {
        // 显示删除失败的toast提示
        toastStore.error('申请删除失败，请重试')
      }
    } catch (error) {
      console.error('删除申请失败:', error)
      // 显示错误的toast提示
      toastStore.error('系统错误，请稍后重试')
    }
  }
}

// 清空筛选条件
const clearFilters = () => {
  filters.value = {
    status: 'all',
    type: 'all',
    rule: 'all',
    searchQuery: '',
    dateRange: {
      start: '',
      end: ''
    }
  }
  currentPage.value = 1
}

// 重新加载数据
const refreshData = async () => {
  try {
    await applicationsStore.fetchApplications()
    // 重置到第一页
    currentPage.value = 1
  } catch (error) {
    console.error('刷新数据失败:', error)
    // 显示错误的toast提示
    toastStore.error('数据刷新失败，请稍后重试')
  }
}

// 监听筛选条件变化，重置到第一页
watch([() => filters.value.status, () => filters.value.type, () => filters.value.rule, () => filters.value.searchQuery, () => filters.value.dateRange.start, () => filters.value.dateRange.end], () => {
  currentPage.value = 1
}, { deep: true })

// 监听总页数变化，如果当前页大于总页数，调整到最后一页
watch(totalPages, (newTotal) => {
  if (currentPage.value > newTotal && newTotal > 0) {
    currentPage.value = newTotal
  }
})

onMounted(async () => {
  // 加载规则列表
  await fetchRules()
  // 确保数据已加载
  await applicationsStore.fetchApplications()
})

onActivated(async () => {
  // 每次组件被激活时自动刷新数据
  await refreshData()
})
</script>

<style scoped>
/* 引入共享样式 */
@import '../common/shared-styles.css';
</style>