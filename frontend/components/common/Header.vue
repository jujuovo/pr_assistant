<template>
  <header class="header">
    <div class="header-content">
      <div class="left-section">
        <img src="/images/logo(1).png" alt="厦门大学校徽" class="logo">
        <span class="system-title">{{ title }}</span>
      </div>
      
      <div class="right-section">
        <!-- 文件通知按钮 -->
        <div class="file-notice" @click="showFiles" title="查看推免相关文件">
          <div class="notice-icon-wrapper">
            <font-awesome-icon :icon="['fas', 'file-alt']" class="notice-icon" />
            <span class="notice-badge" v-if="fileCount > 0">{{ fileCount }}</span>
          </div>
          <span class="notice-text">推免文件</span>
        </div>
        
        <!-- 用户信息区域 -->
        <div class="user-profile" @click="goToProfile">
          <img :src="userAvatar" alt="用户头像" class="user-avatar">
          <div class="user-info">
            <span class="user-name">{{ userName }}</span>
            <span class="user-role">{{ userRole }}</span>
          </div>
        </div>
        
        <!-- 退出按钮 -->
        <button class="logout-button" @click="handleLogout" title="退出登录">
          <font-awesome-icon :icon="['fas', 'sign-out-alt']" />
          <span class="logout-text">退出</span>
        </button>
      </div>
    </div>
    
    <!-- 文件列表弹窗 -->
    <div v-if="isFilesModalVisible" class="overlay" @click="closeFilesModal"></div>
    <div v-if="isFilesModalVisible" class="files-modal">
      <div class="modal-header">
        <h4>推免相关文件</h4>
        <button class="close-btn" @click="closeFilesModal" title="关闭">
          <font-awesome-icon :icon="['fas', 'times']" />
        </button>
      </div>
      <div class="modal-body">
        <div class="table-container">
          <table class="application-table">
            <tbody>
              <tr v-for="file in filesStore.files" :key="file.id" style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 8px;">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <font-awesome-icon :icon="getFileIcon(file.filename)" style="font-size: 16px; color: #003d86;" />
                    <span style="font-size: 12px; color: #333;">{{ file.filename }}</span>
                  </div>
                </td>
                <td style="padding: 2px; font-size: 10px; color: #6c757d;">
                  {{ formatFileSize(file.file_size || 0) }}
                </td>
                <td style="padding: 6px; text-align: center;">
                  <div class="action-buttons">
                    <a :href="getFileFullUrl(file.file_url) || ''" class="btn-outline btn small-btn" style="text-decoration: none;" title="下载">
          <font-awesome-icon :icon="['fas', 'download']" />
        </a>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useToastStore } from '../../stores/toast'
import { useFilesStore } from '../../stores/files'
import { getFileFullUrl } from '../../utils/api'
const toastStore = useToastStore()

const props = defineProps({
  userName: String,
  userAvatar: String,
  title: {
    type: String,
    default: '推免加分系统'
  }
})

const emit = defineEmits(['go-to-profile'])

const router = useRouter()
const authStore = useAuthStore()
const filesStore = useFilesStore()

// 计算属性
const fileCount = computed(() => filesStore.fileCount)

// 计算用户角色
const userRole = computed(() => {
  const roleMap = {
    student: '学生',
    teacher: '教师',
    admin: '管理员'
  }
  return roleMap[authStore.role] || '用户'
})

const isFilesModalVisible = ref(false)

// 组件挂载时加载文件列表
onMounted(async () => {
  const currentUser = authStore.user;
  const facultyId = currentUser ? currentUser.facultyId : null;
  await filesStore.loadFiles(facultyId)
})

// 显示文件列表
const showFiles = async () => {
  if (filesStore.files.length === 0) {
    const currentUser = authStore.user;
    const facultyId = currentUser ? currentUser.facultyId : null;
    await filesStore.loadFiles(facultyId)
  }
  
  if (filesStore.files.length === 0) {
    toastStore.info('暂无推免相关文件')
    return
  }
  
  isFilesModalVisible.value = true
}

// 关闭文件列表弹窗
const closeFilesModal = () => {
  isFilesModalVisible.value = false
}

// 获取文件图标
const getFileIcon = (fileName) => {
  if (!fileName) return ['fas', 'file'];
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
    return `${size} B`
  } else if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(2)} KB`
  } else {
    return `${(size / (1024 * 1024)).toFixed(2)} MB`
  }
}

const goToProfile = () => {
  emit('go-to-profile')
}

const handleLogout = async () => {
  if (confirm('确定要退出登录吗？')) {
    try {
      await authStore.logout()
      router.push('/login')
      toastStore.success('退出登录成功')
    } catch (error) {
      console.error('退出登录失败:', error)
      router.push('/login')
      toastStore.error('退出登录失败，请重试')
    }
  }
}
</script>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: linear-gradient(135deg, #003d86 0%, #0066cc 100%);
  color: #fff;
  height: 70px;
  box-shadow: 0 4px 20px rgba(0, 45, 110, 0.25);
  transition: all 0.3s ease;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  width: 100%;
  margin: 0 auto;
}

/* 左侧区域 */
.left-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.logo {
  width: 170px;
  height: auto;
  object-fit: contain;
  filter: brightness(0) invert(1);
  transition: all 0.3s ease;
}

.system-title {
  font-size: 20px;
  font-weight: bold;
  letter-spacing: 0.5px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* 右侧区域 */
.right-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

/* 文件通知 */
.file-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 6px;
  transition: all 0.2s ease;
  background: rgba(255, 255, 255, 0.05);
}

.file-notice:hover {
  background: rgba(255, 255, 255, 0.1);
}

.notice-icon-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.notice-icon {
  font-size: 18px;
  color: #ffffff;
}

.notice-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  background-color: #ff4757;
  color: white;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  border: 2px solid #003d86;
}

.notice-text {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

/* 用户信息 */
.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  transition: all 0.2s ease;
  background: rgba(255, 255, 255, 0.05);
  margin: 0;
}

.user-profile:hover {
  background: rgba(255, 255, 255, 0.1);
}

.user-avatar {
  width: 42px;
  height: 42px;
  margin-right: 0px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  margin-bottom: 0px;
  gap: 2px;
  margin: 0;
  padding: 0;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.3;
  color: #fff;
  white-space: nowrap;
  margin: 0;
}

.user-role {
  font-size: 12px;
  opacity: 0.9;
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
  padding: 1px 8px;
  border-radius: 10px;
  white-space: nowrap;
  margin: 0;
}

/* 退出按钮 */
.logout-button {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  padding: 8px 16px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.logout-button:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.logout-text {
  font-weight: 500;
}

/* 文件弹窗样式 - 基本保持原有样式 */
.overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 9999;
}

.files-modal {
  position: fixed;
  top: 72px;
  right: 20px;
  background-color: white;
  padding: 12px;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  z-index: 10000;
  max-width: 400px;
  width: 90%;
  max-height: 50vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  border: 1px solid #e0e0e0;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid #e9ecef;
}

.modal-header h4 {
  margin: 0;
  color: #003d86;
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: #003d86;
  cursor: pointer;
  font-size: 18px;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background-color: #f5f5f5;
  color: #003d86;
}

.modal-body {
  max-height: calc(50vh - 70px);
  overflow-y: auto;
  padding: 4px;
}

.modal-body::-webkit-scrollbar {
  width: 6px;
}

.modal-body::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.modal-body::-webkit-scrollbar-thumb {
  background: #003c862d;
  border-radius: 3px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .header-content {
    padding: 0 15px;
  }
  
  .logo {
    width: 120px;
  }
  
  .system-title {
    font-size: 16px;
  }
  
  .right-section {
    gap: 10px;
  }
  
  .notice-text,
  .logout-text {
    display: none;
  }
  
  .user-info {
    display: none;
  }
  
  .file-notice,
  .user-profile {
    padding: 6px 8px;
  }
  
  .logout-button {
    padding: 8px;
  }
}

@media (max-width: 480px) {
  .header {
    height: 55px;
  }
  
  .header-content {
    padding: 0 12px;
  }
  
  .logo {
    width: 100px;
  }
  
  .system-title {
    font-size: 14px;
  }
  
  .file-notice,
  .user-profile,
  .logout-button {
    padding: 4px 6px;
  }
  
  .user-avatar {
    width: 32px;
    height: 32px;
  }
  
  .files-modal {
    right: 10px;
    left: 10px;
    width: auto;
    max-height: 50vh;
  }
}
</style>