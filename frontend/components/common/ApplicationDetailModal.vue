<template>
  <div class="modal-overlay" @click="$emit('close')">
    <div class="modal-content two-column-layout" @click.stop>
      <div class="modal-header">
        <h3>{{ title }}</h3>
        <button class="close-btn" @click="$emit('close')">
          <font-awesome-icon :icon="['fas', 'times']" />
        </button>
      </div>

      <div class="modal-body">
        <!-- 左侧：文件预览区域 -->
        <div class="left-column" v-if="hasFiles">
          <div class="card preview-card">
            <!-- 可预览文件区域 -->
            <div v-if="hasPreviewFiles">
              <div class="card-title">
                证明文件预览
                <span class="image-counter">({{ currentImageIndex + 1 }}/{{ previewFiles.length }})</span>
                <div class="preview-controls">
                  <button class="btn-icon" @click="zoomOut" title="缩小" :disabled="previewZoomLevel <= 0.5">
                    <font-awesome-icon :icon="['fas', 'search-minus']" />
                  </button>
                  <span class="zoom-level">{{ Math.round(previewZoomLevel * 100) }}%</span>
                  <button class="btn-icon" @click="zoomIn" title="放大" :disabled="previewZoomLevel >= 3">
                    <font-awesome-icon :icon="['fas', 'search-plus']" />
                  </button>
                  <button class="btn-icon" @click="resetPreviewZoom" title="重置">
                    <font-awesome-icon :icon="['fas', 'sync']" />
                  </button>
                  <button class="btn-icon" @click.stop="downloadFile(currentPreviewFile)" title="下载">
                    <font-awesome-icon :icon="['fas', 'download']" />
                  </button>
                </div>
              </div>

              <!-- 预览文件导航 -->
              <div class="image-navigation" v-if="previewFiles.length > 1">
                <button class="nav-btn" @click="prevImage" :disabled="currentImageIndex === 0">
                  <font-awesome-icon :icon="['fas', 'chevron-left']" />
                </button>
                <div class="thumbnail-list">
                  <div v-for="(file, index) in previewFiles" :key="index" class="thumbnail-item"
                    :class="{ active: index === currentImageIndex }" @click="switchImage(index)">
                    <img v-if="isImage(file)" :src="getFileUrl(file)" :alt="file.name" />
                    <div v-else-if="isPDF(file)" class="pdf-thumbnail">
                      <font-awesome-icon :icon="['fas', 'file-pdf']" class="pdf-icon" />
                      <span class="pdf-name">{{ file.name.split('.')[0] }}</span>
                    </div>
                  </div>
                </div>
                <button class="nav-btn" @click="nextImage" :disabled="currentImageIndex === previewFiles.length - 1">
                  <font-awesome-icon :icon="['fas', 'chevron-right']" />
                </button>
              </div>

              <!-- 主预览区域 -->
              <div class="main-preview">
                <div class="image-container" @mousedown="startPreviewDrag" @mousemove="onPreviewDrag"
                  @mouseup="endPreviewDrag" @mouseleave="endPreviewDrag" @wheel="onPreviewWheel">
                  <div v-if="isImage(currentPreviewFile)" class="image-transform-container" :style="{
                    transform: `translate(${previewDragOffset.x}px, ${previewDragOffset.y}px) scale(${previewZoomLevel})`,
                    cursor: isPreviewDragging ? 'grabbing' : 'grab'
                  }">
                    <img :src="getFileUrl(currentPreviewFile)" :alt="currentPreviewFile.name" class="preview-image"
                      @load="onPreviewImageLoad" />
                  </div>
                  <div v-else-if="isPDF(currentPreviewFile)" class="pdf-preview-container" :style="{
                    transform: `translate(${previewDragOffset.x}px, ${previewDragOffset.y}px) scale(${previewZoomLevel})`,
                  }">
                    <iframe :src="getFileUrl(currentPreviewFile)" class="pdf-preview" type="application/pdf"
                      title="PDF Preview"></iframe>
                  </div>
                </div>
              </div>
            </div>

            <!-- 没有可预览文件但有其他文件时显示提示 -->
            <div v-else>
              <div class="card-title">证明文件预览</div>
              <div class="no-files">
                <font-awesome-icon :icon="['fas', 'file-image']" class="no-files-icon" />
                <p>暂无图片或PDF文件可预览</p>
                <p class="no-files-desc">您可以在右侧文件列表中下载其他格式的文件</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 没有文件时显示提示 -->
        <div class="left-column" v-else>
          <div class="card preview-card">
            <div class="card-title">证明文件预览</div>
            <div class="no-files">
              <font-awesome-icon :icon="['fas', 'folder-open']" class="no-files-icon" />
              <p>暂无证明文件</p>
            </div>
          </div>
        </div>

        <!-- 右侧：申请信息和文件列表/审核操作 -->
        <div class="right-column">
          <!-- 学生基本信息 -->
          <div class="card compact-card">
            <div class="card-title">学生信息</div>
            <div class="compact-row">
              <div class="compact-group">
                <label>姓名</label>
                <span>{{ studentName }}</span>
              </div>
              <div class="compact-group">
                <label>学号</label>
                <span>{{ application.studentId || '未知学号' }}</span>
              </div>
              <div class="compact-group">
                <label>系</label>
                <span>{{ application.department || '未知系' }}</span>
              </div>
              <div class="compact-group">
                <label>专业</label>
                <span>{{ application.major || '未知专业' }}</span>
              </div>
            </div>
          </div>
          <!-- 申请基本信息 -->
          <div class="card compact-card">
            <div class="card-title">申请信息</div>
            <div class="compact-row">
              <div class="compact-group">
                <label>申请类型</label>
                <span>{{ application.applicationType || '未知类型' }}</span>
              </div>
              <div class="compact-group">
                <label>项目全称</label>
                <span>{{ application.projectName || '未知项目' }}</span>
              </div>
              <div class="compact-group">
                <label>获得时间</label>
                <span>{{ formatDate(application.awardDate || application.award_date) || '-' }}</span>
              </div>
              <div class="compact-group">
                <label>自评分数</label>
                <span>{{ application.selfScore || 0 }}</span>
              </div>
              <div class="compact-group">
                <label>申请时间</label>
                <span>{{ formatDate(application.appliedAt || application.createdAt) }}</span>
              </div>
              <div class="compact-group">
                <label>审核时间</label>
                <span>{{ formatDate(application.reviewedAt) || '-' }}</span>
              </div>
              <div v-if="!isStudentMode" class="compact-group">
                <label>审核人</label>
                <span>{{ application.reviewedBy || '-' }}</span>
              </div>
              <div v-if="isReviewMode || application.status !== 'pending'" class="compact-group">
                <label>最终分数</label>
                <span>{{ application.status === 'pending' ? '-' : (application.status === 'rejected' ? 0 :
                  application.finalScore || 0) }}</span>
              </div>
              <div class="compact-group">
                <label>申请状态</label>
                <span class="status-badge" :class="`status-${application.status}`">{{ getStatusText(application.status)
                  }}</span>
              </div>
            </div>
            <div class="compact-group full-width">
              <label>加分依据</label>
              <p class="description-text">{{ application.description || '无' }}</p>
            </div>
            <div class="compact-group full-width" v-if="application.reviewComment && !isReviewMode">
              <label>审核意见</label>
              <div class="review-comment">{{ application.reviewComment }}</div>
            </div>
          </div>

          <!-- 审核规则信息 -->
          <div class="card compact-card" v-if="application.rule">
            <div class="card-title">审核规则</div>
            <div class="compact-row">
              <div class="compact-group">
                <label>规则名称</label>
                <span>{{ application.rule.name }}</span>
              </div>
              <div class="compact-group">
                <label>规则基础分数</label>
                <span>{{ application.rule.score || 0 }}</span>
              </div>
            </div>
            <div class="compact-group full-width">
              <label>规则说明</label>
              <p class="description-text">{{ application.rule.description || '无' }}</p>
            </div>
            <!-- 动态系数信息 -->
            <div class="compact-row" v-if="Object.keys(dynamicCoefficients).length > 0">
              <div class="compact-group">
                <label>学生选择系数</label>
                <div class="coefficients-list">
                  <div v-for="(detail, key) in coefficientDetails" :key="key" class="coefficient-item">
                    <span class="coefficient-key">{{ detail.label }} : </span>
                    <span class="coefficient-value">{{ detail.displayValue }}</span>
                  </div>
                </div>
              </div>
              <div class="compact-group">
                <label>预估得分</label>
                <span>{{ estimatedScore }}</span>
              </div>
            </div>
          </div>
          <!-- 审核操作区域 -->
          <div v-if="isReviewMode" class="card compact-card">
            <div class="card-title">审核操作</div>
            <div class="form-group">
              <label>最终分数</label>
              <div class="score-input-container">
                <input type="number" v-model.number="reviewData.finalScore" min="0" max="100" step="0.5"
                  class="form-control small-input" />
                <span class="score-hint">预计分数:{{ estimatedScore }}</span>
                <span v-if="isScoreMismatch" class="score-mismatch-warning">
                  最终分数与规则预估分数不一致，请仔细确认
                </span>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>通过意见</label>
                <textarea class="form-control small-textarea" v-model="reviewData.approveComment" rows="2"
                  placeholder="通过说明（可选）"></textarea>
              </div>
              <div class="form-group">
                <label>驳回意见 <span class="required">*</span></label>
                <textarea class="form-control small-textarea" v-model="reviewData.rejectComment" rows="2"
                  placeholder="请输入驳回理由（若驳回则必填）"></textarea>
              </div>
            </div>
            <div class="form-actions-compact">
              <button type="button" class="btn btn-reject" @click="rejectApplication">
                <font-awesome-icon :icon="['fas', 'times']" /> 驳回
              </button>
              <button type="button" class="btn btn-approve" @click="approveApplication">
                <font-awesome-icon :icon="['fas', 'check']" /> 通过
              </button>
            </div>
          </div>

          <!-- 文件列表 -->
          <div class="card">
            <div class="card-title">
              证明文件
              <span class="file-count">({{ props.application.files?.length || 0 }}个文件)</span>
            </div>
            <div class="file-list">
              <div v-for="(file, index) in props.application.files" :key="index" class="file-item-compact">
                <font-awesome-icon :icon="getFileIcon(file.name)" class="file-icon" />
                <span class="file-name">{{ file.name }}</span>
                <div class="file-actions">
                  <button v-if="isImage(file) || isPDF(file)" class="btn-icon" @click="switchToImage(file)"
                    :class="{ active: isCurrentImage(file) }" title="预览">
                    <font-awesome-icon :icon="['fas', 'eye']" />
                  </button>
                  <button class="btn-icon" @click.stop="downloadFile(file)" title="下载">
                    <font-awesome-icon :icon="['fas', 'download']" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useToastStore } from '../../stores/toast'
import { getFileFullUrl } from '../../utils/api'

const toastStore = useToastStore()

const props = defineProps({
  application: {
    type: Object,
    required: true
  },
  isReviewMode: {
    type: Boolean,
    default: false
  },
  isStudentMode: {
    type: Boolean,
    default: false
  },
  authStore: {
    type: Object,
    default: null
  },
  title: {
    type: String,
    default: '申请详情'
  }
})

const emit = defineEmits(['close', 'approve', 'reject'])

// 计算学生姓名
const studentName = computed(() => {
  if (props.isStudentMode && props.authStore?.userName) {
    return props.authStore.userName
  }
  return props.application.studentName || '未知学生'
})

// 计算是否为审核模式
const isReviewMode = computed(() => props.isReviewMode)

// 审核数据
const reviewData = reactive({
  finalScore: props.application.finalScore || props.application.selfScore || 0,
  approveComment: props.application.status === 'approved' ? props.application.reviewComment || '' : '',
  rejectComment: props.application.status === 'rejected' ? props.application.reviewComment || '' : ''
})

// 监听application变化，更新reviewData
watch(() => props.application, (newApplication) => {
  if (newApplication) {
    reviewData.finalScore = newApplication.finalScore || newApplication.selfScore || 0
    reviewData.approveComment = newApplication.status === 'approved' ? newApplication.reviewComment || '' : ''
    reviewData.rejectComment = newApplication.status === 'rejected' ? newApplication.reviewComment || '' : ''
  }
}, { deep: true })

// 监听finalScore变化，确保值在0-100之间
watch(() => reviewData.finalScore, (newScore) => {
  if (newScore !== null && newScore !== undefined) {
    // 确保分数在0-100之间
    reviewData.finalScore = Math.max(0, Math.min(100, parseFloat(newScore) || 0))
  }
})

// 图片相关状态
const currentImageIndex = ref(0)
const previewZoomLevel = ref(1)
const previewDragOffset = reactive({ x: 0, y: 0 })
const isPreviewDragging = ref(false)
const previewLastDragPos = reactive({ x: 0, y: 0 })

// 计算属性
const imageFiles = computed(() => {
  // 确保 files 是数组，且过滤掉 null/undefined 等无效元素
  const validFiles = (props.application.files || []).filter(file => file && typeof file === 'object');
  return validFiles.filter(file => isImage(file));
})

// 获取动态系数
const dynamicCoefficients = computed(() => {
  let coefficients = {};
  // 从后端返回的数据中获取动态系数，处理不同的字段名和可能的JSON字符串
  // 首先检查驼峰式命名的dynamicCoefficients（后端API返回的格式）
  if (props.application.dynamicCoefficients) {
    if (typeof props.application.dynamicCoefficients === 'string') {
      try {
        coefficients = JSON.parse(props.application.dynamicCoefficients);
      } catch (error) {
        coefficients = {};
      }
    } else {
      coefficients = props.application.dynamicCoefficients;
    }
  }
  // 然后检查下划线命名的dynamic_coefficients（兼容旧格式）
  else if (props.application.dynamic_coefficients) {
    if (typeof props.application.dynamic_coefficients === 'string') {
      try {
        coefficients = JSON.parse(props.application.dynamic_coefficients);
      } catch (error) {
        coefficients = {};
      }
    } else {
      coefficients = props.application.dynamic_coefficients;
    }
  }
  // 确保dynamicCoefficients是对象
  if (typeof coefficients !== 'object' || coefficients === null) {
    coefficients = {};
  }
  return coefficients;
});

// 辅助函数：获取学生信息（参考ApplicationForm.vue）
const getStudentData = () => {
  const data = {
    ...dynamicCoefficients.value,
    studentName: props.application.studentName || props.application.student_name || '未知学生',
    studentId: props.application.studentId || props.application.student_id || '未知学号',
    facultyId: props.application.facultyId || props.application.faculty_id || '',
    departmentId: props.application.departmentId || props.application.department_id || '',
    majorId: props.application.majorId || props.application.major_id || ''
  };

  // 将tree_path字符串转换为数组（与ApplicationForm.vue保持一致）
  if (data.tree_path && typeof data.tree_path === 'string') {
    data.tree_path = data.tree_path.split(',');
  }

  return data;
};

// 获取系数的详细信息，包括级别名称
const coefficientDetails = computed(() => {
  if (!props.application.rule?.calculation) return {};

  const calculationType = props.application.rule.calculation.calculation_type;
  let parameters = props.application.rule.calculation.parameters || {};

  // 解析参数（可能是JSON字符串）
  if (typeof parameters === 'string') {
    try {
      parameters = JSON.parse(parameters);
    } catch (error) {
      return {};
    }
  }

  const details = {};
  const studentData = getStudentData();

  // 根据计算类型生成不同的系数详细信息
  if (calculationType === 'tree' || parameters.type === 'tree') {
    // 优先处理tree_path字段（参考ApplicationForm.vue）
    if (studentData.tree_path && Array.isArray(studentData.tree_path)) {
      // 使用tree_path字段直接构建系数详情
      for (let i = 0; i < studentData.tree_path.length; i++) {
        const value = studentData.tree_path[i];
        if (value !== undefined && value !== null && value !== '') {
          const key = i === 0 ? '项目级别' : `级别${i}`;
          details[`_${i}`] = {
            label: key,
            value: value,
            displayValue: value
          };
        }
      }
    } else {
      // 处理带有索引的字段名（如：key_0, key_1）
      const treeFieldKeys = Object.keys(studentData)
        .filter(key => /.*?_\d+$/.test(key))
        .sort((a, b) => {
          const indexA = parseInt(a.match(/.*?_\d+$/)[0].substring(1));
          const indexB = parseInt(b.match(/.*?_\d+$/)[0].substring(1));
          return indexA - indexB;
        });

      // 提取树路径值
      for (const key of treeFieldKeys) {
        const value = studentData[key];
        if (value !== undefined && value !== null && value !== '') {
          const index = parseInt(key.match(/.*?_\d+$/)[0].substring(1));
          const label = index === 0 ? '项目级别' : `级别${index}`;
          details[key] = {
            label: label,
            value: value,
            displayValue: value
          };
        }
      }

      // 如果没有找到带索引的字段，尝试处理普通字段
      if (Object.keys(details).length === 0) {
        // 获取树结构配置
        const treeConfig = parameters.tree || {};
        const tree = treeConfig.structure || treeConfig.tree || {};

        // 如果有树结构，按照树的层次顺序生成详情
        if (tree && tree.root) {
          // 递归遍历树结构，按照用户选择的路径收集维度键
          const dimensionKeys = [];
          const traverseTree = (node) => {
            if (!node) return;

            const dimensionKey = node.dimension.key;
            const dimensionValue = studentData[dimensionKey];

            if (dimensionKey && dimensionValue) {
              dimensionKeys.push(dimensionKey);
            }

            if (node.children && node.children.length > 0 && dimensionValue) {
              // 找到与动态系数值匹配的子节点
              const selectedChild = node.children.find(child => child.dimension.name === dimensionValue);
              if (selectedChild) {
                traverseTree(selectedChild);
              }
            }
          };

          traverseTree(tree.root);

          // 根据收集到的维度键顺序生成详情
          for (const key of dimensionKeys) {
            const value = studentData[key];
            if (value === undefined || value === null || value === '') continue;

            details[key] = {
              label: key === 'root' ? '项目级别' : key,
              value: value,
              displayValue: value
            };
          }
        }
      }
    }
  }
  return details;
});

// 计算预估分数
const estimatedScore = computed(() => {
  if (!props.application.rule) {
    return 0;
  }
  const score = calculateScoreFrontend(props.application.rule);
  return parseFloat(score.toFixed(4));
});

// 前端分数计算函数（与后端RuleEngine保持一致）
const calculateScoreFrontend = (rule) => {
  if (!rule || !rule.calculation) {
    // 如果没有计算配置，使用基础分数
    return rule.score || 0;
  }

  let totalScore = 0;

  // 根据计算类型执行不同的计算逻辑
  switch (rule.calculation.calculation_type) {
    case 'tree':
      // 树结构计算
      totalScore = calculateTreeScore(rule);
      break;

    default:
      // 默认使用基础分数
      totalScore = rule.score || 0;
  }

  // 应用最大分数限制
  if (rule.max_score && totalScore > rule.max_score) {
    totalScore = rule.max_score;
  }

  return totalScore;
};

// 计算树结构分数（参考ApplicationForm.vue的实现）
const calculateTreeScore = (rule) => {
  let parameters = rule.calculation.parameters || {};

  // 解析参数（可能是JSON字符串）
  if (typeof parameters === 'string') {
    try {
      parameters = JSON.parse(parameters);
    } catch (error) {
      console.error('Failed to parse parameters:', error);
      return rule.score || 0;
    }
  }

  // 获取树结构配置
  const treeConfig = parameters.tree || {};

  // 获取对应的分数
  let scores = treeConfig.scores || {};

  // 如果scores是字符串，尝试解析为JSON
  if (typeof scores === 'string') {
    try {
      scores = JSON.parse(scores);
    } catch (e) {
      console.error('Failed to parse scores:', e);
      scores = {};
    }
  }

  // 获取树结构
  const tree = treeConfig.structure || treeConfig.tree || {};
  const rootNode = tree.root;

  if (!rootNode) {
    return 0;
  }

  // 获取完整的学生数据（与后端逻辑完全一致）
  const studentData = getStudentData();

  // 优先使用studentData中的tree_path字段（与后端逻辑一致）
  let treePath = studentData.tree_path;
  let matchingPath = null;

  if (treePath && Array.isArray(treePath) && treePath.length > 0) {
    matchingPath = treePath;
  } else {
    // 如果没有tree_path字段，再回退到动态查找路径
    console.log('没有找到tree_path字段，尝试动态查找路径');

    // 处理带有索引的字段名（如：key_0, key_1）
    const treeFieldKeys = Object.keys(studentData)
      .filter(key => /.*?_\d+$/.test(key))
      .sort((a, b) => {
        const indexA = parseInt(a.match(/.*?_\d+$/)[0].substring(1));
        const indexB = parseInt(b.match(/.*?_\d+$/)[0].substring(1));
        return indexA - indexB;
      });

    // 提取树路径值
    const indexedPath = [];
    for (const key of treeFieldKeys) {
      const value = studentData[key];
      if (value !== undefined && value !== null && value !== '') {
        indexedPath.push(value);
      }
    }

    if (indexedPath.length > 0) {
      matchingPath = indexedPath;
    } else {
      // 递归查找匹配路径（确保找到最深层的匹配叶子节点）
      const findMatchingPath = (node, currentPath = []) => {
        // 获取当前节点的名称
        const nodeDimension = node.dimension || {};
        const nodeName = nodeDimension.name || node.name;

        // 将当前节点添加到路径中
        const fullPath = [...currentPath, nodeName];

        // 如果是叶子节点，检查是否与studentData中的值匹配
        if (!node.children || node.children.length === 0) {
          // 检查当前叶子节点是否匹配
          let is_leaf_matched = false;

          // 灵活匹配方式：检查是否有任何字段的值等于当前叶子节点名
          for (const key in studentData) {
            const value = studentData[key];
            if (value !== undefined && value !== null && value !== '') {
              if (String(value).trim() === nodeName.trim()) {
                is_leaf_matched = true;
                break;
              }
            }
          }

          // 如果叶子节点匹配，返回完整路径
          if (is_leaf_matched) {
            return fullPath;
          } else {
            // 叶子节点不匹配，返回null
            return null;
          }
        }

        // 用于存储找到的最长路径
        let longestPath = null;

        // 遍历当前节点的所有子节点
        for (const child of node.children) {
          // 获取子节点的名称和键（兼容不同的节点结构）
          const childDimension = child.dimension || {};
          const childKey = childDimension.key || child.key;
          const childName = childDimension.name || child.name;

          // 检查当前子节点是否匹配
          let is_child_matched = false;

          // 灵活匹配方式：检查是否有任何字段的值等于当前子节点名
          for (const key in studentData) {
            const value = studentData[key];
            if (value !== undefined && value !== null && value !== '') {
              if (String(value).trim() === childName.trim()) {
                is_child_matched = true;
                break;
              }
            }
          }

          // 传统匹配方式：使用节点自己的key来匹配student_data
          if (!is_child_matched && childKey && studentData.hasOwnProperty(childKey)) {
            const child_value = String(studentData[childKey]);
            if (child_value.trim() === childName.trim()) {
              is_child_matched = true;
            }
          }

          // 对于每个子节点，无论是否匹配，都尝试向下遍历
          // 这确保我们能找到最深层的匹配叶子节点
          const result = findMatchingPath(child, fullPath);

          // 如果找到匹配路径，且该路径比当前最长路径更长，则更新最长路径
          if (result) {
            if (!longestPath || result.length > longestPath.length) {
              longestPath = result;
            }
          }
        }

        // 返回找到的最长匹配路径
        return longestPath;
      };

      // 查找匹配路径
      matchingPath = findMatchingPath(rootNode);
    }
  }

  if (!matchingPath) {
    return 0;
  }

  // 根据匹配路径找到对应的叶子节点，并获取其score属性
  let currentNode = rootNode;

  // 跳过根节点（如果路径包含根节点的话）
  const pathToUse = matchingPath[0] === '根节点' ? matchingPath.slice(1) : matchingPath;

  for (const nodeName of pathToUse) {
    if (currentNode?.children) {
      // 使用更宽松的匹配方式，忽略空格和大小写差异
      const nextNode = currentNode.children.find(child => {
        const childName = child.dimension.name || '';
        return childName.trim() === nodeName.trim();
      });
      if (nextNode) {
        currentNode = nextNode;
      } else {
        break;
      }
    } else {
      break;
    }
  }

  // 获取叶子节点的score属性
  const score = parseFloat(currentNode?.score || 0);

  // 应用最大值限制
  if (rule.calculation && rule.calculation.max_score !== undefined && rule.calculation.max_score !== null && rule.calculation.max_score !== '') {
    const maxScore = parseFloat(rule.calculation.max_score);
    // 确保maxScore是有效的数字
    if (!isNaN(maxScore)) {
      const finalScore = Math.min(score, maxScore);
      return finalScore;
    }
  }

  return score;
}

const pdfFiles = computed(() => {
  // 确保 files 是数组，且过滤掉 null/undefined 等无效元素
  const validFiles = (props.application.files || []).filter(file => file && typeof file === 'object');
  return validFiles.filter(file => isPDF(file));
})

// 所有可预览的文件（图片和PDF）
const previewFiles = computed(() => {
  // 确保 files 是数组，且过滤掉 null/undefined 等无效元素
  const validFiles = (props.application.files || []).filter(file => file && typeof file === 'object');
  return validFiles.filter(file => isImage(file) || isPDF(file));
})

const hasImages = computed(() => imageFiles.value.length > 0)
const hasPDFs = computed(() => pdfFiles.value.length > 0)
const hasPreviewFiles = computed(() => previewFiles.value.length > 0)
const hasFiles = computed(() => props.application.files && props.application.files.length > 0)
const currentImage = computed(() => imageFiles.value[currentImageIndex.value] || null)

// 当前预览的文件（图片或PDF）
const currentPreviewFile = computed(() => {
  if (previewFiles.value.length > 0) {
    // 如果当前索引超出范围，重置为0
    if (currentImageIndex.value >= previewFiles.value.length) {
      currentImageIndex.value = 0;
    }
    return previewFiles.value[currentImageIndex.value];
  }
  return null;
})

// 分数不匹配警告
const isScoreMismatch = computed(() => {
  const ruleScore = props.application.rule?.score;
  const selfScore = reviewData.finalScore;

  // 确保两个分数都有值且可转换为数字
  if (ruleScore !== undefined && ruleScore !== null && ruleScore !== '' &&
    selfScore !== undefined && selfScore !== null && selfScore !== '') {
    // 转换为浮点数进行比较
    return parseFloat(ruleScore) !== parseFloat(selfScore);
  }
  return false;
})

// 方法
const getStatusText = (status) => {
  const statusMap = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回'
  }
  return statusMap[status] || status
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false // 使用24小时制
  })
}

const isImage = (file) => {
  // 先判断 file 和 file.name 是否存在
  if (!file || !file.name) return false;
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']
  const ext = file.name.split('.').pop().toLowerCase()
  return imageExtensions.includes(ext)
}

// 判断是否为PDF文件
const isPDF = (file) => {
  // 先判断 file 和 file.name 是否存在
  if (!file || !file.name) return false;
  const ext = file.name.split('.').pop().toLowerCase()
  return ext === 'pdf'
}

const getFileIcon = (fileName) => {
  if (!fileName) {
    return ['fas', 'file-question']
  }
  const ext = fileName.split('.').pop().toLowerCase()
  if (isImage({ name: fileName })) {
    return ['fas', 'file-image']
  } else if (ext === 'pdf') {
    return ['fas', 'file-pdf']
  } else {
    return ['fas', 'file']
  }
}

const getFileUrl = (file) => {
  if (file instanceof File) return URL.createObjectURL(file)
  if (file.data) return file.data
  if (file.url) return file.url

  let fileUrl = null

  if (file.path) {
    // 使用getFileFullUrl函数确保路径正确
    fileUrl = getFileFullUrl(file.path)
  } else if (file.id) {
    // 如果没有path字段，使用文件ID构建URL
    fileUrl = getFileFullUrl(`/uploads/files/${file.id}`)
  } else if (file.name) {
    // 作为最后的回退，使用文件名构建URL
    fileUrl = getFileFullUrl(`/uploads/files/${file.name}`)
  }

  return fileUrl || ''
}

// 预览文件导航方法
const switchImage = (index) => {
  currentImageIndex.value = index
  resetPreviewZoom()
}

const prevImage = () => {
  if (currentImageIndex.value > 0) {
    currentImageIndex.value--
    resetPreviewZoom()
  }
}

const nextImage = () => {
  if (currentImageIndex.value < previewFiles.value.length - 1) {
    currentImageIndex.value++
    resetPreviewZoom()
  }
}

const switchToImage = (file) => {
  const index = previewFiles.value.findIndex(f => f.name === file.name)
  if (index !== -1) switchImage(index)
}

const isCurrentImage = (file) => currentPreviewFile.value && currentPreviewFile.value.name === file.name

// 预览区域缩放控制
const zoomIn = () => {
  previewZoomLevel.value = Math.min(previewZoomLevel.value + 0.25, 3)
}

const zoomOut = () => {
  previewZoomLevel.value = Math.max(previewZoomLevel.value - 0.25, 0.5)
}

const resetPreviewZoom = () => {
  previewZoomLevel.value = 1
  previewDragOffset.x = 0
  previewDragOffset.y = 0
}

// 预览区域拖拽功能
const startPreviewDrag = (event) => {
  if (event.button !== 0) return
  isPreviewDragging.value = true
  previewLastDragPos.x = event.clientX
  previewLastDragPos.y = event.clientY
  event.preventDefault()
}

const onPreviewDrag = (event) => {
  if (!isPreviewDragging.value) return

  const deltaX = event.clientX - previewLastDragPos.x
  const deltaY = event.clientY - previewLastDragPos.y

  previewDragOffset.x += deltaX
  previewDragOffset.y += deltaY

  previewLastDragPos.x = event.clientX
  previewLastDragPos.y = event.clientY
  event.preventDefault()
}

const endPreviewDrag = () => {
  isPreviewDragging.value = false
}

// 预览区域鼠标滚轮缩放
const onPreviewWheel = (event) => {
  event.preventDefault()

  const delta = -Math.sign(event.deltaY) * 0.1
  const newZoom = Math.max(0.5, Math.min(3, previewZoomLevel.value + delta))

  const rect = event.currentTarget.getBoundingClientRect()
  const mouseX = event.clientX - rect.left
  const mouseY = event.clientY - rect.top

  const zoomPointX = (mouseX - previewDragOffset.x) / previewZoomLevel.value
  const zoomPointY = (mouseY - previewDragOffset.y) / previewZoomLevel.value

  previewZoomLevel.value = newZoom

  previewDragOffset.x = mouseX - zoomPointX * newZoom
  previewDragOffset.y = mouseY - zoomPointY * newZoom
}

// 下载文件
const downloadFile = async (file) => {
  try {
    // 检查是否是浏览器File对象（用于新上传的文件）
    if (file instanceof File) {
      const url = URL.createObjectURL(file)
      const a = document.createElement('a')
      a.href = url
      a.download = file.name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      return
    }

    // 从后端获取的文件对象，构建正确的下载URL
    let downloadUrl = null

    // 构建完整的下载URL
    if (file.id) {
      downloadUrl = getFileFullUrl(`/uploads/files/${file.id}`)
    } else if (file.path) {
      downloadUrl = getFileFullUrl(file.path)
    } else if (file.name) {
      downloadUrl = getFileFullUrl(`/uploads/files/${file.name}`)
    }

    if (!downloadUrl) {
      toastStore.error(`无法下载文件: ${file.name}`)
      return
    }

    // 使用fetch API获取文件内容
    const response = await fetch(downloadUrl)
    if (!response.ok) {
      throw new Error(`下载失败: ${response.status} ${response.statusText}`)
    }

    // 获取文件内容
    const blob = await response.blob()

    // 创建下载链接
    const blobUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = file.name || 'downloaded_file'
    document.body.appendChild(a)

    // 触发下载
    a.click()

    // 清理资源
    setTimeout(() => {
      document.body.removeChild(a)
      window.URL.revokeObjectURL(blobUrl)
    }, 0)
  } catch (error) {
    console.error('文件下载失败:', error)
    toastStore.error(`文件下载失败: ${error.message}`)
  }
}

const onPreviewImageLoad = () => {
  // 图片加载完成后的处理
}

// 审核操作
const approveApplication = () => {
  // 确保最终分数在有效范围内
  const validScore = Math.max(0, Math.min(100, parseFloat(reviewData.finalScore) || 0))
  emit('approve', {
    ...reviewData,
    finalScore: validScore,
    applicationId: props.application.id
  })
}

const rejectApplication = () => {
  // 验证驳回理由是否填写
  if (!reviewData.rejectComment || reviewData.rejectComment.trim() === '') {
    toastStore.error('请填写驳回理由')
    return
  }
  // 拒绝的申请将最终分数设置为0
  reviewData.finalScore = 0;
  emit('reject', {
    ...reviewData,
    applicationId: props.application.id
  })
}
</script>

<style scoped>
/* 引入共享样式 */
@import './shared-styles.css';

/* 模态框特有样式*/
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  width: 100%;
  max-width: 1500px;
  max-height: 90vh;
  min-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.modal-body {
  display: flex;
  flex: 1;
  padding: 0;
  overflow: hidden;
  height: calc(100% - 60px);
}

.left-column {
  flex: 1.5;
  padding: 20px;
  overflow-y: auto;
  border-right: 1px solid #eee;
  background-color: white;
}

.right-column {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #f8f9fa;
}

/* 滚动条样式 */
.left-column::-webkit-scrollbar,
.right-column::-webkit-scrollbar {
  width: 8px;
}

.left-column::-webkit-scrollbar-track,
.right-column::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.left-column::-webkit-scrollbar-thumb,
.right-column::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.left-column::-webkit-scrollbar-thumb:hover,
.right-column::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* Firefox支持 */
.left-column,
.right-column {
  scrollbar-width: thin;
  scrollbar-color: #c1c1c1 #f1f1f1;
}

.card {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 16px;
  margin-bottom: 16px;
}

.preview-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-bottom: 0;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.compact-card {
  padding: 12px;
  margin-bottom: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #003366;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.main-preview {
  margin-bottom: 5px;
  border: 1px solid #eee;
  border-radius: 3px;
  overflow: hidden;
  background: #fafafa;
  flex: 1;
  min-height: 0;
}

.image-container {
  position: relative;
  height: 690px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(45deg, #f0f0f0 25%, transparent 25%),
    linear-gradient(-45deg, #f0f0f0 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #f0f0f0 75%),
    linear-gradient(-45deg, transparent 75%, #f0f0f0 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
  overflow: hidden;
  cursor: default;
}

.image-transform-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.1s ease-out;
  transform-origin: center center;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.1s ease-out;
}

/* PDF预览样式 */
.pdf-preview-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.pdf-preview {
  width: 100%;
  height: 100%;
  border: none;
}

/* PDF缩略图样式 */
.pdf-thumbnail {
  width: 100%;
  height: 100%;
  background-color: #f5f5f5;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
  padding: 5px;
  box-sizing: border-box;
}

.pdf-icon {
  font-size: 20px;
  margin-bottom: 5px;
  color: #dc3545;
}

.pdf-name {
  font-size: 10px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.image-navigation {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.thumbnail-list {
  display: flex;
  overflow-x: auto;
  gap: 8px;
  flex: 1;
  padding: 4px 0;
}

.thumbnail-item {
  width: 80px;
  height: 60px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s ease;
}

.thumbnail-item.active {
  border-color: #003366;
}

.thumbnail-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.nav-btn {
  background: none;
  border: none;
  color: #003366;
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  font-size: 18px;
}

.nav-btn:hover:not(:disabled) {
  background-color: #f0f0f0;
}

.nav-btn:disabled {
  color: #ccc;
  cursor: not-allowed;
}

.preview-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.preview-controls .btn-icon {
  background: rgba(0, 51, 102, 0.1);
  color: #003366;
  border: none;
  border-radius: 4px;
  padding: 6px 8px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.preview-controls .btn-icon:hover:not(:disabled) {
  background: #003366;
  color: white;
}

.preview-controls .btn-icon:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.preview-controls .zoom-level {
  font-size: 14px;
  color: #666;
  min-width: 50px;
  text-align: center;
}

.zoom-level {
  font-size: 14px;
  color: #666;
  min-width: 50px;
  text-align: center;
}

.no-files {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.no-files-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.no-files-desc {
  font-size: 14px;
  margin-top: 8px;
}

.compact-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 8px;
}

.compact-group {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
  min-width: 120px;
}

.compact-group.full-width {
  width: 100%;
  min-width: 100%;
}

/* 必填项标记 */
.required {
  color: #dc3545;
  font-weight: bold;
  margin-left: 2px;
}

.compact-group label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
  font-weight: 500;
}

.compact-group span {
  font-size: 14px;
  color: #333;
  padding: 6px 0;
}

.review-comment {
  background-color: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.description-text {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
}

.file-list {
  margin-top: 12px;
  border: none !important;
}

.file-actions {
  margin-left: auto;
}

.btn-icon {
  background: none;
  border: none;
  color: #003366;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 3px;
  font-size: 12px;
}

.btn-icon:hover,
.btn-icon.active {
  background: #003366;
  color: white;
}

/* 组件特有样式 */
.small-input {
  padding: 6px 10px;
  font-size: 13px;
  width: 100px;
}

.small-textarea {
  padding: 6px 10px;
  font-size: 13px;
  resize: vertical;
  min-height: 60px;
}

.form-actions-compact {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: -26px;
}

.btn-approve {
  background-color: #28a745;
  color: white;
}

.btn-approve:hover {
  background-color: #218838;
}

.btn-reject {
  background-color: #dc3545;
  color: white;
}

.btn-reject:hover {
  background-color: #c82333;
}

.file-item-compact {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: #f8f9fa;
  border-radius: 4px;
  margin-bottom: 5px;
  font-size: 13px;
}

.score-mismatch-warning {
  display: block;
  color: #dc3545;
  font-size: 12px;
  margin-top: 4px;
  padding: 2px 0;
  line-height: 1.2;
  font-weight: normal;
  text-align: left;
}

.score-input-container {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-hint {
  font-size: 13px;
  color: #666;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .two-column-layout {
    height: 95vh;
  }

  .modal-body {
    flex-direction: column;
  }

  .left-column {
    border-right: none;
    border-bottom: 1px solid #eee;
    width: 100%;
    max-height: 50%;
    height: 50%;
  }

  .right-column {
    width: 100%;
    max-height: 50%;
    height: 50%;
  }
}

@media (max-width: 768px) {
  .two-column-layout {
    width: 98%;
    margin: 10px;
    height: 95vh;
  }

  .modal-header {
    padding: 12px 15px;
  }

  .modal-header h3 {
    font-size: 16px;
  }

  .left-column {
    padding: 15px;
  }

  .right-column {
    padding: 15px;
    max-height: 40%;
    height: 40%;
  }

  .preview-controls {
    flex-wrap: wrap;
    justify-content: center;
    margin-top: 8px;
    margin-left: 0;
  }

  .card-title {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>