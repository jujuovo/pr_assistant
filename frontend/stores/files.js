import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api, { getFileFullUrl } from '../utils/api'

export const useFilesStore = defineStore('files', () => {
  // 文件列表状态
  const files = ref([])
  const loading = ref(false)
  const error = ref(null)

  // 计算属性
  const fileCount = computed(() => files.value.length)

  // 加载文件列表
  const loadFiles = async (facultyId = null) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.getPublicGraduateFiles(facultyId)
      files.value = response?.files || []
      return true
    } catch (err) {
      console.error('加载文件列表失败:', err)
      error.value = '加载文件列表失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // 上传文件
  const uploadFiles = async (filesToUpload, facultyId) => {
    loading.value = true
    error.value = null
    
    try {
      for (const file of filesToUpload) {
        await api.uploadGraduateFile(file, 'admin', '', 'graduate', facultyId)
      }
      
      // 上传成功后重新加载文件列表
      await loadFiles()
      return true
    } catch (err) {
      console.error('文件上传失败:', err)
      error.value = '文件上传失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // 下载文件
  const downloadFile = (file) => {
    window.location.href = getFileFullUrl(file.file_url)
  }

  // 删除文件
  const deleteFile = async (fileId) => {
    loading.value = true
    error.value = null
    
    try {
      await api.deleteGraduateFile(fileId)
      
      // 删除成功后从本地状态中移除该文件
      files.value = files.value.filter(file => file.id !== fileId)
      return true
    } catch (err) {
      console.error('文件删除失败:', err)
      error.value = '文件删除失败'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    // 状态
    files,
    loading,
    error,
    
    // 计算属性
    fileCount,
    
    // 方法
    loadFiles,
    uploadFiles,
    downloadFile,
    deleteFile
  }
})
