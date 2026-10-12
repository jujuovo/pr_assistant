<template>
  <div class="page-content">
    <div class="page-title">
      <span>规则管理</span>
      <div class="page-title-actions">
        <button class="btn btn-outline" @click="openAddRuleModal">
          <font-awesome-icon :icon="['fas', 'plus']" /> 添加规则
        </button>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filters">
      <div class="filter-group">
        <span class="filter-label">当前学院:</span>
        <select class="form-control" v-model="filters.facultyId">
          <option value="all">全部</option>
          <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">
            {{ faculty.name }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">规则名称:</span>
        <input type="text" class="form-control" v-model="filters.name" placeholder="请输入规则名称">
      </div>
      <div class="filter-group">
        <span class="filter-label">规则类型:</span>
        <select class="form-control" v-model="filters.type" @change="handleFilterTypeChange">
          <option value="all">全部</option>
          <option value="academic">学术专长</option>
          <option value="comprehensive">综合表现</option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">子类型:</span>
        <select class="form-control" v-model="filters.subType">
          <option value="all">全部</option>
          <!-- 学术专长子类型 -->
          <template v-if="filters.type === 'academic' || filters.type === 'all'">
            <option value="competition">学业竞赛</option>
            <option value="research">科研成果</option>
            <option value="innovation">创新创业训练</option>
          </template>
          <!-- 综合表现子类型 -->
          <template v-if="filters.type === 'comprehensive' || filters.type === 'all'">
            <option value="international_internship">国际组织实习</option>
            <option value="military_service">参军入伍服兵役</option>
            <option value="volunteer">志愿服务</option>
            <option value="social_work">社会工作</option>
            <option value="sports">体育比赛</option>
            <option value="honor_title">荣誉称号</option>
          </template>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">状态:</span>
        <select class="form-control" v-model="filters.status">
          <option value="all">全部</option>
          <option value="active">启用</option>
          <option value="disabled">禁用</option>
        </select>
      </div>

      <button class="btn btn-outline" @click="resetFilters">清空筛选</button>
      <button class="btn btn-outline delete-btn" @click="batchDeleteRules" :disabled="selectedRuleIds.length === 0">
        <font-awesome-icon :icon="['fas', 'trash']" /> 批量删除
      </button>
    </div>

    <!-- 规则表格 -->
    <div class="card">
      <!-- 加载状态指示器 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>
      <div class="table-container">
        <table class="application-table">
          <thead>
            <tr>
              <th>
                <input type="checkbox" v-model="selectAll" @change="toggleSelectAll">
              </th>
              <th>学院</th>
              <th>规则名称</th>
              <th>类型</th>
              <th>子类型</th>
              <th>基础分值</th>
              <th>最大分数</th>
              <th>最大数量</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in paginatedRules" :key="rule.id">
              <td>
                <input type="checkbox" v-model="selectedRuleIds" :value="rule.id">
              </td>
              <td>{{ getFacultyName(rule.faculty_id) }}</td>
              <td>{{ rule.name }}</td>
              <td>{{ getTypeText(rule.type) }}</td>
              <td>{{ getSubTypeText(rule.sub_type) }}</td>
              <td>{{ rule.score }}</td>
              <td>{{ rule.max_score || '-' }}</td>
              <td>{{ rule.max_count || '-' }}</td>

              <td>
                <span :class="`status-badge status-${rule.status === 'active' ? 'approved' : 'rejected'}`">
                  {{ rule.status === 'active' ? '启用' : '禁用' }}
                </span>
              </td>
              <td>{{ formatDate(rule.createdAt) }}</td>
              <td>
                <div class="action-buttons">
                  <button class="btn-outline btn small-btn" @click="editRule(rule)" title="编辑">
                    <font-awesome-icon :icon="['fas', 'edit']" />
                  </button>
                  <button v-if="rule.status === 'active'" class="btn-outline btn small-btn"
                    @click="toggleRuleStatus(rule.id)" title="禁用">
                    <font-awesome-icon :icon="['fas', 'ban']" />
                  </button>
                  <button v-else class="btn-outline btn small-btn" @click="toggleRuleStatus(rule.id)" title="启用">
                    <font-awesome-icon :icon="['fas', 'check']" />
                  </button>
                  <button class="btn-outline btn small-btn delete-btn" @click="deleteRule(rule)" title="删除">
                    <font-awesome-icon :icon="['fas', 'trash-alt']" />
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="paginatedRules.length === 0">
              <td colspan="10" class="no-data">暂无规则数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 分页控件 -->
    <div class="pagination">
      <div class="pagination-info">显示 {{ startIndex + 1 }}-{{ endIndex }} 条，共 {{ totalRules }} 条记录</div>
      <div class="pagination-controls">
        <button class="btn-outline btn" :disabled="currentPage === 1" @click="prevPage">
          <font-awesome-icon :icon="['fas', 'chevron-left']" /> 上一页
        </button>
        <button class="btn-outline btn" :disabled="currentPage >= totalPages" @click="nextPage">
          下一页 <font-awesome-icon :icon="['fas', 'chevron-right']" />
        </button>
      </div>
    </div>

    <!-- 添加/编辑规则模态框 -->
    <RuleModal v-if="showAddRuleModal" :visible="showAddRuleModal" :editing-rule="editingRule" :faculties="faculties"
      :all-rules="allRules" @close="closeModal" @save="saveRule" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../../utils/api'
import { useToastStore } from '../../stores/toast'
import { useAuthStore } from '../../stores/auth'
import RuleModal from './RuleModal.vue'

const toastStore = useToastStore()
const authStore = useAuthStore()

const showAddRuleModal = ref(false)
const editingRule = ref(null)
const currentPage = ref(1)
const pageSize = 10
const loading = ref(false)

// 批量选择相关变量
const selectAll = ref(false)
const selectedRuleIds = ref([])

const filters = reactive({
  name: '',
  type: 'all',
  subType: 'all',
  status: 'all',
  facultyId: 'all'
})

// 规则列表
const rules = ref([])
const allRules = ref([])

const faculties = ref([])

// 筛选后的规则列表
const filteredRules = computed(() => {
  return rules.value.filter(rule => {
    // 规则名称筛选
    const matchesName = rule.name.toLowerCase().includes(filters.name.toLowerCase())

    // 类型筛选
    const matchesType = filters.type === 'all' || rule.type === filters.type

    // 子类型筛选
    const matchesSubType = filters.subType === 'all' || rule.sub_type === filters.subType

    // 状态筛选
    const matchesStatus = filters.status === 'all' || rule.status === filters.status

    // 学院筛选
    const matchesFaculty = filters.facultyId === 'all' || rule.faculty_id === filters.facultyId

    return matchesName && matchesType && matchesSubType && matchesStatus && matchesFaculty
  })
})

// 分页计算
const totalRules = computed(() => filteredRules.value.length)
const totalPages = computed(() => Math.ceil(totalRules.value / pageSize))
const startIndex = computed(() => (currentPage.value - 1) * pageSize)
const endIndex = computed(() => Math.min(startIndex.value + pageSize, totalRules.value))

const paginatedRules = computed(() => {
  return filteredRules.value.slice(startIndex.value, endIndex.value)
})

// 初始化数据
onMounted(async () => {
  await fetchFaculties()
  fetchRules()
})

// 获取规则列表
async function fetchRules() {
  loading.value = true
  try {
    const response = await api.getRules({})
    rules.value = Array.isArray(response.rules) ? response.rules : []
    allRules.value = Array.isArray(response.rules) ? response.rules : []
  } catch (error) {
    console.error('获取规则列表失败:', error)
    toastStore.addToast({ message: '获取规则列表失败', type: 'error' })
    rules.value = []
    allRules.value = []
  } finally {
    loading.value = false
  }
}

// 获取学院列表
async function fetchFaculties() {
  try {
    const response = await api.getFacultiesAdmin()
    faculties.value = Array.isArray(response.faculties) ? response.faculties : []
    
    // 将管理员所在的学院设置为默认选中值
    const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    if (adminFacultyId) {
      filters.facultyId = adminFacultyId
    }
  } catch (error) {
    console.error('获取学院列表失败:', error)
    toastStore.addToast({ message: '获取学院列表失败', type: 'error' })
  }
}

// 打开添加规则模态框
function openAddRuleModal() {
  editingRule.value = null
  showAddRuleModal.value = true
}

// 编辑规则
async function editRule(rule) {
  try {
    // 调用API获取完整的规则信息（包括计算规则）
    const response = await api.getRule(rule.id)
    if (response && response.data) {
      editingRule.value = response.data
      showAddRuleModal.value = true
    }
  } catch (error) {
    console.error('获取规则详情失败:', error)
    toastStore.addToast({ message: '获取规则详情失败', type: 'error' })
  }
}

// 关闭模态框
function closeModal() {
  showAddRuleModal.value = false
  editingRule.value = null
}

// 保存规则
async function saveRule(formData) {
  try {
    // 使用来自RuleModal的数据
    const ruleFormData = formData

    // 验证必填字段
    if (!ruleFormData.name || !ruleFormData.type || !ruleFormData.sub_type || ruleFormData.score === null) {
      toastStore.addToast({ message: '请填写完整的必填字段', type: 'error' })
      return
    }

    // 特殊验证：如果是科研成果，需要选择科研成果种类
    if (ruleFormData.type === 'academic' && ruleFormData.sub_type === 'research' && !ruleFormData.research_type) {
      toastStore.addToast({ message: '请选择科研成果种类', type: 'error' })
      return
    }

    // 处理规则数据
    const ruleData = {
      ...ruleFormData,
      // 将空字符串转换为null
      max_score: ruleFormData.max_score === '' ? null : ruleFormData.max_score,
      max_count: ruleFormData.max_count === '' ? null : ruleFormData.max_count,
      faculty_id: ruleFormData.faculty_id === '' ? null : ruleFormData.faculty_id,
      research_type: ruleFormData.research_type === '' ? null : ruleFormData.research_type
    }

    // 如果是科研成果类型且没有选择科研成果种类，清空该字段
    if (ruleData.type !== 'academic' || ruleData.sub_type !== 'research') {
      ruleData.research_type = null
    }

    let response
    if (ruleFormData.id) {
      // 更新规则
      response = await api.updateRule(ruleFormData.id, ruleData)
      toastStore.addToast({ message: '规则更新成功', type: 'success' })
    } else {
      // 创建新规则
      response = await api.createRule(ruleData)
      toastStore.addToast({ message: '规则创建成功', type: 'success' })
    }

    // 刷新规则列表
    fetchRules()

    // 关闭模态框
    closeModal()
  } catch (error) {
    console.error('保存规则失败:', error)
    toastStore.addToast({ message: '保存规则失败', type: 'error' })
  }
}

// 切换规则状态
async function toggleRuleStatus(ruleId) {
  try {
    const rule = rules.value.find(r => r.id === ruleId)
    if (!rule) return

    // 确定当前操作类型
    const action = rule.status === 'active' ? '禁用' : '启用'

    await api.toggleRuleStatus(ruleId)
    toastStore.addToast({ message: `规则${action}成功`, type: 'success' })
    fetchRules()
  } catch (error) {
    console.error('切换规则状态失败:', error)
    toastStore.addToast({ message: '切换规则状态失败', type: 'error' })
  }
}

// 删除规则
async function deleteRule(rule) {
  if (confirm(`确定要删除规则 "${rule.name}" 吗？此操作不可恢复。`)) {
    try {
      await api.deleteRule(rule.id)
      toastStore.addToast({ message: '规则删除成功', type: 'success' })
      fetchRules()
    } catch (error) {
      console.error('删除规则失败:', error)
      toastStore.addToast({ message: '删除规则失败', type: 'error' })
    }
  }
}

// 分页控制
function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

// 格式化日期
function formatDate(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取类型文本
function getTypeText(type) {
  switch (type) {
    case 'academic': return '学术专长'
    case 'comprehensive': return '综合表现'
    default: return type
  }
}

// 获取子类型文本
function getSubTypeText(subType) {
  switch (subType) {
    // 学术专长
    case 'competition': return '学业竞赛'
    case 'research': return '科研成果'
    case 'innovation': return '创新创业训练'
    // 综合表现
    case 'international_internship': return '国际组织实习'
    case 'military_service': return '参军入伍服兵役'
    case 'volunteer': return '志愿服务'
    case 'social_work': return '社会工作'
    case 'sports': return '体育比赛'
    case 'honor_title': return '荣誉称号'
    default: return subType
  }
}

// 处理筛选类型变化
function handleFilterTypeChange() {
  filters.subType = 'all'
}

// 根据学院ID获取学院名称
function getFacultyName(facultyId) {
  if (!facultyId) return '-'
  const faculty = faculties.value.find(f => f.id === facultyId)
  return faculty ? faculty.name : '-'
}

// 全选/取消全选功能
function toggleSelectAll() {
  if (selectAll.value) {
    // 全选：将当前页所有规则的ID添加到selectedRuleIds中
    selectedRuleIds.value = paginatedRules.value.map(rule => rule.id)
  } else {
    // 取消全选：清空selectedRuleIds
    selectedRuleIds.value = []
  }
}

// 批量删除功能
async function batchDeleteRules() {
  if (selectedRuleIds.value.length === 0) {
    toastStore.addToast({ message: '请先选择要删除的规则', type: 'warning' })
    return
  }

  if (confirm(`确定要删除选中的 ${selectedRuleIds.value.length} 条规则吗？此操作不可恢复。`)) {
    try {
      loading.value = true
      // 调用API批量删除规则
      await api.batchDeleteRules(selectedRuleIds.value)
      toastStore.addToast({ message: '批量删除规则成功', type: 'success' })

      // 重置选择状态
      selectAll.value = false
      selectedRuleIds.value = []

      // 刷新规则列表
      await fetchRules()
    } catch (error) {
      console.error('批量删除规则失败:', error)
      toastStore.addToast({ message: '批量删除规则失败', type: 'error' })
    } finally {
      loading.value = false
    }
  }
}

// 重置筛选
function resetFilters() {
  // 保存当前学院选择
  const currentFaculty = filters.facultyId
  Object.assign(filters, {
    name: '',
    type: 'all',
    subType: 'all',
    status: 'all',
    facultyId: currentFaculty
  })
}
</script>

<style scoped>
/* 引入共享样式 */
@import '../common/shared-styles.css';
</style>