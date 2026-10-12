<template>
  <div v-if="visible" class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop="handleModalContentClick">
      <div class="modal-header">
        <h3>{{ editingRule ? '编辑规则' : '添加规则' }}</h3>
        <button class="close-btn" @click="$emit('close')">
          <font-awesome-icon :icon="['fas', 'times']" />
        </button>
      </div>
      <div class="modal-body">
        <form @submit.prevent="handleSave">
          <!-- 两列布局容器 -->
          <div class="form-layout">
            <!-- 左侧容器：基本信息、规则配置、规则说明 -->
            <div class="form-layout-left">
              <!-- 基本信息卡片 -->
              <div class="card">
                <div class="card-title">基本信息</div>
                <div class="card-body">
                  <div class="form-group">
                    <label class="form-label">规则名称</label>
                    <input type="text" class="form-control" v-model="ruleForm.name" required>
                  </div>

                  <!-- 规则类型（卡片式选择） -->
                  <div class="form-group">
                    <label class="form-label">规则类型</label>
                    <div class="radio-cards compact">
                      <div class="radio-card" :class="{ active: ruleForm.type === 'academic' }"
                        @click.stop="handleTypeChange('academic')">
                        <div class="radio-icon">
                          <font-awesome-icon :icon="['fas', 'book']" />
                        </div>
                        <span>学术专长</span>
                      </div>
                      <div class="radio-card" :class="{ active: ruleForm.type === 'comprehensive' }"
                        @click.stop="handleTypeChange('comprehensive')">
                        <div class="radio-icon">
                          <font-awesome-icon :icon="['fas', 'trophy']" />
                        </div>
                        <span>综合表现</span>
                      </div>
                    </div>
                  </div>

                  <!-- 规则子类型（卡片式选择） -->
                  <div class="form-group" v-if="ruleForm.type">
                    <label class="form-label">具体类型</label>
                    <div class="radio-cards">
                      <div class="radio-card" v-for="type in currentSubTypes" :key="type.value"
                        :class="{ active: ruleForm.sub_type === type.value }"
                        @click.stop="ruleForm.sub_type = type.value; handleSubTypeChange()">
                        <div class="radio-icon">
                          <font-awesome-icon :icon="type.icon" />
                        </div>
                        <span>{{ type.label }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- 科研成果类型选择（只有科研成果需要） -->
                  <div class="form-group" v-if="ruleForm.type === 'academic' && ruleForm.sub_type === 'research'">
                    <label class="form-label">科研成果种类</label>
                    <div class="radio-cards compact">
                      <div class="radio-card small" :class="{ active: ruleForm.research_type === 'paper' }"
                        @click.stop="ruleForm.research_type = 'paper'">
                        <div class="radio-icon">
                          <font-awesome-icon :icon="['fas', 'file-alt']" />
                        </div>
                        <span>学术论文</span>
                      </div>
                      <div class="radio-card small" :class="{ active: ruleForm.research_type === 'patent' }"
                        @click.stop="ruleForm.research_type = 'patent'">
                        <div class="radio-icon">
                          <font-awesome-icon :icon="['fas', 'file-invoice']" />
                        </div>
                        <span>发明专利</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 规则配置卡片 -->
              <div class="card">
                <div class="card-title">规则配置</div>
                <div class="card-body">

                  <div class="form-row">
                    <!-- 最大分数限制（可选） -->
                    <div class="form-group">
                      <label class="form-label">最高分数</label>
                      <input type="number" class="form-control" v-model="ruleForm.max_score" step="0.1" min="0"
                        placeholder="请输入最大分数限制（留空表示无限制）">
                    </div>

                    <!-- 最大项目数量限制（可选） -->
                    <div class="form-group">
                      <label class="form-label">最多项目数</label>
                      <input type="number" class="form-control" v-model="ruleForm.max_count" min="1"
                        placeholder="请输入最大项目数量（留空表示无限制）">
                    </div>
                  </div>

                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label">学院</label>
                      <select class="form-control" v-model="ruleForm.faculty_id">
                        <option value="">全部学院</option>
                        <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">{{ faculty.name }}
                        </option>
                      </select>
                    </div>
                    <div class="form-group">
                      <label class="form-label">默认分数</label>
                      <input type="number" class="form-control" v-model="ruleForm.score" step="0.1" min="0" max="30"
                        required>
                      <div class="help-text">当计分方式无法计算时，系统将使用此分数</div>
                    </div>
                    <div class="form-group">
                      <label class="form-label">状态</label>
                      <select class="form-control" v-model="ruleForm.status" required>
                        <option value="active">启用</option>
                        <option value="disabled">禁用</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
              <!-- 规则说明卡片 -->
              <div class="card">
                <div class="card-title">规则说明</div>
                <div class="card-body">
                  <div class="form-group">
                    <textarea class="form-control" v-model="ruleForm.description" rows="3"
                      placeholder="请输入规则详细描述"></textarea>
                  </div>
                </div>
              </div>
            </div>

            <!-- 右侧容器：计算规则 -->
            <div class="form-layout-right">
              <!-- 计算规则卡片 -->
              <div class="card">
                <div class="card-title">计算规则</div>
                <div class="card-body">

                  <!-- 计分方式设置 -->
                  <div class="json-formula-config">
                    <div class="form-group">
                      <label class="form-label">计分方式</label>
                      <div class="radio-cards">
                        <div class="radio-card horizontal" :class="{ active: jsonFormulaConfig.type === 'tree' }"
                          @click="jsonFormulaConfig.type = 'tree'">
                          <div class="radio-icon">
                            <font-awesome-icon :icon="['fas', 'tree']" />
                          </div>
                          <span>树结构计算</span>
                        </div>
                      </div>
                    </div>

                    <!-- 树结构计算配置 -->
                    <div v-if="jsonFormulaConfig.type === 'tree'" class="tree-config">
                      <div class="help-text">
                        树结构计算支持层级化的计分配置，适用于复杂的评分场景。
                        <br>计算方式：根据树结构的节点组合应用对应分数，绿色标记的节点分数即表示不同组合下的分数。
                        <br>
                        <br>点击节点可进入编辑状态，修改节点名称和分数。可以使用Enter键保存，或Esc键取消编辑，也可以再次点击节点退出编辑状态并保存。
                      </div>

                      <!-- 树结构配置 -->
                      <div v-if="jsonFormulaConfig.tree.mode === 'tree'" class="tree-config">
                        <h4>树结构配置</h4>
                        <div class="tree-config-container">
                          <!-- 树可视化区域 -->
                          <div class="tree-visualization">
                            <!-- 根节点 -->
                            <div v-if="treeData.root" class="tree-root">
                              <tree-node :node="treeData.root" :level="0" :selected-node-id="selectedNodeId"
                                @node-select="handleNodeSelect" @add-child="handleAddChild"
                                @delete-node="handleDeleteNode" @update-node="handleUpdateNode"
                                @edit-start="handleEditStart" @edit-end="handleEditEnd"
                                :get-node-path="getNodePath" />
                            </div>
                            <div v-else class="tree-empty">
                              <p>树结构为空，请添加根节点</p>
                              <button type="button" class="btn btn-primary" @click="initializeTree">
                                <font-awesome-icon icon="tree" /> 初始化树结构
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="form-actions">
            <button type="button" class="btn btn-outline" @click="$emit('close')">取消</button>
            <button type="submit" class="btn">保存</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted, onUnmounted } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { useAuthStore } from '../../stores/auth'

// 属性
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  editingRule: {
    type: Object,
    default: null
  },

  faculties: {
    type: Array,
    default: () => []
  },
  allRules: {
    type: Array,
    default: () => []
  }
})

// 事件
const emit = defineEmits(['close', 'save'])

// 认证存储
const authStore = useAuthStore()

// 表单数据
const ruleForm = reactive({
  name: '',
  type: '',
  sub_type: '',
  research_type: '',
  max_score: null,
  max_count: null,
  faculty_id: '',
  score: 0,

  calculation_formula: null,
  status: 'active',
  description: ''
})

// 公式配置 - 支持树结构计算
const jsonFormulaConfig = reactive({
  type: 'tree',
  // 树结构计算配置
  tree: {
    mode: 'tree', // 'tree'
    // 树结构配置 - 简单默认值，实际使用时会被覆盖或初始化
    structure: {
      root: {
        id: 'root',
        dimension: { name: '根节点', key: 'root' },
        value: 'root',
        children: []
      }
    }
  }
})

// 树节点组件
// 导入TreeNode组件
import TreeNode from './TreeNode.vue'

// 树结构管理逻辑
// 生成唯一节点ID
function generateNodeId() {
  return `node_${Date.now()}_${Math.floor(Math.random() * 1000)}`
}

// 计算树数据
const treeData = computed(() => {
  if (jsonFormulaConfig.tree.structure && jsonFormulaConfig.tree.structure.root) {
    return jsonFormulaConfig.tree.structure
  }
  return { root: null }
})

// 选中节点管理
const selectedNodeId = ref(null)
const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  return findNodeById(treeData.value.root, selectedNodeId.value)
})

// 正在编辑的节点ID数组
const editingNodeIds = ref([])

// 查找节点函数
function findNodeById(node, id) {
  if (!node) return null
  if (node.id === id) return node
  for (const child of node.children || []) {
    const found = findNodeById(child, id)
    if (found) return found
  }
  return null
}

// 处理节点编辑开始事件
function handleEditStart(nodeId) {
  // 将节点ID添加到正在编辑的节点数组中
  if (!editingNodeIds.value.includes(nodeId)) {
    editingNodeIds.value.push(nodeId)
  }
}

// 处理节点编辑结束事件
function handleEditEnd(nodeId) {
  // 将节点ID从正在编辑的节点数组中移除
  editingNodeIds.value = editingNodeIds.value.filter(id => id !== nodeId)
}

// 处理模态框内容点击事件，点击编辑框外部关闭编辑框
function handleModalContentClick(event) {
  if (selectedNodeId.value) {
    // 忽略对树节点的点击
    const treeNodeElement = event.target.closest('.tree-node')
    if (treeNodeElement) {
      return
    }

    // 点击树节点外部时取消节点选择
    selectedNodeId.value = null
  }
}

// 节点操作函数

// 处理节点选择
function handleNodeSelect(nodeId) {
  selectedNodeId.value = nodeId
}

// 处理添加子节点
function handleAddChild(parent) {
  const parentNode = typeof parent === 'object' ? parent : findNodeById(treeData.value.root, parent)
  if (!parentNode) return

  const nodeName = '新维度'
  // 根据名称生成默认键值：转换为小写，空格替换为下划线，删除特殊字符
  const nodeKey = nodeName.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')

  const newNode = {
    id: generateNodeId(),
    dimension: {
      name: nodeName,
      key: nodeKey
    },
    value: nodeName,
    children: [],
    score: 0
  }

  if (!parentNode.children) parentNode.children = []
  parentNode.children.push(newNode)

  // 自动展开父节点
  parentNode.expanded = true

  // 选中新节点并更新编辑面板位置
  handleNodeSelect(newNode.id)
}

// 处理删除节点
function handleDeleteNode(node) {
  const nodeToDelete = typeof node === 'object' ? node : findNodeById(treeData.value.root, node)
  if (!nodeToDelete || nodeToDelete.id === 'root') return
  if (!nodeToDelete) return

  function findParent(currentNode, targetNode) {
    if (!currentNode || !currentNode.children) return null
    if (currentNode.children.some(child => child.id === targetNode.id)) {
      return currentNode
    }
    for (const child of currentNode.children) {
      const result = findParent(child, targetNode)
      if (result) return result
    }
    return null
  }

  const parent = findParent(treeData.value.root, nodeToDelete)
  if (parent) {
    parent.children = parent.children.filter(child => child.id !== nodeToDelete.id)
    if (selectedNodeId.value === nodeToDelete.id) {
      selectedNodeId.value = null
    }
  }
}

// 更新节点
function handleUpdateNode(updatedNode) {
  const node = findNodeById(treeData.value.root, updatedNode.id)
  if (node) {
    // 深度更新节点属性
    node.score = updatedNode.score
    node.value = updatedNode.value
    // 特殊处理dimension对象的更新
    if (updatedNode.dimension && node.dimension) {
      Object.assign(node.dimension, updatedNode.dimension)
    }
  }
}

// 初始化树结构
function initializeTree() {
  if (!jsonFormulaConfig.tree) jsonFormulaConfig.tree = {}
  if (!jsonFormulaConfig.tree.structure) jsonFormulaConfig.tree.structure = {}

  jsonFormulaConfig.tree.structure.root = {
    id: 'root',
    dimension: {
      name: '根节点',
      key: 'root'
    },
    value: '根节点',
    children: [],
    score: 0
  }
  // 初始选中根节点
  selectedNodeId.value = 'root'
}

// 获取节点路径
function getNodePath(node) {
  function findPath(currentNode, targetNode, path = []) {
    if (!currentNode) return null

    const currentPath = [...path, currentNode.dimension ? currentNode.dimension.name : '']

    if (currentNode.id === targetNode.id) {
      return currentPath
    }

    for (const child of currentNode.children) {
      const result = findPath(child, targetNode, currentPath)
      if (result) return result
    }

    return null
  }

  const path = findPath(jsonFormulaConfig.tree.structure.root, node)
  return path ? path.join(' → ') : ''
}

// 监听编辑规则的变化
watch(() => props.editingRule, (newRule) => {
  if (newRule) {
    // 分配基本规则数据
    Object.assign(ruleForm, newRule)

    // 处理计算设置
    if (newRule.calculation) {
      // 设置计算类型为tree（仅支持树结构计算）
      jsonFormulaConfig.type = 'tree'

      // 从计算参数中复制配置
      if (newRule.calculation.parameters) {
        // 设置树结构配置
        if (newRule.calculation.parameters.tree) {
          // 确保树结构模式
          jsonFormulaConfig.tree.mode = 'tree'
          // 复制树结构数据
          if (newRule.calculation.parameters.tree.structure) {
            jsonFormulaConfig.tree.structure = newRule.calculation.parameters.tree.structure
          }
        } else {
          // 如果没有树结构配置，创建默认配置
          jsonFormulaConfig.tree.structure = {
            root: {
              id: 'root',
              dimension: { name: '根节点', key: 'root' },
              value: 'root',
              children: []
            }
          }
        }

        // 如果存在，从计算参数设置最大分数和最大数量
        if (newRule.calculation.parameters.max_score) {
          ruleForm.max_score = newRule.calculation.parameters.max_score
        }
        if (newRule.calculation.parameters.max_count) {
          ruleForm.max_count = newRule.calculation.parameters.max_count
        }
      }
    } else {
      // 默认JSON公式配置 - 仅支持树结构计算
      jsonFormulaConfig.type = 'tree'
    }
  } else {
    // 重置表单
    // 获取管理员所在学院ID
    const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    
    Object.assign(ruleForm, {
      name: '',
      type: '',
      sub_type: '',
      research_type: '',
      max_score: null,
      max_count: null,
      faculty_id: adminFacultyId || '',
      score: 0,
      calculation_formula: null,
      status: 'active',
      description: ''
    })

    // 重置公式配置
    Object.assign(jsonFormulaConfig, {
      type: 'tree',
      // 树结构计算配置
      tree: {
        mode: 'tree',
        // 树结构配置
        structure: {
          root: {
            id: 'root',
            dimension: { name: '根节点', key: 'root' },
            value: 'root',
            children: []
          }
        }
      }
    })
  }
}, { immediate: true })

// 监听visible属性的变化
watch(() => props.visible, (newVisible) => {
  if (!newVisible) {
    // 当模态框关闭时重置表单
  }
})

// 根据所选类型的规则子类型
const currentSubTypes = computed(() => {
  if (ruleForm.type === 'academic') {
    return [
      { value: 'competition', label: '学术竞赛', icon: ['fas', 'trophy'] },
      { value: 'research', label: '科研成果', icon: ['fas', 'microscope'] },
      { value: 'innovation', label: '创新创业', icon: ['fas', 'lightbulb'] }
    ]
  } else if (ruleForm.type === 'comprehensive') {
    return [
      { value: 'volunteer', label: '志愿服务', icon: ['fas', 'hand-holding-heart'] },
      { value: 'sports', label: '体育竞赛', icon: ['fas', 'futbol'] },
      { value: 'international_internship', label: '国际组织实习', icon: ['fas', 'globe'] },
      { value: 'military_service', label: '参军入伍', icon: ['fas', 'shield'] },

      { value: 'honor_title', label: '荣誉称号', icon: ['fas', 'medal'] },
      { value: 'social_work', label: '社会工作', icon: ['fas', 'users-cog'] }
    ]
  }
  return []
})

// 计算最大分数（用于限制输入）
const maxScore = computed(() => {
  return parseFloat(ruleForm.max_score) || 100
})

// 处理类型变化
const handleTypeChange = (type) => {
  ruleForm.type = type
  ruleForm.sub_type = ''
  ruleForm.research_type = ''
  // 重置其他类型特定字段
}

// 处理子类型变化
const handleSubTypeChange = () => {
  if (ruleForm.sub_type !== 'research') {
    ruleForm.research_type = ''
  }
  // 重置其他子类型特定字段
}

// 为后端准备计算数据 - 支持多种计算类型
const prepareCalculationData = () => {
  // 根据选择的计算类型准备参数
  let params = {
    base_score: ruleForm.score,
    max_count: ruleForm.max_count
  }

  // 树结构计算配置
  params.tree = jsonFormulaConfig.tree
  // 确保模式为tree
  params.tree.mode = 'tree'

  return {
    calculation_type: 'tree', // 仅支持tree类型
    formula: null,
    parameters: params,
    max_score: ruleForm.max_score
  }
}

// 强制保存所有正在编辑的节点
const forceSaveAllNodes = () => {
  // 简单而有效的方法：取消当前选中状态，触发保存
  if (selectedNodeId.value) {
    // 保存当前选中节点
    const currentNode = findNodeById(treeData.value.root, selectedNodeId.value)
    if (currentNode) {
      // 确保节点数据有效
      if (!currentNode.dimension) {
        currentNode.dimension = { name: '未命名节点', key: 'unnamed' }
      }
      if (currentNode.score === undefined || currentNode.score === null) {
        currentNode.score = 0
      }
    }
    // 取消选中状态
    selectedNodeId.value = null
  }
  
  // 如果有正在编辑的节点，触发点击外部事件
  if (editingNodeIds.value.length > 0) {
    // 创建一个临时元素来模拟点击，确保event.target是Element对象
    const tempElement = document.createElement('div')
    tempElement.style.position = 'absolute'
    tempElement.style.left = '-9999px'
    document.body.appendChild(tempElement)
    
    // 发送点击事件到临时元素
    const event = new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      view: window,
      target: tempElement
    })
    tempElement.dispatchEvent(event)
    
    // 清理临时元素
    document.body.removeChild(tempElement)
  }
}

// 处理表单提交
const handleSave = () => {
  // 强制保存所有正在编辑的节点
  forceSaveAllNodes()
  
  // 准备规则数据
  const ruleData = {
    ...ruleForm,
    // 将空字符串转换为null（对于可能为null的字段）
    faculty_id: ruleForm.faculty_id === '' ? null : ruleForm.faculty_id,
    research_type: ruleForm.research_type === '' ? null : ruleForm.research_type,
    // 添加嵌套字段
    calculation: prepareCalculationData()
  }

  // 对于非科研类型，清空科研类型字段
  if (!(ruleData.type === 'academic' && ruleData.sub_type === 'research')) {
    ruleData.research_type = null
  }

  // 发送保存事件并携带规则数据
  emit('save', ruleData)
}
</script>

<style scoped>
/* 引入共享样式 */
@import '../common/shared-styles.css';

/* 模态框样式 */
.modal-content {
  max-width: 1200px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
}

/* 表单布局 */
.form-layout {
  display: flex;
  gap: 25px;
  margin-bottom: 20px;
}

.form-layout-left {
  flex: 1;
  width: 50%;
}

.form-layout-right {
  flex: 1;
  width: 50%;
}

/* 组件特定表单样式 */
.form-layout-left .form-row,
.form-layout-right :not(.json-formula-config) .form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
  align-items: flex-start;
}

.form-layout-left .form-row .form-group,
.form-layout-right :not(.json-formula-config) .form-row .form-group {
  flex: 1;
  margin-bottom: 0;
}

/* 公式配置 */
.json-formula-config {
  margin-top: 15px;
}

/* 系数配置 */
.coefficient-type-group {
  position: relative;
  background-color: #f9f9f9;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  padding: 15px;
  margin-bottom: 20px;
}

.grade-config-item {
  margin-bottom: 15px;
  padding: 10px;
  background: #fff;
  border: 1px solid #eee;
  border-radius: 4px;
}

/* 系数行布局 */
.coefficient-type-group .grade-config-item {
  margin-bottom: 10px;
}

.coefficient-type-group .grade-config-item .coefficient-row {
  display: flex;
  align-items: center;
  gap: 15px;
  width: 100%;
  margin-bottom: 0px;
}

.coefficient-type-group .grade-config-item .coefficient-row .form-group {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  flex: 1;
  margin-bottom: 0;
}

.coefficient-type-group .grade-config-item .coefficient-row .form-group .form-label {
  display: inline-block;
  white-space: nowrap;
  min-width: 36px;
  margin-bottom: 0;
  font-weight: 500;
  color: #555;
}

.coefficient-type-group .grade-config-item .coefficient-row .form-group .form-control {
  flex: 1;
}

/* 删除按钮 */
.delete-btn {
  position: absolute;
  top: 10px;
  right: 10px;
}

/* 树结构计算样式 */
.tree-config {
  margin-top: 15px;
}

/* 树结构容器 */
.tree-config-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
  background-color: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.tree-visualization {
  position: relative;
  min-height: 200px;
  max-height: 600px;
  overflow-y: auto;
  padding: 20px;
  background-color: #f9fafb;
  border-radius: 6px;
}

.tree-root {
  display: flex;
  justify-content: center;
  margin-bottom: 40px;
}

.tree-empty {
  text-align: center;
  padding: 40px 20px;
  color: #9ca3af;
}

.tree-empty p {
  margin-bottom: 20px;
}

.node-path {
  padding: 8px 12px;
  background-color: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 12px;
  color: #6b7280;
  word-break: break-all;
  font-family: monospace;
}

.node-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid #e0e0e0;
}

.node-actions .btn {
  flex: 1;
  font-size: 14px;
  padding: 8px 12px;
}

/* 树结构行布局 */
.tree-row {
  display: flex;
  margin-bottom: 5px;
}

.tree-cell {
  margin-right: 10px;
  padding: 5px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #f9f9f9;
  min-width: 100px;
  text-align: center;
}

/* 响应式设计 */
@media (max-width: 992px) {
  .form-layout {
    flex-direction: column;
    gap: 20px;
  }

  .form-layout-left,
  .form-layout-right {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .form-row {
    flex-direction: column;
    gap: 15px;
  }

  .form-row .form-group {
    width: 100%;
  }

  .radio-card {
    min-width: calc(50% - 8px);
  }

  .radio-card.horizontal {
    min-width: 120px;
  }
}

@media (max-width: 576px) {
  .radio-card {
    min-width: 100%;
  }

  .coefficient-type-group {
    padding: 12px;
  }
}
</style>