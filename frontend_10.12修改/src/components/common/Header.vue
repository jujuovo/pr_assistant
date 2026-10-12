<template>
  <header class="header">
    <div class="header-content">
      <div class="left-section">
        <img src="/images/logo(1).png" alt="厦门大学校徽" class="logo" />
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
        <div v-if="!compactIdentity" class="user-profile" @click="goToProfile">
          <img :src="userAvatar" alt="用户头像" class="user-avatar" />
          <div class="user-info">
            <span class="user-name">{{ userName }}</span>
            <span class="user-role">{{ userRole }}</span>
          </div>
        </div>

        <!-- 退出按钮 -->
        <button type="button" class="logout-button" @click.stop="handleLogout" title="退出登录">
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
              <tr
                v-for="file in filesStore.files"
                :key="file.id"
                style="border-bottom: 1px solid #e9ecef"
              >
                <td style="padding: 8px">
                  <div style="display: flex; align-items: center; gap: 8px">
                    <font-awesome-icon
                      :icon="getFileIcon(file.filename)"
                      style="font-size: 16px; color: #003d86"
                    />
                    <span style="font-size: 12px; color: #333">{{ file.filename }}</span>
                  </div>
                </td>
                <td style="padding: 2px; font-size: 10px; color: #6c757d">
                  {{ formatFileSize(file.file_size || 0) }}
                </td>
                <td style="padding: 6px; text-align: center">
                  <div class="action-buttons">
                    <a
                      :href="getFileFullUrl(file.file_url) || ''"
                      class="btn-outline btn small-btn"
                      style="text-decoration: none"
                      title="下载"
                    >
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
import { useAuthStore } from '@/stores/auth.js'
import { useToastStore } from '@/stores/toast.js'
import { useFilesStore } from '@/stores/files.js'
import { getFileFullUrl } from '@/services/api.js'
const toastStore = useToastStore()

const props = defineProps({
  compactIdentity: { type: Boolean, default: false },
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
  const currentUser = authStore.user
  const facultyId = currentUser ? currentUser.facultyId : null
  await filesStore.loadFiles(facultyId)
})

// 显示文件列表
const showFiles = async () => {
  if (filesStore.files.length === 0) {
    const currentUser = authStore.user
    const facultyId = currentUser ? currentUser.facultyId : null
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
  if (!fileName) return ['fas', 'file']
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
  try {
    await authStore.logout()
    await router.replace('/login')
    toastStore.success('已退出登录')
  } catch (error) {
    console.error('退出登录失败:', error)
    await router.replace('/login')
    toastStore.error('退出登录失败，请重新登录')
  }
}
</script>

<style scoped src="@/assets/styles/components/common/Header.css"></style>
