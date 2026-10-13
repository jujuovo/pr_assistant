<template>
  <div class="page-content">
    <div class="page-title application-form-heading">
      <button
        v-if="selectedCategory"
        type="button"
        class="back-category-button"
        @click="$emit('back-to-categories')"
      >
        <font-awesome-icon :icon="['fas', 'arrow-left']" aria-hidden="true" />
        返回评测项目
      </button>
      <span>{{ selectedCategory ? `${selectedCategory.title}申请` : '加分申请' }}</span>
    </div>

    <div class="card application-card simplified-application-card">
      <form @submit.prevent="submitForm" novalidate>
        <section class="form-section application-step">
          <div class="section-title">
            <span class="step-number">1</span>
            <span>项目类型</span>
          </div>
          <div class="form-group">
            <label class="form-label" for="application-type"
              >项目类型 <span class="required">*</span></label
            >
            <div class="input-with-icon">
              <font-awesome-icon :icon="['fas', 'list-check']" aria-hidden="true" />
              <select
                id="application-type"
                v-model="formData.applicationType"
                class="form-control"
                required
                :disabled="loading.rules"
                @change="handleProjectTypeChange"
              >
                <option value="">请选择项目类型</option>
                <option v-for="type in projectTypes" :key="type.value" :value="type.value">
                  {{ type.label }}
                </option>
              </select>
            </div>
            <p class="field-help">{{
              selectedCategory
                ? `当前栏目：${selectedCategory.title}`
                : '请选择项目类型，选择后才能继续填写申请信息。'
            }}</p>
          </div>
        </section>

        <section
          class="form-section application-step gated-step"
          :class="{ 'is-locked': !hasProjectType }"
        >
          <div class="section-title">
            <span class="step-number">2</span>
            <span>项目全称 &amp; 获得时间</span>
          </div>
          <fieldset :disabled="!hasProjectType">
            <div class="form-grid">
              <div class="form-group">
                <label class="form-label" for="project-name"
                  >项目全称 <span class="required">*</span></label
                >
                <div class="input-with-icon">
                  <font-awesome-icon :icon="['fas', 'signature']" aria-hidden="true" />
                  <input
                    id="project-name"
                    v-model.trim="formData.projectName"
                    type="text"
                    class="form-control"
                    placeholder="请输入项目全称（2–30个字符）"
                    minlength="2"
                    maxlength="30"
                    required
                  />
                </div>
              </div>
              <div class="form-group">
                <label class="form-label" for="award-date"
                  >获得时间 <span class="required">*</span></label
                >
                <div class="input-with-icon">
                  <font-awesome-icon :icon="['fas', 'calendar']" aria-hidden="true" />
                  <input
                    id="award-date"
                    v-model="formData.awardDate"
                    type="date"
                    class="form-control"
                    required
                  />
                </div>
              </div>
            </div>
          </fieldset>
          <button
            v-if="!hasProjectType"
            type="button"
            class="locked-click-target"
            aria-label="项目类型未选择，点击查看提示"
            @click="notifyProjectTypeRequired"
          ></button>
        </section>

        <section
          class="form-section application-step gated-step"
          :class="{ 'is-locked': !hasProjectType }"
        >
          <div class="section-title">
            <span class="step-number">3</span>
            <span>证明材料</span>
          </div>
          <fieldset :disabled="!hasProjectType">
            <div
              class="file-upload-area"
              @click="triggerFileInput"
              @drop="handleDrop"
              @dragover.prevent
              @dragenter.prevent
            >
              <div class="upload-icon"
                ><font-awesome-icon :icon="['fas', 'cloud-upload-alt']"
              /></div>
              <div class="upload-text">
                <p>点击或拖拽文件到此处上传</p>
                <p class="help-text"
                  >支持 {{ fileUploadSettings.allowedFileTypesString }} 格式，单个文件不超过
                  {{ fileUploadSettings.singleFileSizeLimit }}MB，总文件大小不超过
                  {{ fileUploadSettings.totalFileSizeLimit }}MB，最多上传
                  {{ fileUploadSettings.maxFileCount }} 个文件</p
                >
              </div>
            </div>
            <input
              ref="fileInput"
              type="file"
              class="visually-hidden-file"
              :accept="fileUploadSettings.allowedFileTypes.join(',')"
              multiple
              @change="handleFileSelect"
            />

            <div v-if="formData.files.length" class="file-list">
              <div class="file-list-header"
                ><span>已上传文件（{{ formData.files.length }}）</span></div
              >
              <div
                v-for="(file, index) in formData.files"
                :key="file.name + index"
                class="file-item"
              >
                <div class="file-icon"><font-awesome-icon :icon="getFileIcon(file.name)" /></div>
                <div class="file-info">
                  <div class="file-name">{{ file.name }}</div>
                  <div class="file-meta">{{ formatFileSize(file.size) }}</div>
                </div>
                <div class="file-actions">
                  <button
                    type="button"
                    class="file-action-btn"
                    @click.stop="previewFile(file)"
                    aria-label="预览文件"
                  >
                    <font-awesome-icon :icon="['fas', 'eye']" />
                  </button>
                  <button
                    type="button"
                    class="file-action-btn"
                    @click.stop="removeFile(index)"
                    aria-label="删除文件"
                  >
                    <font-awesome-icon :icon="['fas', 'times']" />
                  </button>
                </div>
              </div>
            </div>
          </fieldset>
          <button
            v-if="!hasProjectType"
            type="button"
            class="locked-click-target"
            aria-label="项目类型未选择，点击查看提示"
            @click="notifyProjectTypeRequired"
          ></button>
        </section>

        <div class="form-actions">
          <button type="button" class="btn btn-outline" @click="saveDraft">
            <font-awesome-icon :icon="['fas', 'save']" /> 保存草稿
          </button>
          <button type="submit" class="btn btn-primary">
            <font-awesome-icon :icon="['fas', 'paper-plane']" /> 提交审核
          </button>
        </div>
      </form>
    </div>

    <div v-if="previewFileData" class="modal-overlay" @click="closePreview">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3><font-awesome-icon :icon="getFileIcon(previewFileData.name)" /> 文件预览</h3>
          <button class="close-btn" @click="closePreview" aria-label="关闭预览">
            <font-awesome-icon :icon="['fas', 'times']" />
          </button>
        </div>
        <div class="modal-body">
          <div v-if="isImageFile(previewFileData.name)" class="image-preview">
            <img :src="previewFileData.url" :alt="previewFileData.name" />
          </div>
          <div v-else class="file-preview">
            <div class="file-preview-icon"
              ><font-awesome-icon :icon="getFileIcon(previewFileData.name)" size="4x"
            /></div>
            <h4>{{ previewFileData.name }}</h4>
            <p class="help-text">该文件类型不支持在线预览，请下载后查看</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useApplicationsStore } from '@/stores/applications.js'
import { useToastStore } from '@/stores/toast.js'
import { getFileFullUrl } from '@/services/api.js'

// 接收编辑申请ID
const props = defineProps(['editApplicationId', 'selectedCategory'])
defineEmits(['back-to-categories'])

const authStore = useAuthStore()
const applicationsStore = useApplicationsStore()
const toastStore = useToastStore()
const fileInput = ref(null)
const previewFileData = ref(null)

const categoryProjectTypes = {
  'academic-performance': [
    '科创竞赛',
    '学术论文',
    '专利著作',
    '专业作品展出',
    '大创项目',
    'CCF CSP认证'
  ],
  'academic-innovation': [
    '科创竞赛',
    '学术论文',
    '专利著作',
    '专业作品展出',
    '大创项目',
    'CCF CSP认证'
  ],
  'social-work': ['学生干部任职经历', '学生干部表彰'],
  'volunteer-service': ['志愿服务经历', '志愿服务表彰'],
  'social-practice': ['社会实践经历', '社会实践表彰'],
  'arts-sports': ['文体竞赛', '表演展示', '文体表彰', '文明宿舍表彰', '体质健康测试']
}

const categoryKeywords = {
  'academic-performance': ['学业', '课程', '成绩'],
  'academic-innovation': ['学术', '科研', '创新', '竞赛', '论文', '专利', '著作', '大创', 'csp'],
  'social-work': ['社会工作', '学生工作', '干部', '任职'],
  'volunteer-service': ['志愿', '公益'],
  'social-practice': ['社会实践', '调研'],
  'arts-sports': ['文体', '文化', '艺术', '体育', '宿舍', '体质']
}

const allProjectTypeLabels = [...new Set(Object.values(categoryProjectTypes).flat())]
const projectTypes = computed(() => {
  const labels = props.selectedCategory?.key
    ? categoryProjectTypes[props.selectedCategory.key] || []
    : allProjectTypeLabels
  return labels.map((label) => ({
    value: label,
    label,
    keywords: [label, ...(categoryKeywords[props.selectedCategory?.key] || [])]
  }))
})

const hasProjectType = computed(() => Boolean(formData.applicationType))

const notifyProjectTypeRequired = () => {
  toastStore.warning('请先选择项目类型，选择后才能继续填写')
}

const syncRuleForProjectType = () => {
  if (!formData.applicationType || !availableRules.value.length) return
  const selectedType = projectTypes.value.find((type) => type.value === formData.applicationType)
  const matchingRule =
    availableRules.value.find((rule) => {
      const source = `${rule.type || ''} ${rule.name || ''} ${rule.description || ''}`.toLowerCase()
      return (
        rule.type === formData.applicationType ||
        selectedType?.keywords.some((keyword) => source.includes(keyword.toLowerCase()))
      )
    }) || availableRules.value[0]

  if (matchingRule) {
    formData.ruleId = matchingRule.id
    formData.selfScore = String(matchingRule.score || 0)
    formData.description = `${selectedType?.label || '加分项目'}证明材料申请`
  }
}

const handleProjectTypeChange = () => {
  if (!formData.applicationType) {
    formData.ruleId = ''
    return
  }
  syncRuleForProjectType()
}

// 表单数据
const formData = reactive({
  // 添加用户信息
  id: null, // 用于存储申请ID，编辑时使用
  studentId: authStore.user?.studentId || '',
  name: authStore.userName,
  departmentId: authStore.user?.departmentId || '',
  majorId: authStore.user?.majorId || '',
  facultyId: authStore.user?.facultyId || authStore.user?.faculty_id || '',
  // 基本信息
  projectName: '',
  awardDate: '',
  ruleId: '', // 选择的规则ID
  // 动态系数字段，根据规则配置自动生成
  dynamicCoefficients: {},
  // 通用字段
  selfScore: '',
  description: '',
  files: [],
  // 申请类型，将从规则中获取
  applicationType: ''
})

// 加载状态
const loading = reactive({
  rules: false,
  calculation: false,
  score: false
})

// 监听规则变化，清空旧规则的动态系数字段
const isLoadingEditData = ref(false)

// 重置表单的通用函数
const resetForm = () => {
  Object.assign(formData, {
    id: null,
    studentId: authStore.user?.studentId || '',
    name: authStore.userName,
    departmentId: authStore.user?.departmentId || '',
    majorId: authStore.user?.majorId || '',
    projectName: '',
    awardDate: '',
    ruleId: '',
    selfScore: '',
    description: '',
    files: [],
    dynamicCoefficients: {},
    applicationType: '',
    facultyId: authStore.user?.facultyId || authStore.user?.faculty_id || ''
  })
}

// 规则选择和预估分数计算相关
import api from '@/services/api.js'

const availableRules = ref([])
const estimatedScore = ref(0)

// 系统设置
const systemSettings = ref({
  singleFileSizeLimit: 10, // 默认10MB
  totalFileSizeLimit: 50, // 默认50MB
  allowedFileTypes: ['.pdf', '.jpg', '.jpeg', '.png'], // 数组格式，用于文件输入框的accept属性
  allowedFileTypesString: '.pdf, .jpg, .jpeg, .png' // 字符串格式，直接用于显示
})

// 计算属性，确保模板始终能获取到正确的值
const fileUploadSettings = computed(() => ({
  allowedFileTypesString:
    systemSettings.value?.allowedFileTypesString || '.pdf, .jpg, .jpeg, .png, .webp',
  singleFileSizeLimit: systemSettings.value?.singleFileSizeLimit || 10,
  totalFileSizeLimit: systemSettings.value?.totalFileSizeLimit || 50,
  maxFileCount: systemSettings.value?.maxFileCount || 10,
  allowedFileTypes: systemSettings.value?.allowedFileTypes || [
    '.pdf',
    '.jpg',
    '.jpeg',
    '.png',
    '.webp'
  ]
}))

// 加载编辑数据
const loadEditData = async (applicationId) => {
  // 如果没有ID或ID为空，重置为新表单
  if (!applicationId) {
    // 清空表单
    resetForm()
    return
  }

  // 设置加载标志，避免在加载过程中清空动态系数
  isLoadingEditData.value = true

  try {
    const application = await applicationsStore.fetchApplicationById(applicationId)

    // 将后端字段转换为前端字段名
    const frontendData = toFrontendFields(application)

    // 清空表单
    resetForm()

    // 先设置ruleId，确保selectedRule能够正确计算
    if (frontendData.ruleId) {
      formData.ruleId = frontendData.ruleId
    }
    // 这将确保系数选择字段能够正确显示
    await fetchMatchingRules()

    // 填充表单基本数据（排除动态系数字段和ruleId，单独处理）
    for (const [key, value] of Object.entries(frontendData)) {
      if (key in formData && key !== 'dynamicCoefficients' && key !== 'ruleId') {
        formData[key] = value
      }
    }
    // 填充动态系数字段
    let dynamicCoefficients = {}

    // 优先使用转换后的字段，如果没有则使用原始字段
    const rawDynamicCoefficients =
      frontendData.dynamicCoefficients || application.dynamic_coefficients
    if (rawDynamicCoefficients) {
      if (typeof rawDynamicCoefficients === 'string') {
        try {
          dynamicCoefficients = JSON.parse(rawDynamicCoefficients)
        } catch (error) {
          console.error('解析动态系数失败:', error)
          dynamicCoefficients = {}
        }
      } else {
        dynamicCoefficients = rawDynamicCoefficients
      }
    } else {
      console.log('没有找到动态系数数据')
    }
    // 确保dynamicCoefficients是对象
    if (typeof dynamicCoefficients !== 'object' || dynamicCoefficients === null) {
      dynamicCoefficients = {}
    }
    // 将所有值转换为字符串类型，以匹配select选项的值类型
    const stringifiedCoefficients = {}
    for (const [key, value] of Object.entries(dynamicCoefficients)) {
      stringifiedCoefficients[key] = value !== null && value !== undefined ? String(value) : ''
    }
    // 清空现有的dynamicCoefficients
    Object.keys(formData.dynamicCoefficients).forEach(
      (key) => delete formData.dynamicCoefficients[key]
    )
    // 将tree_path转换为前端需要的带索引的树结构字段
    // 先将tree_path字符串转换为数组
    if (
      stringifiedCoefficients.tree_path &&
      typeof stringifiedCoefficients.tree_path === 'string'
    ) {
      stringifiedCoefficients.tree_path = stringifiedCoefficients.tree_path.split(',')
    }
    if (stringifiedCoefficients.tree_path && Array.isArray(stringifiedCoefficients.tree_path)) {
      // 获取当前选中的规则
      const currentRule = availableRules.value.find((rule) => rule.id === formData.ruleId)
      if (currentRule && currentRule.calculation) {
        let parameters = currentRule.calculation.parameters || {}
        if (typeof parameters === 'string') {
          try {
            parameters = JSON.parse(parameters)
          } catch (error) {
            console.error('解析规则参数失败:', error)
            parameters = {}
          }
        }

        // 检查是否是树结构计算
        if (currentRule.calculation.calculation_type === 'tree' || parameters.type === 'tree') {
          const treeConfig = parameters.tree || {}
          const tree = treeConfig.root || (treeConfig.structure && treeConfig.structure.root)

          if (tree && tree.dimension) {
            // 遍历tree_path数组，为每个元素创建对应的索引字段
            let currentNode = tree
            stringifiedCoefficients.tree_path.forEach((path, index) => {
              // 使用当前节点的dimension.key作为字段名前缀
              const fieldName = `${currentNode.dimension.key}_${index}`
              stringifiedCoefficients[fieldName] = path

              // 移动到下一个节点
              if (currentNode.children && currentNode.children.length > 0) {
                const nextNode = currentNode.children.find((child) => child.dimension.name === path)
                if (nextNode) {
                  currentNode = nextNode
                }
              }
            })

            // 如果有下一层级，创建对应的字段
            if (currentNode.children && currentNode.children.length > 0) {
              const nextLevelIndex = stringifiedCoefficients.tree_path.length
              const nextFieldName = `${currentNode.dimension.key}_${nextLevelIndex}`
              stringifiedCoefficients[nextFieldName] = ''
            }
          }
        } else {
          // 非树结构计算，直接使用tree_${index}格式
          stringifiedCoefficients.tree_path.forEach((path, index) => {
            const fieldName = `tree_${index}`
            stringifiedCoefficients[fieldName] = path
          })
        }
      } else {
        // 如果没有找到规则或计算配置，直接使用tree_${index}格式
        stringifiedCoefficients.tree_path.forEach((path, index) => {
          const fieldName = `tree_${index}`
          stringifiedCoefficients[fieldName] = path
        })
      }

      // 移除tree_path字段，因为前端不再需要它
      delete stringifiedCoefficients.tree_path
    }

    // 检查是否存在直接的tree_字段（如果后端没有返回tree_path数组）
    const hasDirectTreeFields = Object.keys(stringifiedCoefficients).some((key) =>
      /tree_(\d+)$/.test(key)
    )

    // 如果没有tree_path数组也没有直接的tree_字段，尝试从rule配置中创建默认的tree_字段
    if (!stringifiedCoefficients.tree_path && !hasDirectTreeFields) {
      // 获取当前选中的规则
      const selectedRule = availableRules.value.find((rule) => rule.id === formData.ruleId)
      if (selectedRule && selectedRule.calculation && selectedRule.calculation.fields) {
        // 检查规则中是否有树结构字段
        const treeFields = selectedRule.calculation.fields.filter((field) => field.type === 'tree')
        if (treeFields.length > 0) {
          // 创建默认的tree_字段
          treeFields.forEach((field, index) => {
            const fieldName = `tree_${index}`
            stringifiedCoefficients[fieldName] = ''
          })
        }
      }
    }

    // 使用reactive创建一个新的dynamicCoefficients对象，确保Vue的响应式系统能够正确跟踪变化
    const newDynamicCoefficients = reactive({})
    Object.assign(newDynamicCoefficients, stringifiedCoefficients)
    formData.dynamicCoefficients = newDynamicCoefficients

    // 手动重建选中的树节点路径，确保表单字段能正确显示之前选择的层级
    rebuildSelectedTreePath()
    // 处理文件（如果有）
    if (application.files && Array.isArray(application.files)) {
      // 将后端返回的文件数据转换为前端可用的格式
      formData.files = application.files.map((file) => {
        // 后端返回的文件通常包含id、name、path等字段
        // 直接使用这些字段创建一个文件对象表示
        return {
          id: file.id,
          name: file.name,
          path: file.path,
          size: file.size || 0,
          // 标记这是后端返回的文件，不是浏览器File对象
          isBackendFile: true
        }
      })
    } else {
      formData.files = []
    }
  } catch (error) {
    console.error('加载编辑数据失败:', error)
    // 当加载失败（如404），重置为新表单
    resetForm()
  } finally {
    // 无论加载成功或失败，都重置加载标志
    isLoadingEditData.value = false
  }
}

// 监听编辑申请ID变化
watch(
  () => props.editApplicationId,
  (newId) => {
    if (newId) {
      loadEditData(newId)
    }
  },
  { immediate: true }
)

// 防抖函数
const debounce = (func, delay) => {
  let timeoutId
  return (...args) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => func.apply(null, args), delay)
  }
}

// 创建防抖版本的预估分数计算函数，避免频繁计算
const debouncedCalculateEstimatedScore = debounce(() => {
  if (formData.ruleId) {
    calculateEstimatedScore()
  }
}, 300) // 300ms防抖

// 监听表单关键字段变化，自动匹配规则
watch(
  () => formData.projectName,
  debounce(() => {
    fetchMatchingRules()
  }, 500)
) // 500ms防抖

// 仅在需要时重新加载规则
watch(
  () => formData.ruleId,
  () => {
    // 规则ID变化时，重新计算预估分数
    if (formData.ruleId) {
      calculateEstimatedScore()
    }
  }
)

// 缓存规则数据，避免重复请求
const cachedRules = ref([])

// 获取匹配的规则
const fetchMatchingRules = async () => {
  // 如果已经加载过规则，直接使用缓存
  if (cachedRules.value.length > 0) {
    availableRules.value = cachedRules.value
    syncRuleForProjectType()
    calculateEstimatedScore()
    return
  }

  loading.rules = true
  try {
    // 获取学生所在学院ID
    const studentFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    // 使用正确的API方法获取规则
    const rulesResponse = await api.getRules({ faculty_id: studentFacultyId })
    // 过滤掉禁用的规则，只显示状态为'active'的规则
    const activeRules = rulesResponse.rules.filter((rule) => rule.status === 'active')

    // 将串行请求改为并行请求
    const rulesWithCalculation = await Promise.all(
      activeRules.map(async (rule) => {
        try {
          const calculationResponse = await api.getRuleCalculation(rule.id)
          return {
            ...rule,
            calculation: calculationResponse.data || null
          }
        } catch (error) {
          console.error(`获取规则${rule.id}的计算配置失败:`, error)
          return rule
        }
      })
    )

    availableRules.value = rulesWithCalculation
    cachedRules.value = rulesWithCalculation // 缓存规则数据

    // 精简表单只展示项目类型，内部自动匹配一条兼容规则用于原提交接口。
    syncRuleForProjectType()

    // 重新计算预估分数
    calculateEstimatedScore()
  } catch (error) {
    console.error('获取规则失败:', error)
  } finally {
    loading.rules = false
  }
}

// 获取当前选中的规则
const selectedRule = computed(() => {
  if (!formData.ruleId) return null
  return availableRules.value.find((rule) => rule.id === formData.ruleId)
})

// 跟踪当前选中的树节点路径，用于层级显示表单
const selectedTreePath = ref([])

watch(
  () => selectedRule.value?.id,
  (newRuleId, oldRuleId) => {
    if (newRuleId !== oldRuleId && !isLoadingEditData.value) {
      // 清空动态系数，只保留当前规则相关的字段
      formData.dynamicCoefficients = {}

      // 重置预估分数
      estimatedScore.value = 0
    }
  }
)

// 通用监听：所有动态系数变化都触发预估分数重新计算
watch(
  () => formData.dynamicCoefficients,
  () => {
    if (selectedRule.value?.calculation) {
      calculateEstimatedScore()
    }
  },
  { deep: true }
)

// 根据当前表单值重建选中的树节点路径
const rebuildSelectedTreePath = (newCoefficients = formData.dynamicCoefficients) => {
  if (!selectedRule.value?.calculation) return

  const calculationType = selectedRule.value.calculation.calculation_type
  let parameters = selectedRule.value.calculation.parameters || {}
  if (typeof parameters === 'string') {
    try {
      parameters = JSON.parse(parameters)
    } catch (error) {
      console.error('解析规则参数失败:', error)
      return
    }
  }

  if (calculationType !== 'tree' && parameters.type !== 'tree') return

  const treeConfig = parameters.tree || {}
  const tree = treeConfig.root || (treeConfig.structure && treeConfig.structure.root)
  if (!tree) return

  // 根据当前表单值重建选中的树节点路径
  const buildPath = (node, path = [], level = 0) => {
    if (!node || !node.dimension) return path

    // 查找当前节点的表单值（支持带索引的字段名）
    const indexedKey = `${node.dimension.key}_${level}`
    let fieldValue = newCoefficients[indexedKey]

    if (fieldValue !== undefined && fieldValue !== null && fieldValue !== '') {
      // 检查当前值是否为当前节点的有效子节点
      const isValidChild = node.children?.some((child) => child.dimension.name === fieldValue)

      if (isValidChild) {
        path.push(fieldValue)

        // 查找匹配的子节点
        const selectedChild = node.children.find((child) => child.dimension.name === fieldValue)
        if (selectedChild && selectedChild.children && selectedChild.children.length > 0) {
          return buildPath(selectedChild, path, level + 1)
        }
      }
    }

    return path
  }

  // 重建选中的树节点路径
  const newPath = buildPath(tree)

  // 如果路径发生变化，清除不再需要的字段值
  if (JSON.stringify(newPath) !== JSON.stringify(selectedTreePath.value)) {
    // 保存当前需要的字段名
    const neededFields = new Set()

    // 标记当前路径需要的字段
    let currentNode = tree
    for (let i = 0; i < newPath.length; i++) {
      const indexedKey = `${currentNode.dimension.key}_${i}`
      neededFields.add(indexedKey)

      // 移动到下一个节点
      if (currentNode?.children && currentNode.children.length > 0) {
        currentNode = currentNode.children.find((child) => child.dimension.name === newPath[i])
        if (!currentNode) break
      } else {
        currentNode = null
        break
      }
    }

    // 标记下一层级需要的字段
    if (currentNode && currentNode.children && currentNode.children.length > 0) {
      const nextLevelKey = `${currentNode.dimension.key}_${newPath.length}`
      neededFields.add(nextLevelKey)
    }

    // 更直接地清除不再需要的字段值
    const keysToDelete = []
    for (const key in newCoefficients) {
      // 检查是否是树结构字段（带索引的字段名）
      const isTreeField = /_\d+$/.test(key)
      if (isTreeField && !neededFields.has(key)) {
        keysToDelete.push(key)
      }
    }

    // 执行删除操作
    keysToDelete.forEach((key) => {
      delete newCoefficients[key]
    })
  }

  selectedTreePath.value = newPath
}

// 监听表单字段变化，更新选中的树节点路径
watch(
  () => formData.dynamicCoefficients,
  (newCoefficients) => {
    rebuildSelectedTreePath(newCoefficients)
  },
  { deep: true }
)

// 动态生成的表单字段配置 - 实现层级选择，每层显示独立选择框
const dynamicFormFields = computed(() => {
  if (!selectedRule.value?.calculation) {
    return []
  }

  const calculationType = selectedRule.value.calculation.calculation_type
  let parameters = selectedRule.value.calculation.parameters || {}

  // 解析参数（可能是JSON字符串）
  if (typeof parameters === 'string') {
    try {
      parameters = JSON.parse(parameters)
    } catch (error) {
      console.error('解析规则参数失败:', error)
      return []
    }
  }

  const fields = []

  // 根据计算类型生成不同的表单字段
  if (calculationType === 'tree' || parameters.type === 'tree') {
    // 树结构计算：生成路径中每个层级的表单字段
    try {
      const treeConfig = parameters.tree || {}
      const tree = treeConfig.root || (treeConfig.structure && treeConfig.structure.root)

      if (!tree || !tree.dimension) return []

      // 生成路径中每个层级的选择框
      let currentNode = tree
      let currentDepth = 0

      // 显示已选择的层级，每个层级都显示为选择框
      for (let i = 0; i < selectedTreePath.value.length; i++) {
        const selectedValue = selectedTreePath.value[i]

        // 只有当当前节点有子节点时，才生成选择框
        if (currentNode.children && currentNode.children.length > 0) {
          // 获取当前节点的子节点作为选项
          const options =
            currentNode.children?.map((child) => ({
              value: child.dimension.name,
              label: child.dimension.name
            })) || []

          fields.push({
            name: `${currentNode.dimension.key}_${i}`, // 使用唯一名称避免字段冲突
            label: currentNode.dimension.name,
            type: 'select',
            options: options,
            value: selectedValue,
            required: true,
            depth: currentDepth,
            originalKey: currentNode.dimension.key // 保存原始key用于数据处理
          })
        }

        // 移动到下一个节点
        if (currentNode?.children && currentNode.children.length > 0) {
          const nextNode = currentNode.children.find(
            (child) => child.dimension.name === selectedValue
          )
          if (nextNode && nextNode.dimension) {
            currentNode = nextNode
            currentDepth++
          } else {
            currentNode = null // 如果没有匹配的子节点，终止遍历
          }
        } else {
          currentNode = null // 如果当前节点没有子节点，终止遍历
        }
      }

      // 如果当前节点有子节点，显示下一层级的选择框
      if (currentNode && currentNode.children && currentNode.children.length > 0) {
        fields.push({
          name: `${currentNode.dimension.key}_${selectedTreePath.value.length}`, // 使用唯一名称
          label: currentNode.dimension.name,
          type: 'select',
          options: currentNode.children.map((child) => ({
            value: child.dimension.name,
            label: child.dimension.name
          })),
          required: true,
          depth: currentDepth,
          originalKey: currentNode.dimension.key // 保存原始key用于数据处理
        })
      }
    } catch (error) {
      console.error('解析树结构参数失败:', error)
      return []
    }
  }

  return fields
})

// 计算预估分数
const calculateEstimatedScore = async () => {
  if (!formData.ruleId) {
    estimatedScore.value = 0
    return
  }

  loading.score = true
  try {
    const selectedRule = availableRules.value.find((rule) => rule.id === formData.ruleId)
    if (!selectedRule) {
      estimatedScore.value = 0
      return
    }
    // 项目类型由用户在六个固定选项中选择，不能再被后端规则类型覆盖。

    // 准备学生数据
    const studentData = {
      faculty_id: authStore.user?.faculty_id || authStore.user?.facultyId
    }

    // 处理动态系数，将树结构字段转换为后端期望的格式
    // 与prepareApplicationData函数保持完全一致的处理逻辑
    const processedCoefficients = {}

    // 第一步：直接将所有树结构字段转换为路径数组，总是使用'tree_path'作为键名
    // 这样后端可以统一处理所有规则的树路径
    const treePathValues = []

    // 找出所有树结构字段并按索引排序
    const treeFieldKeys = Object.keys(formData.dynamicCoefficients)
      .filter((key) => /.*?_\d+$/.test(key))
      .sort((a, b) => {
        const indexA = parseInt(a.match(/.*?_(\d+)$/)[1])
        const indexB = parseInt(b.match(/.*?_(\d+)$/)[1])
        return indexA - indexB
      })

    // 提取树路径值
    for (const key of treeFieldKeys) {
      const value = formData.dynamicCoefficients[key]
      if (value !== undefined && value !== null && value !== '') {
        treePathValues.push(value)
      }
    }

    // 保存树路径到固定的'tree_path'字段
    if (treePathValues.length > 0) {
      processedCoefficients.tree_path = treePathValues
    }

    // 复制所有非树结构字段
    for (const [key, value] of Object.entries(formData.dynamicCoefficients)) {
      // 跳过树结构字段（带索引的字段）
      if (!/(.*?)_\d+$/.test(key)) {
        processedCoefficients[key] = value
      }
    }

    // 将处理后的动态系数字段添加到学生数据中
    for (const [key, value] of Object.entries(processedCoefficients)) {
      studentData[key] = value
    }
    // 将字符串类型的数字转换为数字类型
    Object.keys(studentData).forEach((key) => {
      if (typeof studentData[key] === 'string' && !isNaN(Number(studentData[key]))) {
        studentData[key] = Number(studentData[key])
      }
    })
    // 调用后端API计算分数
    const scoreResponse = await api.calculateRuleScore(selectedRule.id, {
      student_data: studentData
    })
    if (scoreResponse.code === 200) {
      estimatedScore.value = parseFloat(scoreResponse.data.score.toFixed(4))
    } else {
      // 如果API返回错误，回退到前端计算
      throw new Error('API calculation failed')
    }
  } catch (error) {
    console.log('计算错误:', error)
    // 如果API调用失败，回退到前端计算
    const selectedRule = availableRules.value.find((rule) => rule.id === formData.ruleId)
    if (!selectedRule) {
      estimatedScore.value = 0
      return
    }

    let score = calculateScoreFrontend(selectedRule)
    // 应用最大分数限制
    if (selectedRule.max_score && score > selectedRule.max_score) {
      score = selectedRule.max_score
      console.log('应用最大分数限制:', score)
    }

    estimatedScore.value = parseFloat(score.toFixed(4))
    console.log('设置预估分数为:', estimatedScore.value)
  } finally {
    loading.score = false
  }
}

// 前端分数计算函数（与后端RuleEngine保持一致）
const calculateScoreFrontend = (rule) => {
  if (!rule || !rule.calculation) {
    // 如果没有计算配置，使用基础分数
    return rule.score || 0
  }

  let totalScore = 0

  // 根据计算类型执行不同的计算逻辑
  switch (rule.calculation.calculation_type) {
    case 'tree':
      // 树结构计算
      totalScore = calculateTreeScore(rule)
      break

    default:
      // 默认使用基础分数
      totalScore = rule.score || 0
  }

  return totalScore
}

// 计算树结构分数
const calculateTreeScore = (rule) => {
  // 验证规则和计算配置
  if (!rule || !rule.calculation) {
    return rule.score || 0
  }

  let parameters = rule.calculation.parameters || {}

  // 解析参数（可能是JSON字符串）
  if (typeof parameters === 'string') {
    try {
      parameters = JSON.parse(parameters)
    } catch (error) {
      console.error('解析参数失败:', error)
      return rule.score || 0
    }
  }

  // 获取树结构配置
  const treeConfig = parameters.tree || {}

  // 获取树结构
  const tree = treeConfig.structure || {}
  const rootNode = tree.root

  if (!rootNode) {
    return 0
  }

  // 获取分数配置
  let scores = treeConfig.scores || {}
  // 如果scores是字符串，尝试解析为JSON
  if (typeof scores === 'string') {
    try {
      scores = JSON.parse(scores)
    } catch (e) {
      scores = {}
    }
  }

  // 确保scores是对象
  if (typeof scores !== 'object' || scores === null) {
    scores = {}
  }

  // 获取完整的学生数据（与后端逻辑完全一致）
  const studentData = {
    ...formData.dynamicCoefficients,
    ...(authStore.user || {})
  }

  // 优先使用studentData中的tree_path字段（与后端逻辑一致）
  let treePath = studentData.tree_path
  let matchingPath = null

  if (treePath && Array.isArray(treePath) && treePath.length > 0) {
    matchingPath = treePath
  } else {
    // 如果没有tree_path字段，再回退到动态查找路径

    // 递归查找匹配路径（修复：确保找到最深层的匹配叶子节点）
    const findMatchingPath = (node, currentPath = []) => {
      // 获取当前节点的名称
      const nodeDimension = node.dimension || {}
      const nodeName = nodeDimension.name || node.name

      // 将当前节点添加到路径中
      const fullPath = [...currentPath, nodeName]

      // 如果是叶子节点，检查是否与studentData中的值匹配
      if (!node.children || node.children.length === 0) {
        // 检查当前叶子节点是否匹配
        let is_leaf_matched = false

        // 灵活匹配方式：检查是否有任何字段的值等于当前叶子节点名
        for (const key in studentData) {
          const value = studentData[key]
          if (value !== undefined && value !== null && value !== '') {
            if (String(value).trim() === nodeName.trim()) {
              is_leaf_matched = true
              break
            }
          }
        }

        // 如果叶子节点匹配，返回完整路径
        if (is_leaf_matched) {
          return fullPath
        } else {
          // 叶子节点不匹配，返回null
          return null
        }
      }

      // 用于存储找到的最长路径
      let longestPath = null

      // 遍历当前节点的所有子节点
      for (const child of node.children) {
        // 获取子节点的名称和键（兼容不同的节点结构）
        const childDimension = child.dimension || {}
        const childKey = childDimension.key || child.key
        const childName = childDimension.name || child.name

        // 检查当前子节点是否匹配
        let is_child_matched = false

        // 灵活匹配方式：检查是否有任何字段的值等于当前子节点名
        for (const key in studentData) {
          const value = studentData[key]
          if (value !== undefined && value !== null && value !== '') {
            if (String(value).trim() === childName.trim()) {
              is_child_matched = true
              break
            }
          }
        }

        // 传统匹配方式：使用节点自己的key来匹配student_data
        if (!is_child_matched && childKey && studentData.hasOwnProperty(childKey)) {
          const child_value = String(studentData[childKey])
          if (child_value.trim() === childName.trim()) {
            is_child_matched = true
          }
        }

        // 对于每个子节点，无论是否匹配，都尝试向下遍历
        // 这确保我们能找到最深层的匹配叶子节点
        const result = findMatchingPath(child, fullPath)

        // 如果找到匹配路径，且该路径比当前最长路径更长，则更新最长路径
        if (result) {
          if (!longestPath || result.length > longestPath.length) {
            longestPath = result
          }
        }
      }

      // 返回找到的最长匹配路径
      return longestPath
    }

    // 查找匹配路径
    matchingPath = findMatchingPath(rootNode)
  }

  if (!matchingPath) {
    console.log('没有找到匹配路径，返回0分')
    return 0
  }

  // 根据匹配路径找到对应的叶子节点，并获取其score属性
  let currentNode = rootNode

  // 跳过根节点（如果路径包含根节点的话）
  const pathToUse = matchingPath[0] === '根节点' ? matchingPath.slice(1) : matchingPath

  for (const nodeName of pathToUse) {
    if (currentNode?.children) {
      // 使用更宽松的匹配方式，忽略空格和大小写差异
      const nextNode = currentNode.children.find((child) => {
        const childName = child.dimension.name || ''
        return childName.trim() === nodeName.trim()
      })
      if (nextNode) {
        currentNode = nextNode
      } else {
        console.log('没有找到匹配的子节点:', nodeName)
        break
      }
    } else {
      console.log('当前节点没有子节点')
      break
    }
  }

  // 获取叶子节点的score属性
  const score = parseFloat(currentNode?.score || 0)

  // 应用最大值限制
  if (rule.calculation.max_score !== undefined) {
    const maxScore = parseFloat(rule.calculation.max_score)
    const finalScore = Math.min(score, maxScore)
    return finalScore
  }

  return score
}

// 刷新规则列表（清除缓存）
const refreshRules = () => {
  cachedRules.value = [] // 清除缓存
  fetchMatchingRules()
}

// 在组件挂载时自动刷新规则选择栏并加载系统设置
onMounted(() => {
  refreshRules()
  loadSystemSettings()
})

// 加载系统设置
const loadSystemSettings = async () => {
  try {
    const response = await api.getPublicSystemInfo()

    // 检查response是否存在
    if (response && response.data) {
      const settings = response.data

      // 将allowedFileTypes转换为数组，并保存原始字符串
      let allowedFileTypesArray = ['.pdf', '.jpg', '.jpeg', '.png']
      let allowedFileTypesString = '.pdf, .jpg, .jpeg, .png'

      if (settings.allowedFileTypes !== undefined && settings.allowedFileTypes !== null) {
        if (typeof settings.allowedFileTypes === 'string') {
          allowedFileTypesArray = settings.allowedFileTypes.split(',').map((ext) => ext.trim())
          allowedFileTypesString = settings.allowedFileTypes
        } else if (Array.isArray(settings.allowedFileTypes)) {
          allowedFileTypesArray = settings.allowedFileTypes
          allowedFileTypesString = settings.allowedFileTypes.join(', ')
        }
      }

      // 更新systemSettings
      systemSettings.value = {
        singleFileSizeLimit: settings.singleFileSizeLimit || 10,
        totalFileSizeLimit: settings.totalFileSizeLimit || 50,
        allowedFileTypes: allowedFileTypesArray,
        allowedFileTypesString: allowedFileTypesString
      }
    }
  } catch (error) {
    console.error('获取系统设置失败:', error)
    // 确保systemSettings始终有默认值
    systemSettings.value = {
      singleFileSizeLimit: 10,
      totalFileSizeLimit: 50,
      allowedFileTypes: ['.pdf', '.jpg', '.jpeg', '.png'],
      allowedFileTypesString: '.pdf, .jpg, .jpeg, .png'
    }
  }
}

// 原有方法保持不变...
const getFileIcon = (fileName) => {
  if (!fileName) {
    return ['fas', 'file-question']
  }
  const ext = fileName.split('.').pop().toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext)) {
    return ['fas', 'file-image']
  } else if (ext === 'pdf') {
    return ['fas', 'file-pdf']
  } else {
    return ['fas', 'file']
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const isImageFile = (fileName) => {
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
  const ext = fileName.split('.').pop().toLowerCase()
  return imageExtensions.includes(ext)
}

const triggerFileInput = () => {
  fileInput.value.click()
}

// 验证并添加文件的通用函数
const validateAndAddFiles = (files) => {
  // 检查总文件数量
  const totalLimit = systemSettings.value?.totalFileSizeLimit || 50
  const singleLimit = systemSettings.value?.singleFileSizeLimit || 10
  const allowedTypes = systemSettings.value?.allowedFileTypes || ['.pdf', '.jpg', '.jpeg', '.png']
  const fileCountLimit = systemSettings.value?.maxFileCount || 10 // 默认限制10个文件

  // 检查总文件数量
  const totalFiles = formData.files.length + files.length
  if (totalFiles > fileCountLimit) {
    toastStore.error(`文件数量超过${fileCountLimit}个限制`)
    return false
  }

  // 检查总文件大小
  const currentTotalSize = formData.files.reduce((total, file) => total + file.size, 0)
  let totalSizeWithNewFiles = currentTotalSize

  for (const file of files) {
    totalSizeWithNewFiles += file.size
  }

  if (totalSizeWithNewFiles > totalLimit * 1024 * 1024) {
    toastStore.error(`总文件大小超过${totalLimit}MB限制`)
    return false
  }

  // 检查单个文件大小和类型
  for (const file of files) {
    if (file.size > singleLimit * 1024 * 1024) {
      toastStore.error(`文件 ${file.name} 大小超过${singleLimit}MB限制`)
      continue
    }

    const fileExt = `.${file.name.split('.').pop().toLowerCase()}`
    if (!allowedTypes.includes(fileExt)) {
      toastStore.error(`文件 ${file.name} 类型不支持，仅支持${allowedTypes.join(', ')}格式`)
      continue
    }

    // 使用展开运算符创建新数组，确保响应式更新
    formData.files = [...formData.files, file]
  }

  return true
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  validateAndAddFiles(files)
  event.target.value = ''
}

const handleDrop = (event) => {
  event.preventDefault()
  const files = Array.from(event.dataTransfer.files)
  validateAndAddFiles(files)
}

const removeFile = (index) => {
  // 使用展开运算符创建新数组，确保响应式更新
  formData.files = formData.files.filter((_, i) => i !== index)
}

const previewFile = (file) => {
  // 检查是否是浏览器File对象（用于新上传的文件）
  if (file instanceof File) {
    if (isImageFile(file.name)) {
      const url = URL.createObjectURL(file)
      previewFileData.value = {
        name: file.name,
        url: url,
        file: file,
        size: file.size
      }
    } else {
      previewFileData.value = {
        name: file.name,
        file: file,
        size: file.size
      }
    }
  } else {
    // 从后端获取的文件对象，通常包含id、name、path等字段
    // 对于后端图片文件，构建正确的预览URL
    let url = null
    if (isImageFile(file.name)) {
      if (file.path) {
        // 使用getFileFullUrl函数确保路径正确
        url = getFileFullUrl(file.path)
      } else if (file.id) {
        // 如果没有path字段，使用文件ID构建URL
        url = getFileFullUrl(`/uploads/files/${file.id}`)
      }
    }
    previewFileData.value = {
      name: file.name,
      url: url,
      file: file,
      size: file.size || 0
    }
  }
}

const closePreview = () => {
  if (previewFileData.value && previewFileData.value.url) {
    URL.revokeObjectURL(previewFileData.value.url)
  }
  previewFileData.value = null
}

// 获取applicationType的通用函数
const getApplicationType = () => {
  let applicationType = formData.applicationType
  if (!applicationType && formData.ruleId) {
    const selectedRule = availableRules.value.find((rule) => rule.id === formData.ruleId)
    if (selectedRule && selectedRule.type) {
      applicationType = selectedRule.type
      // 将获取到的applicationType保存回formData，确保提交时包含该字段
      formData.applicationType = applicationType
    }
  }
  return applicationType
}

// 获取学生信息的通用函数
const getStudentInfo = () => {
  return {
    studentName: authStore.user?.name || authStore.userName || '未知学生',
    studentId: authStore.user?.studentId || '未知学号',
    facultyId: authStore.user?.facultyId || authStore.user?.faculty_id || '',
    departmentId: authStore.user?.departmentId || authStore.user?.department_id || '',
    majorId: authStore.user?.majorId || authStore.user?.major_id || ''
  }
}

// 定义后端到前端的字段映射
const backToFrontMappings = {
  student_id: 'studentId',
  faculty_id: 'facultyId',
  department_id: 'departmentId',
  major_id: 'majorId',
  project_name: 'projectName',
  award_date: 'awardDate',
  rule_id: 'ruleId',
  self_score: 'selfScore',
  final_score: 'finalScore',
  applied_at: 'appliedAt',
  created_at: 'createdAt',
  updated_at: 'updatedAt',
  application_type: 'applicationType',
  dynamic_coefficients: 'dynamicCoefficients'
}

// 将后端字段名转换为前端字段名
const toFrontendFields = (data) => {
  const result = { ...data }
  Object.keys(backToFrontMappings).forEach((backKey) => {
    const frontKey = backToFrontMappings[backKey]
    if (result.hasOwnProperty(backKey)) {
      result[frontKey] = result[backKey]
      delete result[backKey]
    }
  })
  return result
}

// 准备申请数据的通用函数
const prepareApplicationData = (status) => {
  const { studentName, studentId, facultyId, departmentId, majorId } = getStudentInfo()
  const applicationType = getApplicationType()

  // 处理动态系数，将树结构字段转换为后端期望的格式
  const processedCoefficients = {}

  // 第一步：直接将所有树结构字段转换为路径数组，总是使用'tree_path'作为键名
  // 这样后端可以统一处理所有规则的树路径
  const treePathValues = []

  // 找出所有树结构字段并按索引排序
  const treeFieldKeys = Object.keys(formData.dynamicCoefficients)
    .filter((key) => /.*?_(\d+)$/.test(key))
    .sort((a, b) => {
      const indexA = parseInt(a.match(/.*?_(\d+)$/)[1])
      const indexB = parseInt(b.match(/.*?_(\d+)$/)[1])
      return indexA - indexB
    })

  // 提取树路径值
  for (const key of treeFieldKeys) {
    const value = formData.dynamicCoefficients[key]
    if (value !== undefined && value !== null && value !== '') {
      treePathValues.push(value)
    }
  }

  // 保存树路径到固定的'tree_path'字段
  if (treePathValues.length > 0) {
    processedCoefficients.tree_path = treePathValues
  }

  // 复制所有非树结构字段
  for (const [key, value] of Object.entries(formData.dynamicCoefficients)) {
    // 跳过树结构字段（带索引的字段）
    if (!/(.*?)_(\d+)$/.test(key)) {
      processedCoefficients[key] = value
    }
  }

  // 创建清理后的表单数据
  const cleanedFormData = {
    ...formData,
    dynamicCoefficients: processedCoefficients
  }

  return {
    ...cleanedFormData,
    // 确保使用正确的字段名，与后端期望保持一致
    studentName,
    studentId,
    facultyId,
    departmentId,
    majorId,
    status,
    appliedAt: new Date().toISOString(),
    applicationType
  }
}

// 修改保存草稿和提交表单的验证逻辑
const saveDraft = async () => {
  try {
    if (!formData.applicationType) {
      notifyProjectTypeRequired()
      return
    }
    // 验证项目名称长度
    if (!formData.projectName || formData.projectName.length < 2) {
      toastStore.error('项目全称不能少于2个字符')
      return
    }
    if (formData.projectName.length > 30) {
      toastStore.error('项目全称不能超过30个字符')
      return
    }
    syncRuleForProjectType()

    // 获取学生信息和applicationType
    const { studentName, studentId, facultyId, departmentId, majorId } = getStudentInfo()
    const applicationType = getApplicationType()

    // 准备草稿数据
    const draftData = prepareApplicationData('draft')

    let success
    let newAppId
    if (formData.id) {
      // 更新现有申请
      success = await applicationsStore.updateApplication(formData.id, draftData)
      newAppId = formData.id
    } else {
      // 创建新申请
      const result = await applicationsStore.addApplication(draftData)
      if (result) {
        newAppId = result
        success = true
      } else {
        success = false
      }
    }

    if (success && newAppId) {
      toastStore.success('草稿已保存')
      // 保存成功后重新加载最新数据
      await loadEditData(newAppId)
      // 重新计算预估分数
      calculateEstimatedScore()
    } else {
      toastStore.error('保存草稿失败，请稍后重试')
    }
  } catch (error) {
    console.error('保存草稿失败:', error)
    toastStore.error('保存草稿失败，请稍后重试')
  }
}

const submitForm = async () => {
  // 通用验证
  if (!formData.applicationType) {
    notifyProjectTypeRequired()
    return
  }
  if (!formData.projectName) {
    toastStore.error('请输入项目全称')
    return
  }
  if (formData.projectName.length < 2) {
    toastStore.error('项目全称不能少于2个字符')
    return
  }
  if (formData.projectName.length > 30) {
    toastStore.error('项目全称不能超过30个字符')
    return
  }

  if (!formData.awardDate) {
    toastStore.error('请输入获得时间')
    return
  }

  // 被精简掉的规则与计分字段由项目类型自动派生，仅用于兼容原提交接口。
  syncRuleForProjectType()

  if (formData.files.length === 0) {
    toastStore.error('请上传证明文件')
    return
  }

  // 获取学生信息和applicationType
  const { studentName, studentId, facultyId, departmentId, majorId } = getStudentInfo()
  const applicationType = getApplicationType()

  // 确保studentName字段存在（兼容后端期望）
  formData.studentName = formData.name || authStore.userName

  // 准备申请数据
  const applicationData = prepareApplicationData('pending')

  try {
    let success
    if (formData.id) {
      // 更新现有申请
      success = await applicationsStore.updateApplication(formData.id, applicationData)
    } else {
      // 创建新申请
      success = await applicationsStore.addApplication(applicationData)
    }

    if (success) {
      toastStore.success('申请已提交，等待审核中...')

      // 重置表单
      resetForm()

      // 重置规则列表和预估分数
      availableRules.value = []
      estimatedScore.value = 0

      // 不再自动切换到申请历史页面，保持在加分申请页面
    } else {
      toastStore.error('提交失败，请稍后重试')
    }
  } catch (error) {
    console.error('提交申请失败:', error)
    toastStore.error('提交失败，请稍后重试')
  }
}
</script>

<style scoped src="@/assets/styles/pages/student/applications/ApplicationForm.css"></style>
