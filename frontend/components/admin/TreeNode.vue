<template>
  <div class="tree-node" :class="{ expanded: node.expanded }">
    <!-- 节点内容 -->
    <div 
      class="node-content"
      :class="{ 
        selected: node.id === selectedNodeId,
        leaf: !node.children || node.children.length === 0,
        editing: isEditing
      }"
      @click="handleNodeContentClick"
      ref="nodeContentRef"
      :title="getNodePath ? getNodePath(node) : ''"
    >
      <!-- 展开/折叠按钮 -->
      <button 
        v-if="node.children && node.children.length > 0"
        type="button"
        class="node-toggle"
        @click.stop="toggleExpand"
        :title="node.expanded ? '折叠' : '展开'"
      >
        <font-awesome-icon :icon="node.expanded ? 'chevron-down' : 'chevron-right'" />
      </button>
      
      <!-- 节点信息 - 统一样式的内联编辑 -->
      <div class="node-info" ref="nodeInfoRef">
          <div class="node-name">
            <template v-if="isEditing">
              <input 
                type="text" 
                class="node-name-input"
                v-model="editName"
                @input="updateNodeName"
                placeholder="节点名称"
                ref="nameInputRef"
                @keydown.enter.prevent.stop="focusScoreInput"
                @keydown.esc.prevent.stop="handleEscKey"
                @click.stop
              >
            </template>
            <template v-else>
              {{ node.dimension.name }}
            </template>
          </div>
          <div class="node-meta">
            <span class="node-score">
              分数: 
              <template v-if="isEditing">
                <input 
                  type="number" 
                  class="node-score-input"
                  v-model="editScore"
                  @input="updateNodeScore"
                  step="0.1"
                  min="0"
                  placeholder="0"
                  ref="scoreInputRef"
                  @keydown.enter.prevent.stop="saveEdit"
                  @keydown.esc.prevent.stop="handleEscKey"
                  @click.stop
                >
              </template>
              <template v-else>
                {{ node.score }}
              </template>
            </span>
          </div>
      </div>
      
      <!-- 节点操作 -->
      <div class="node-actions">
        <!-- 查看模式操作按钮 -->
        <template v-if="!isEditing">
          <button 
            type="button" 
            class="btn-icon"
            @click.stop="$emit('add-child', node)"
            title="添加子节点"
          >
            <font-awesome-icon icon="plus" />
          </button>
          <button 
            v-if="node.id !== 'root'"
            type="button" 
            class="btn-icon"
            @click.stop="$emit('delete-node', node)"
            title="删除节点"
          >
            <font-awesome-icon icon="trash" />
          </button>
        </template>
      </div>
    </div>
    
    <!-- 子节点 -->
    <div v-if="node.expanded && node.children && node.children.length > 0" class="node-children">
      <tree-node
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :level="level + 1"
        :selected-node-id="selectedNodeId"
        :get-node-path="getNodePath"
        @node-select="$emit('node-select', $event)"
        @add-child="$emit('add-child', $event)"
        @delete-node="$emit('delete-node', $event)"
        @update-node="$emit('update-node', $event)"
        @edit-start="$emit('edit-start', $event)"
        @edit-end="$emit('edit-end', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  level: {
    type: Number,
    default: 0
  },
  selectedNodeId: {
    type: String,
    default: null
  },
  getNodePath: {
    type: Function,
    default: null
  }
})

const emit = defineEmits(['node-select', 'add-child', 'delete-node', 'update-node', 'edit-start', 'edit-end'])

// 编辑状态
const isEditing = ref(false)
const editName = ref('')
const editScore = ref(0)
const nodeContentRef = ref(null)
const nodeInfoRef = ref(null)
const nameInputRef = ref(null)
const scoreInputRef = ref(null)

// 原始值，用于取消编辑时恢复
const originalName = ref('')
const originalScore = ref(0)

// 初始化编辑数据
watch(() => props.node, (newNode) => {
  if (newNode) {
    editName.value = newNode.dimension?.name || ''
    editScore.value = newNode.score || 0
  }
}, { immediate: true, deep: true })

// 进入编辑模式或保存编辑
function enterEditMode() {
  if (isEditing.value) {
    // 当前已在编辑模式，退出并保存
    saveEdit()
  } else {
    // 当前不在编辑模式，进入编辑
    // 保存原始值用于取消编辑
    originalName.value = props.node.dimension?.name || ''
    originalScore.value = props.node.score || 0
    
    isEditing.value = true
    editName.value = props.node.dimension?.name || ''
    editScore.value = props.node.score || 0
    
    // 向父组件发送编辑开始事件
    emit('edit-start', props.node.id)
    
    // 延迟聚焦到名称输入框
    setTimeout(() => {
      if (nameInputRef.value) {
        nameInputRef.value.focus()
        nameInputRef.value.select()
      }
    }, 100)
    
    // 添加全局点击监听器
    document.addEventListener('click', handleClickOutside)
  }
}

// 处理节点内容区域点击
function handleNodeContentClick() {
  // 点击整个节点内容区域都触发编辑状态切换
  enterEditMode()
}

// 名称输入框回车后聚焦到分数输入框
function focusScoreInput() {
  // 使用setTimeout确保DOM更新后再聚焦
  setTimeout(() => {
    if (scoreInputRef.value) {
      scoreInputRef.value.focus()
      scoreInputRef.value.select()
    }
  }, 0)
}

// 处理外部点击事件
function handleClickOutside(event) {
  // 使用ref直接引用DOM元素
  if (isEditing.value && nodeContentRef.value) {
    // 检查点击是否在节点内容区域之外
    if (!nodeContentRef.value.contains(event.target)) {
      // 检查点击是否是保存按钮（确保event.target是Element对象）
      let saveButton = null
      if (event.target instanceof Element) {
        saveButton = event.target.closest('button[type="submit"]') || event.target.closest('.btn-primary')
      }
      
      // 无论是点击外部区域还是保存按钮，都保存并退出编辑
      saveEdit()
    }
  }
}

// 更新节点名称
function updateNodeName() {
  // 只在内部更新编辑值，不实时发送更新事件
  // 保存时才统一发送更新
}

// 更新节点分数
function updateNodeScore() {
  // 只在内部更新编辑值，不实时发送更新事件
  // 保存时才统一发送更新
}

// 保存编辑
function saveEdit() {
  if (props.node.dimension) {
    props.node.dimension.name = editName.value
    // 根据名称生成键值：转换为小写，空格替换为下划线，删除特殊字符
    props.node.dimension.key = editName.value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
  }
  const savedScore = parseFloat(editScore.value) || 0
  props.node.score = savedScore
  isEditing.value = false
  // 移除全局点击监听器
  document.removeEventListener('click', handleClickOutside)
  emit('update-node', props.node)
  // 向父组件发送编辑结束事件
  emit('edit-end', props.node.id)
}

// 取消编辑并恢复原始值
function cancelEdit() {
  if (props.node.dimension) {
    editName.value = originalName.value
    props.node.dimension.name = originalName.value
  }
  editScore.value = originalScore.value
  props.node.score = originalScore.value
  isEditing.value = false
  // 移除全局点击监听器
  document.removeEventListener('click', handleClickOutside)
  // 向父组件发送编辑结束事件
  emit('edit-end', props.node.id)
}

// 处理Esc键
function handleEscKey() {
  cancelEdit()
}

// 切换展开/折叠
function toggleExpand() {
  props.node.expanded = !props.node.expanded
  emit('update-node', props.node)
}
// 在组件卸载时清理事件监听器
onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

</script>

<style scoped>
.tree-node {
  margin-left: calc(var(--level, 0) * 24px);
  transition: margin-left 0.3s ease;
}

.node-content {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
  flex-wrap: wrap;
  gap: 8px;
}

.node-content:hover {
  background: #f8f9fa;
  border-color: #c0c0c0;
}

.node-content.selected {
  background: #e3f2fd;
  border-color: #2196f3;
  box-shadow: 0 0 0 1px rgba(33, 150, 243, 0.1);
}

.node-content.leaf {
  border-left: 3px solid #4caf50;
}

.node-toggle {
  background: none;
  border: none;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
  flex-shrink: 0;
  flex-grow: 0;
  flex-basis: auto;
}

.node-toggle:hover {
  background: #f0f0f0;
  color: #333;
}

.node-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}

.node-name {
  font-weight: 600;
  color: #333;
  margin-bottom: 2px;
  font-size: 14px;
  word-break: break-all;
}

.node-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.node-value {
  color: #666;
}

.node-score {
  color: #2196f3;
  font-weight: 500;
}

.node-name-input, .node-score-input {
  display: inline-block;
  width: auto;
  min-width: 80px;
  max-width: 100px;
  padding: 2px 4px;
  margin: 0;
  border: 1px solid #2196f3;
  border-radius: 3px;
  background: #fff;
  font-size: 14px;
  line-height: 1.4;
  font-weight: 600;
  color: #333;
  transition: none;
  height: auto;
  box-sizing: border-box;
  vertical-align: baseline;
}

.node-name-input:focus, .node-score-input:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 0 0 1px rgba(25, 118, 210, 0.3);
}

.node-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s ease;
  flex-shrink: 0;
}

.node-content:hover .node-actions {
  opacity: 1;
}

.btn-icon {
  background: none;
  border: none;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.btn-icon:hover {
  background: #f0f0f0;
  color: #333;
}

.btn-save {
  color: #4caf50;
}

.btn-save:hover {
  background: #e8f5e9;
  color: #388e3c;
}

.btn-cancel {
  color: #f44336;
}

.btn-cancel:hover {
  background: #ffebee;
  color: #d32f2f;
}

.node-children {
  margin-left: 24px;
  border-left: 1px dashed #e0e0e0;
  padding-left: 12px;
}

</style>