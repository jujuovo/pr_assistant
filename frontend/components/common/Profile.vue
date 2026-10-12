<template>
  <div class="page-content">
    <div class="page-title">
      <span>个人信息</span>
      <button class="btn btn-outline" @click="toggleEdit" :disabled="saving || uploadingAvatar">
        <font-awesome-icon :icon="['fas', 'edit']" />
        {{ isEditing ? '取消编辑' : '编辑信息' }}
      </button>
    </div>

    <div class="card">
      <div class="card-title">基本资料</div>
      <form @submit.prevent="saveProfile">
        <!-- 头像显示与上传 -->
        <div class="form-row avatar-row">
          <div class="form-group avatar-group">
            <div class="avatar-container">
              <img :src="getAvatarUrl" alt="头像" class="avatar-img" />
              <div class="avatar-overlay" @click="triggerAvatarUpload">
                <font-awesome-icon :icon="['fas', 'camera']" class="avatar-icon" />
                <span>更换头像</span>
              </div>
            </div>
            <div class="avatar-tooltip">
              上传图片限制：JPG、PNG格式，大小不超过{{ avatarSizeLimit }}MB
            </div>
            <button class="btn btn-outline reset-avatar-btn" @click="resetAvatar" :disabled="uploadingAvatar">
              <font-awesome-icon :icon="['fas', 'undo']" /> 恢复默认头像
            </button>
            <input type="file" ref="avatarInput" @change="handleAvatarChange" accept="image/*" style="display: none;">
          </div>
        </div>

        <!-- 动态渲染表单字段 -->
        <div v-for="(row, rowIndex) in formRows" :key="rowIndex" class="form-row">
          <div v-for="field in row" :key="field.key" class="form-group" :class="{ [field.className]: field.className }">
            <label class="form-label">{{ field.label }}</label>
            <input type="text" class="form-control" v-model="profile[field.key]"
              :disabled="!isEditing || field.editable !== true" :required="field.required" />
          </div>
        </div>

        <div v-if="isEditing" class="form-actions">
          <button type="button" class="btn btn-outline" @click="cancelEdit" :disabled="saving">
            取消
          </button>
          <button type="submit" class="btn" :disabled="saving">
            <font-awesome-icon v-if="saving" :icon="['fas', 'spinner']" spin />
            {{ saving ? '保存中...' : '保存更改' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 修改密码 -->
    <div class="card">
      <div class="card-title">安全设置</div>
      <button class="btn btn-outline" @click="showChangePassword = true">
        <font-awesome-icon :icon="['fas', 'key']" /> 修改密码
      </button>
    </div>

    <!-- 修改密码模态框 -->
    <div v-if="showChangePassword" class="modal-overlay" @click="closePasswordModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>修改密码</h3>
          <button class="close-btn" @click="closePasswordModal">
            <font-awesome-icon :icon="['fas', 'times']" />
          </button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="changePassword">
            <div class="form-group">
              <label class="form-label">当前密码</label>
              <input type="password" class="form-control" v-model="passwordForm.currentPassword" required>
            </div>
            <div class="form-group">
              <label class="form-label">新密码</label>
              <input type="password" class="form-control" v-model="passwordForm.newPassword" required minlength="6">
              <div class="help-text">密码长度至少6位</div>
            </div>
            <div class="form-group">
              <label class="form-label">确认新密码</label>
              <input type="password" class="form-control" v-model="passwordForm.confirmPassword" required>
              <div v-if="passwordForm.newPassword !== passwordForm.confirmPassword" class="error-text">两次输入的密码不一致</div>
            </div>
          </form>
          <div class="form-actions">
            <button class="btn btn-outline" @click="closePasswordModal">取消</button>
            <button class="btn" @click="changePassword"
              :disabled="passwordForm.newPassword !== passwordForm.confirmPassword">确认修改</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useToastStore } from '../../stores/toast'
import api, { getFileFullUrl } from '../../utils/api'

const authStore = useAuthStore()
const toastStore = useToastStore()
const router = useRouter()

const isEditing = ref(false)
const saving = ref(false)
const showChangePassword = ref(false)
const uploadingAvatar = ref(false)
const avatarInput = ref(null)
const systemSettings = ref({})
const avatarSizeLimit = computed(() => systemSettings.value.avatarFileSizeLimit || 2)

const originalProfile = ref({})
const profile = reactive({})

// 计算头像URL，确保包含完整的服务器地址前缀
const getAvatarUrl = computed(() => {
  if (!profile.avatar || profile.avatar === '') return '/images/default-avatar.jpg'

  // 使用getFileFullUrl函数处理头像URL
  return getFileFullUrl(profile.avatar)
})

const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 根据用户类型配置表单字段
const getUserType = () => {
  return authStore.user?.role || ''
}

// 定义不同用户类型的表单字段配置
const formFieldsConfig = {
  student: {
    rows: [
      [
        { key: 'name', label: '姓名', editable: false, required: true },
        { key: 'studentId', label: '学号', editable: false }
      ],
      [
        { key: 'facultyName', label: '学院', editable: false },
        { key: 'majorName', label: '专业', editable: false }
      ],
      [
        { key: 'email', label: '电子邮箱', editable: true },
        { key: 'phone', label: '手机号码', editable: true }
      ]
    ],
    editableFields: ['email', 'phone']
  },
  teacher: {
    rows: [
      [
        { key: 'name', label: '姓名', editable: false, required: true },
        { key: 'teacherId', label: '工号', editable: false }
      ],
      [
        { key: 'facultyName', label: '学院', editable: false },
        { key: 'title', label: '职称', editable: true }
      ],
      [
        { key: 'email', label: '电子邮箱', editable: true },
        { key: 'phone', label: '手机号码', editable: true }
      ],
      [
        { key: 'office', label: '办公室地址', editable: true },
        { key: 'officePhone', label: '办公电话', editable: true }
      ]
    ],
    editableFields: ['title', 'email', 'phone', 'office', 'officePhone']
  },
  admin: {
    rows: [
      [
        { key: 'name', label: '姓名', editable: true, required: true },
        { key: 'adminId', label: '账号', editable: false }
      ],
      [
        { key: 'faculty', label: '学院', editable: true, required: true },
        { key: 'roleName', label: '角色', editable: true }
      ],
      [
        { key: 'email', label: '电子邮箱', editable: true },
        { key: 'phone', label: '手机号码', editable: true }
      ]
    ],
    editableFields: ['name', 'faculty', 'roleName', 'email', 'phone']
  }
}

// 根据用户类型获取表单行配置
const formRows = computed(() => {
  const userType = getUserType()
  return formFieldsConfig[userType]?.rows || []
})

// 根据用户类型获取可编辑字段列表
const getEditableFields = () => {
  const userType = getUserType()
  return formFieldsConfig[userType]?.editableFields || []
}

const toggleEdit = () => {
  if (isEditing.value) {
    // 取消编辑，恢复原始数据
    Object.assign(profile, originalProfile.value)
    isEditing.value = false
  } else {
    // 开始编辑，保存原始数据
    originalProfile.value = { ...profile }
    isEditing.value = true
  }
}

const cancelEdit = () => {
  Object.assign(profile, originalProfile.value)
  isEditing.value = false
}

const triggerAvatarUpload = () => {
  if (avatarInput.value) {
    avatarInput.value.click()
  }
}

const handleAvatarChange = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  // 检查文件大小
  const maxSize = avatarSizeLimit.value * 1024 * 1024
  if (file.size > maxSize) {
    toastStore.error(`头像文件大小不能超过${avatarSizeLimit.value}MB`)
    return
  }

  uploadingAvatar.value = true
  try {
    // 调用上传头像API
    const response = await api.uploadAvatar(authStore.user.username, file)

    // 更新用户信息
    authStore.updateUserInfo(response.user)

    // 更新本地profile中的头像
    profile.avatar = response.user.avatar

    toastStore.success('头像上传成功')
  } catch (error) {
    console.error('头像上传失败:', error)
    toastStore.error(`头像上传失败: ${error.message || '请稍后重试'}`)
  } finally {
    uploadingAvatar.value = false
    // 清空文件输入
    if (avatarInput.value) {
      avatarInput.value.value = ''
    }
  }
}

const resetAvatar = async () => {
  // 确认是否恢复默认头像
  if (!confirm('确定要恢复默认头像吗？')) {
    return
  }

  uploadingAvatar.value = true
  try {
    // 调用恢复默认头像API，传入token参数
    const response = await api.resetAvatar(authStore.user.username, authStore.user.token)

    // 更新用户信息
    authStore.updateUserInfo(response.user)

    // 更新本地profile中的头像
    profile.avatar = response.user.avatar

    toastStore.success('已恢复默认头像')
  } catch (error) {
    console.error('恢复默认头像失败:', error)
    toastStore.error(`恢复默认头像失败: ${error.message || '请稍后重试'}`)
  } finally {
    uploadingAvatar.value = false
  }
}

const saveProfile = async () => {
  saving.value = true

  try {
    // 准备更新数据
    const updateData = { username: authStore.user.username }
    const editableFields = getEditableFields()

    // 只包含可编辑字段
    editableFields.forEach(field => {
      if (profile[field] !== undefined) {
        updateData[field] = profile[field]
      }
    })

    // 调用API更新个人信息
    const response = await api.updateProfile(updateData)

    // 更新auth store中的用户信息
    authStore.updateUserInfo(response.user)

    // 对于学生用户，额外获取最新信息确保同步
    if (getUserType() === 'student') {
      await authStore.getCurrentUser()
    }

    toastStore.success('个人信息已更新')
    isEditing.value = false
  } catch (error) {
    console.error('保存失败:', error)
    toastStore.error(`保存失败: ${error.message || '请稍后重试'}`)
  } finally {
    saving.value = false
  }
}

const changePassword = async () => {
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    toastStore.error('两次输入的密码不一致')
    return
  }

  if (passwordForm.newPassword.length < 6) {
    toastStore.error('密码长度至少6位')
    return
  }

  try {
    // 准备修改密码数据
    const passwordData = {
      username: authStore.user.username,
      currentPassword: passwordForm.currentPassword,
      newPassword: passwordForm.newPassword
    }

    // 调用API修改密码
    await api.changePassword(passwordData)

    toastStore.success('密码修改成功，请重新登录')

    // 关闭弹窗
    closePasswordModal()

    // 延迟执行登出操作，确保用户看到成功提示
    setTimeout(async () => {
      // 调用登出方法
      await authStore.logout()
      // 跳转到登录页面
      router.push('/login')
    }, 200)
  } catch (error) {
    console.error('密码修改失败:', error)
    toastStore.error(`密码修改失败: ${error.message || '请稍后重试'}`)
  }
}

const closePasswordModal = () => {
  showChangePassword.value = false
  // 清空表单
  Object.assign(passwordForm, {
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
}

// 生命周期
onMounted(async () => {
  // 加载系统设置，获取头像大小限制
  try {
    const response = await api.getSystemSettings()
    systemSettings.value = response.settings
  } catch (error) {
    console.error('加载系统设置失败:', error)
    // 使用默认值
    systemSettings.value = { avatarFileSizeLimit: 2 }
  }

  // 从auth store获取当前用户信息
  if (authStore.user) {
    const user = authStore.user
    const userType = getUserType()

    // 根据用户类型初始化profile对象
    if (userType === 'student') {
      Object.assign(profile, {
        name: user.name || '',
        studentId: user.studentId || user.username || '',
        facultyId: user.facultyId || '',
        facultyName: user.faculty || '',
        majorId: user.majorId || '',
        majorName: user.major || '',
        email: user.email || '',
        phone: user.phone || '',
        avatar: user.avatar || ''
      })
    } else if (userType === 'teacher') {
      Object.assign(profile, {
        name: user.name || '',
        teacherId: user.username || '',
        facultyId: user.facultyId || '',
        facultyName: user.faculty || '',
        title: user.title || '',
        email: user.email || '',
        phone: user.phone || '',
        office: user.office || '',
        officePhone: user.officePhone || '',
        avatar: user.avatar || ''
      })
    } else if (userType === 'admin') {
      Object.assign(profile, {
        name: user.name || '',
        adminId: user.username || '',
        faculty: user.faculty || '',
        roleName: user.roleName || '',
        email: user.email || '',
        phone: user.phone || '',
        avatar: user.avatar || ''
      })
    }

    originalProfile.value = { ...profile }
  }
})
</script>

<style scoped>
/* 引入共享样式 */
@import '../common/shared-styles.css';

/* 头像样式 */
.avatar-row {
  justify-content: center;
  margin-bottom: 20px;
}

.avatar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  position: relative;
}

.avatar-container {
  position: relative;
  width: 150px;
  height: 150px;
  border-radius: 50%;
  overflow: hidden;
  border: 3px solid #e8e8e8;
  cursor: pointer;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* 添加抗锯齿效果 */
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
  /* 添加轻微阴影增强视觉效果 */
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.1);
}

.avatar-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  color: white;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.avatar-container:hover .avatar-overlay {
  opacity: 1;
}

.avatar-icon {
  font-size: 24px;
  margin-bottom: 5px;
}

.avatar-tooltip {
  position: absolute;
  top: 160px;
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
  z-index: 10;
}

.avatar-container:hover+.avatar-tooltip {
  opacity: 1;
  visibility: visible;
}

.reset-avatar-btn {
  margin-top: 10px;
  font-size: 14px;
  padding: 5px 15px;
  white-space: nowrap;
}

/* 错误文本样式 */
.error-text {
  font-size: 12px;
  color: #e74c3c;
  margin-top: 5px;
}
</style>