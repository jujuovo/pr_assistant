<template>
  <div class="page-content">
    <div class="page-title">
      <span>推免相关文件管理</span>
    </div>

    <!-- 上传区域 -->
    <div class="card">
      <div class="card-body">
        <div class="card-title">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>上传文件</span>
          </div>
        </div>
        <div class="form-group">
          <div class="file-upload-area" @click="triggerFileInput">
            <font-awesome-icon class="upload-icon" :icon="['fas', 'cloud-arrow-up']" />
            <div>
              <p>点击上传或拖拽文件到此处</p>
              <p class="help-text">支持PDF、Word、Excel、PPT等格式文件</p>
            </div>
            <input type="file" ref="fileInput" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx"
              @change="handleFileChange" style="display: none;">
          </div>
          <!-- 已选文件列表 -->
          <div class="file-list" v-if="selectedFiles.length > 0">
            <div class="file-list-header">
              <span>已上传文件 ({{ selectedFiles.length }})</span>
            </div>
            <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
              <div class="file-icon">
                <font-awesome-icon :icon="getFileIcon(file.name)" />
              </div>
              <div class="file-info">
                <div class="file-name">{{ file.name }}</div>
                <div class="file-meta">{{ formatFileSize(file.size) }}</div>
              </div>
              <div class="file-actions">
                <button type="button" class="file-action-btn" @click="removeFile(index)" title="移除文件">
                  <font-awesome-icon :icon="['fas', 'times']" />
                </button>
              </div>
            </div>
          </div>

          <!-- 学院选择 -->
          <div class="form-group" style="margin-top: 15px;">
            <label class="form-label">所属学院</label>
            <select v-model="selectedFacultyId" class="form-control">
              <option value="">请选择学院</option>
              <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">
                {{ faculty.name }}
              </option>
            </select>
          </div>

          <div class="form-actions">
            <button class="btn btn-outline" @click="uploadFiles" :disabled="!selectedFacultyId">
              <font-awesome-icon :icon="['fas', 'upload']" /> 上传文件
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 表格区域 -->
    <div class="card">
      <div class="card-body">
        <!-- 搜索和筛选 -->
        <div class="filters">
          <div class="filter-group">
            <input type="text" v-model="fileFilter" placeholder="搜索文件..." class="form-control">
          </div>
          <div class="filter-group">
            <label class="filter-label">学院：</label>
            <select v-model="selectedFacultyFilter" class="form-control">
              <option value="">全部学院</option>
              <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">
                {{ faculty.name }}
              </option>
            </select>
          </div>
          <div class="filter-group">
            <button class="btn btn-outline" @click="resetFilters">清空筛选</button>
            <button class="btn btn-outline" @click="batchDelete" :disabled="selectedFileIds.length === 0">
              <font-awesome-icon :icon="['fas', 'trash']" /> 批量删除
            </button>
          </div>
        </div>

        <!-- 加载状态指示器 -->
        <div v-if="loading" class="loading-overlay">
          <div class="loading-spinner"></div>
          <div class="loading-text">加载中...</div>
        </div>

        <!-- 文件列表 -->
        <div class="table-container">
          <table class="application-table">
            <thead>
              <tr>
                <th><input type="checkbox" v-model="selectAll" @change="toggleSelectAll"></th>
                <th>文件名称</th>
                <th>所属学院</th>
                <th>文件大小</th>
                <th>上传时间</th>
                <th style="text-align: center;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="file in filteredFiles" :key="file.id">
                <td><input type="checkbox" v-model="selectedFileIds" :value="file.id"></td>
                <td>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <font-awesome-icon :icon="getFileIcon(file.filename)" />
                    {{ file.filename }}
                  </div>
                </td>
                <td>{{ file.faculty?.name || '未分配' }}</td>
                <td>{{ formatFileSize(file.file_size) }}</td>
                <td>{{ formatUploadTime(file.upload_time) }}</td>
                <td>
                  <div class="action-buttons">
                    <button class="btn-outline btn small-btn" @click="downloadFile(file)" title="下载">
                      <font-awesome-icon icon="fa-solid fa-download" />
                    </button>
                    <button class="btn-outline btn small-btn delete-btn" @click="deleteFile(file.id)" title="删除">
                      <font-awesome-icon icon="fa-solid fa-trash" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 空状态 -->
        <div v-if="!loading && filteredFiles.length === 0" class="no-data">
          暂无上传文件
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useToastStore } from '../../stores/toast'
import { useFilesStore } from '../../stores/files'
import { useAuthStore } from '../../stores/auth'
import api from '../../utils/api'
import { getFileFullUrl } from '../../utils/api'

const toastStore = useToastStore()
const filesStore = useFilesStore()
const authStore = useAuthStore()

// 文件相关状态
const fileInput = ref(null)
const selectedFiles = ref([])
const loading = ref(false)
const faculties = ref([])
const selectedFacultyId = ref('')

// 批量操作相关状态
const selectAll = ref(false)
const selectedFileIds = ref([])

// 筛选条件
const fileFilter = ref('')
const selectedFacultyFilter = ref('')

// 触发文件选择对话框
const triggerFileInput = () => {
  fileInput.value?.click()
}

// 处理文件选择
const handleFileChange = (event) => {
  if (event.target.files) {
    selectedFiles.value = Array.from(event.target.files)
  }
}

// 移除单个文件
const removeFile = (index) => {
  selectedFiles.value.splice(index, 1)
  // 如果没有文件了，清空fileInput的值
  if (selectedFiles.value.length === 0 && fileInput.value) {
    fileInput.value.value = ''
  }
}

// 上传文件
const uploadFiles = async () => {
  if (selectedFiles.value.length === 0) {
    toastStore.warning('请先选择要上传的文件')
    return
  }

  if (!selectedFacultyId.value) {
    toastStore.warning('请选择文件所属学院')
    return
  }

  loading.value = true
  try {
    // 调用filesStore的uploadFiles方法，传递文件数组和学院ID
    await filesStore.uploadFiles(selectedFiles.value, selectedFacultyId.value)
    toastStore.success('文件上传成功')

    // 清空选择的文件和学院
    selectedFiles.value = []
    selectedFacultyId.value = ''
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  } catch (error) {
    console.error('文件上传失败:', error)
    toastStore.error('文件上传失败')
  } finally {
    loading.value = false
  }
}

// 筛选后的文件列表
const filteredFiles = computed(() => {
  return filesStore.files.filter(file => {
    // 文件名称筛选
    const nameMatch = !fileFilter.value || file.filename.toLowerCase().includes(fileFilter.value.toLowerCase())

    // 学院筛选
    const facultyMatch = !selectedFacultyFilter.value || file.faculty?.id === parseInt(selectedFacultyFilter.value)

    return nameMatch && facultyMatch
  })
})

// 重置筛选
const resetFilters = () => {
  fileFilter.value = ''
  selectedFacultyFilter.value = ''
}

// 加载文件列表
const loadFiles = async () => {
  loading.value = true
  try {
    await filesStore.loadFiles()
  } catch (error) {
    console.error('加载文件列表失败:', error)
    toastStore.error('加载文件列表失败')
  } finally {
    loading.value = false
  }
}

// 下载文件
const downloadFile = async (file) => {
  try {
    // 构建下载URL
    const downloadUrl = getFileFullUrl(file.file_url)
    
    // 直接跳转到下载链接，让浏览器处理下载
    window.location.href = downloadUrl
    
    toastStore.success('文件下载开始')
  } catch (error) {
    console.error('下载文件失败:', error)
    toastStore.error('下载文件失败')
  }
}

// 删除文件
const deleteFile = async (fileId) => {
  if (confirm('确定要删除此文件吗？')) {
    loading.value = true
    try {
      await filesStore.deleteFile(fileId)
      toastStore.success('文件删除成功')
      // 如果删除的文件在选中列表中，移除它
      const index = selectedFileIds.value.indexOf(fileId)
      if (index > -1) {
        selectedFileIds.value.splice(index, 1)
      }
      // 如果没有选中文件了，取消全选
      if (selectedFileIds.value.length === 0) {
        selectAll.value = false
      }
    } catch (error) {
      console.error('文件删除失败:', error)
      toastStore.error('文件删除失败')
    } finally {
      loading.value = false
    }
  }
}

// 全选/取消全选
const toggleSelectAll = () => {
  if (selectAll.value) {
    selectedFileIds.value = filteredFiles.value.map(file => file.id)
  } else {
    selectedFileIds.value = []
  }
}

// 批量删除
const batchDelete = async () => {
  if (selectedFileIds.value.length === 0) {
    return
  }

  if (confirm(`确定要删除选中的 ${selectedFileIds.value.length} 个文件吗？`)) {
    loading.value = true
    try {
      // 批量删除文件
      const promises = selectedFileIds.value.map(fileId =>
        filesStore.deleteFile(fileId).catch(error => {
          console.error(`删除文件 ${fileId} 失败:`, error)
          return false
        })
      )

      const results = await Promise.all(promises)
      const successCount = results.filter(result => result !== false).length

      if (successCount > 0) {
        toastStore.success(`成功删除 ${successCount} 个文件`)
      }

      if (successCount < selectedFileIds.value.length) {
        toastStore.warning(`部分文件删除失败`)
      }

      // 清空选中列表
      selectedFileIds.value = []
      selectAll.value = false
    } catch (error) {
      console.error('批量删除文件失败:', error)
      toastStore.error('批量删除文件失败')
    } finally {
      loading.value = false
    }
  }
}

// 获取文件图标
const getFileIcon = (fileName) => {
  const ext = fileName.split('.').pop().toLowerCase()
  switch (ext) {
    case 'pdf':
      return ['fas', 'file-pdf']
    case 'doc':
    case 'docx':
      return ['fas', 'file-word']
    case 'xls':
    case 'xlsx':
      return ['fas', 'file-excel']
    case 'ppt':
    case 'pptx':
      return ['fas', 'file-powerpoint']
    default:
      return ['fas', 'file']
  }
}

// 格式化文件大小
const formatFileSize = (size) => {
  if (size < 1024) {
    return size + ' B'
  } else if (size < 1024 * 1024) {
    return (size / 1024).toFixed(2) + ' KB'
  } else {
    return (size / (1024 * 1024)).toFixed(2) + ' MB'
  }
}

// 格式化上传时间
const formatUploadTime = (time) => {
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

// 加载学院列表
const loadFaculties = async () => {
  try {
    const response = await api.getFaculties()
    faculties.value = response.faculties || []
  } catch (error) {
    console.error('加载学院列表失败:', error)
    toastStore.error('加载学院列表失败')
  }
}

// 组件挂载时加载数据
onMounted(async () => {
  await loadFaculties()
  await loadFiles()
  
  // 设置默认学院为当前用户的学院
  const adminFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
  if (adminFacultyId) {
    selectedFacultyId.value = adminFacultyId
    selectedFacultyFilter.value = adminFacultyId
  }
})
</script>

<style scoped>
/* 引入共享样式 */
@import '../common/shared-styles.css';
</style>
