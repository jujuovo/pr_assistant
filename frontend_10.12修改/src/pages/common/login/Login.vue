<template>
  <div class="login-page">
    <!-- 简化背景效果 -->
    <div class="background-container">
      <div class="background-blur"></div>
      <div class="background-overlay"></div>
    </div>

    <div class="login-container">
      <!-- 合并后的登录内容区域 -->
      <div class="login-content">
        <!-- 左侧信息显示区域 - 优化后 -->
        <div class="info-panel">
          <div class="info-content">
            <div class="logo-area">
              <div class="logo">
                <img src="/images/logo(1).png" alt="系统logo" style="width: 260px; height: 60px" />
              </div>
              <div class="logo-text">
                <span class="system-name">推免加分系统</span>
                <span class="auth-title">厦门大学</span>
              </div>
            </div>

            <div class="welcome-content">
              <h1 class="welcome-title">欢迎使用推免加分系统</h1>
              <p class="welcome-subtitle">便捷的在线申请平台</p>
              <p class="welcome-subtitle">助您顺利完成推免加分申请流程</p>

              <!-- 优化时间信息卡片 -->
              <div class="time-card">
                <div class="time-header">
                  <div class="time-icon">
                    <font-awesome-icon :icon="['fas', 'calendar-check']" />
                  </div>
                  <div class="time-header-text">
                    <div class="time-title">推免申请开放时间</div>
                    <div class="time-subtitle">请在规定时间内完成申请</div>
                  </div>
                </div>
                <div class="time-dates">
                  <div class="time-item">
                    <div class="time-item-icon">
                      <font-awesome-icon :icon="['fas', 'hourglass-start']" />
                    </div>
                    <div class="time-item-content">
                      <div class="time-label">开放时间</div>
                      <div class="time-value">
                        {{ applicationTimeStart }}
                        <div v-if="settingsLoading" class="loading-spinner-small"></div>
                      </div>
                    </div>
                  </div>
                  <div class="time-item">
                    <div class="time-item-icon">
                      <font-awesome-icon :icon="['fas', 'hourglass-end']" />
                    </div>
                    <div class="time-item-content">
                      <div class="time-label">截止时间</div>
                      <div class="time-value">
                        {{ applicationTimeEnd }}
                        <div v-if="settingsLoading" class="loading-spinner-small"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧登录区域 -->
        <div class="login-box">
          <div class="login-header">
            <h2 class="login-title">统一身份认证</h2>
            <p class="login-subtitle">请使用您的学号/工号登录系统</p>
          </div>

          <div class="login-tabs">
            <button class="tab-btn active">
              {{
                activeTab === 'login'
                  ? '账号登录'
                  : activeTab === 'register'
                    ? '账号注册'
                    : '密码重置'
              }}
            </button>
          </div>

          <div class="form-container">
            <!-- 登录表单 -->
            <form v-if="activeTab === 'login'" class="login-form" @submit.prevent="handleLogin">
              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'user']" class="input-icon" />
                <input
                  type="text"
                  v-model="loginForm.username"
                  placeholder="请输入学号/工号"
                  required
                />
              </div>
              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'lock']" class="input-icon" />
                <input
                  type="password"
                  v-model="loginForm.password"
                  placeholder="请输入密码"
                  required
                />
              </div>
              <div class="input-group captcha-group">
                <div style="display: flex; align-items: center; gap: 10px; width: 100%">
                  <div style="flex: 1; position: relative">
                    <font-awesome-icon :icon="['fas', 'shield-alt']" class="input-icon" />
                    <input
                      type="text"
                      v-model="loginForm.captcha"
                      placeholder="请输入验证码"
                      required
                    />
                  </div>
                  <div style="position: relative; display: inline-block">
                    <img
                      :src="captchaImage"
                      alt="验证码"
                      style="
                        max-height: 50px;
                        max-width: 90px;
                        width: 100%;
                        height: auto;
                        cursor: pointer;
                        border-radius: 8px;
                      "
                      @click="refreshCaptcha"
                      title="点击刷新"
                    />
                    <div v-if="captchaLoading" class="captcha-loading-overlay">
                      <div class="loading-spinner-small" style="width: 20px; height: 20px"></div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="form-actions">
                <div class="links-container">
                  <a href="#" class="tab-link" @click.prevent="switchTab('forgot')"> 忘记密码? </a>
                  <a href="#" class="tab-link" @click.prevent="switchTab('register')"> 注册账号 </a>
                </div>
                <button type="submit" class="login-btn" :class="{ loading }" :disabled="loading">
                  <span class="btn-text">登录</span>
                  <div class="btn-loading">
                    <font-awesome-icon :icon="['fas', 'spinner']" spin />
                  </div>
                </button>
              </div>
            </form>

            <!-- 注册表单 -->
            <form
              v-else-if="activeTab === 'register'"
              class="register-form"
              @submit.prevent="handleRegister"
            >
              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'user']" class="input-icon" />
                <input
                  type="text"
                  v-model="registerForm.username"
                  placeholder="请输入学号/工号 (5-20个字符)"
                  required
                  minlength="5"
                  maxlength="20"
                />
              </div>

              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'user-tag']" class="input-icon" />
                <input
                  type="text"
                  v-model="registerForm.name"
                  placeholder="请输入姓名 (2-20个字符)"
                  required
                  minlength="2"
                  maxlength="20"
                />
              </div>

              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'user-shield']" class="input-icon" />
                <select v-model="registerForm.role" required @change="handleRoleChange">
                  <option value="">请选择角色</option>
                  <option value="student">学生</option>
                  <option value="teacher">教师</option>
                </select>
              </div>

              <!-- 学院选择 -->
              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'university']" class="input-icon" />
                <select v-model="registerForm.facultyId" required @change="handleFacultyChange">
                  <option value="">请选择学院</option>
                  <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">
                    {{ faculty.name }}
                  </option>
                </select>
              </div>

              <!-- 系选择（仅学生显示） -->
              <div class="input-group" v-if="registerForm.role === 'student'">
                <font-awesome-icon :icon="['fas', 'building']" class="input-icon" />
                <select
                  v-model="registerForm.departmentId"
                  required
                  @change="handleDepartmentChange"
                >
                  <option value="">请选择系</option>
                  <option
                    v-for="department in departments"
                    :key="department.id"
                    :value="department.id"
                  >
                    {{ department.name }}
                  </option>
                </select>
              </div>

              <!-- 专业选择（仅学生显示） -->
              <div class="input-group" v-if="registerForm.role === 'student'">
                <font-awesome-icon :icon="['fas', 'graduation-cap']" class="input-icon" />
                <select v-model="registerForm.majorId" required>
                  <option value="">请选择专业</option>
                  <option v-for="major in majors" :key="major.id" :value="major.id">
                    {{ major.name }}
                  </option>
                </select>
              </div>

              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'lock']" class="input-icon" />
                <input
                  type="password"
                  v-model="registerForm.password"
                  placeholder="请设置密码"
                  required
                  minlength="6"
                />
              </div>

              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'lock']" class="input-icon" />
                <input
                  type="password"
                  v-model="registerForm.confirmPassword"
                  placeholder="请确认密码"
                  required
                  minlength="6"
                />
              </div>
              <div class="input-group captcha-group">
                <div style="display: flex; align-items: center; gap: 10px; width: 100%">
                  <div style="flex: 1; position: relative">
                    <font-awesome-icon :icon="['fas', 'shield-alt']" class="input-icon" />
                    <input
                      type="text"
                      v-model="registerForm.captcha"
                      placeholder="请输入验证码"
                      required
                    />
                  </div>
                  <div style="position: relative; display: inline-block">
                    <img
                      :src="captchaImage"
                      alt="验证码"
                      style="
                        max-height: 50px;
                        max-width: 90px;
                        width: 100%;
                        height: auto;
                        cursor: pointer;
                        border-radius: 8px;
                      "
                      @click="refreshCaptcha"
                      title="点击刷新"
                    />
                    <div v-if="captchaLoading" class="captcha-loading-overlay">
                      <div class="loading-spinner-small" style="width: 20px; height: 20px"></div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="form-actions">
                <div class="links-container">
                  <a href="#" class="tab-link" @click.prevent="switchTab('login')">
                    已有账号？立即登录
                  </a>
                </div>
                <button type="submit" class="login-btn" :class="{ loading }" :disabled="loading">
                  <span class="btn-text">注册</span>
                  <div class="btn-loading">
                    <font-awesome-icon :icon="['fas', 'spinner']" spin />
                  </div>
                </button>
              </div>
            </form>

            <!-- 忘记密码表单 -->
            <form
              v-else-if="activeTab === 'forgot'"
              class="login-form"
              @submit.prevent="handleResetPassword"
            >
              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'user']" class="input-icon" />
                <input
                  type="text"
                  v-model="resetForm.username"
                  placeholder="请输入学号/工号"
                  required
                />
              </div>

              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'lock']" class="input-icon" />
                <input
                  type="password"
                  v-model="resetForm.newPassword"
                  placeholder="请设置新密码"
                  required
                  minlength="6"
                />
              </div>

              <div class="input-group">
                <font-awesome-icon :icon="['fas', 'lock']" class="input-icon" />
                <input
                  type="password"
                  v-model="resetForm.confirmPassword"
                  placeholder="请确认新密码"
                  required
                  minlength="6"
                />
              </div>
              <div class="input-group captcha-group">
                <div style="display: flex; align-items: center; gap: 10px; width: 100%">
                  <div style="flex: 1; position: relative">
                    <font-awesome-icon :icon="['fas', 'shield-alt']" class="input-icon" />
                    <input
                      type="text"
                      v-model="resetForm.captcha"
                      placeholder="请输入验证码"
                      required
                    />
                  </div>
                  <div style="position: relative; display: inline-block">
                    <img
                      :src="captchaImage"
                      alt="验证码"
                      style="
                        max-height: 50px;
                        max-width: 90px;
                        width: 100%;
                        height: auto;
                        cursor: pointer;
                        border-radius: 8px;
                      "
                      @click="refreshCaptcha"
                      title="点击刷新"
                    />
                    <div v-if="captchaLoading" class="captcha-loading-overlay">
                      <div class="loading-spinner-small" style="width: 20px; height: 20px"></div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="form-actions">
                <div class="links-container">
                  <a href="#" class="tab-link" @click.prevent="switchTab('login')"> 返回登录 </a>
                </div>
                <button type="submit" class="login-btn" :class="{ loading }" :disabled="loading">
                  <span class="btn-text">重置</span>
                  <div class="btn-loading">
                    <font-awesome-icon :icon="['fas', 'spinner']" spin />
                  </div>
                </button>
              </div>
            </form>
          </div>

          <div class="help-area">
            <template v-if="activeTab === 'login'">
              <p class="help-text">首次登录请点击"注册账号"进行设置</p>
              <p class="help-text">若密码遗忘可通过"忘记密码"进行重置</p>
            </template>
            <template v-else-if="activeTab === 'register'">
              <p class="help-text">管理员账号请联系系统管理员开通</p>
              <p class="help-text">如有疑问，请联系系统技术支持</p>
            </template>
            <template v-else-if="activeTab === 'forgot'">
              <p class="help-text">请输入学号/工号以进行密码重置</p>
              <p class="help-text">请妥善保管您的密码信息</p>
            </template>
          </div>
        </div>
      </div>
    </div>
    <Footer />
  </div>
</template>

<script setup>
import Footer from '@/components/common/Footer.vue'
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { useToastStore } from '@/stores/toast.js'
import api from '@/services/api.js'

// 添加小型加载动画样式
const style = document.createElement('style')
style.textContent = `
.loading-spinner-small {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #f3f3f3;
  border-top: 2px solid #3498db;
  border-radius: 50%;
  animation: spin-small 1s linear infinite;
  vertical-align: middle;
  margin-left: 5px;
}

@keyframes spin-small {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.captcha-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(255, 255, 255, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 8px;
}
`
document.head.appendChild(style)

const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()

// 组件挂载时自动获取验证码
onMounted(() => {
  refreshCaptcha()
})

// 标签页状态管理
const activeTab = ref('login') // 'login', 'register', 'forgot'
const loading = ref(false)
const loadingOptions = ref(false)

// 标签页切换函数
const switchTab = (tab) => {
  activeTab.value = tab
  // 切换标签页时刷新验证码
  refreshCaptcha()
}

// 登录表单数据
const loginForm = reactive({
  username: '',
  password: '',
  captcha: ''
})

// 验证码相关
const captchaImage = ref('')
const captchaToken = ref('')
const captchaLoading = ref(false)
const captchaTimer = ref(null)
const CAPTCHA_EXPIRE_TIME = 300000 // 验证码过期时间，单位毫秒（5分钟）- 与后端保持一致

// 获取验证码
const refreshCaptcha = async () => {
  // 清除之前的定时器
  if (captchaTimer.value) {
    clearTimeout(captchaTimer.value)
    captchaTimer.value = null
  }

  captchaLoading.value = true
  try {
    // 使用项目已有的api模块获取验证码
    const response = await api.generateCaptcha()
    // 将base64字符串转换为可显示的图片
    captchaImage.value = `data:image/png;base64,${response.image}`
    // 保存验证码token
    captchaToken.value = response.token

    // 设置验证码过期定时器
    captchaTimer.value = setTimeout(() => {
      refreshCaptcha()
    }, CAPTCHA_EXPIRE_TIME)
  } catch (error) {
    console.error('获取验证码失败:', error)
    toastStore.error('获取验证码失败，请刷新页面重试')
  } finally {
    captchaLoading.value = false
  }
}

// 注册表单数据
const registerForm = reactive({
  username: '',
  name: '',
  password: '',
  confirmPassword: '',
  role: '',
  facultyId: '',
  departmentId: '',
  majorId: '',
  captcha: ''
})

// 忘记密码表单数据
const resetForm = reactive({
  username: '',
  newPassword: '',
  confirmPassword: '',
  captcha: ''
})

// 下拉选项数据（注册用）
const faculties = ref([])
const departments = ref([])
const majors = ref([])

// 申请时间相关数据
const applicationTimeStart = ref('')
const applicationTimeEnd = ref('')
const settingsLoading = ref(false)

// 注册表单验证
const isRegisterFormValid = computed(() => {
  const { username, name, password, confirmPassword, role, facultyId, departmentId, majorId } =
    registerForm

  // 基本字段验证
  if (!username || !name || !password || !confirmPassword || !role || !facultyId) {
    return false
  }

  // 用户名长度验证
  if (username.length < 5 || username.length > 20) {
    return false
  }

  // 姓名长度验证
  if (name.length < 2 || name.length > 20) {
    return false
  }

  // 学生需要验证系和专业
  if (role === 'student' && (!departmentId || !majorId)) {
    return false
  }

  // 密码一致性验证
  if (password !== confirmPassword) {
    return false
  }

  // 密码长度验证
  if (password.length < 6) {
    return false
  }

  return true
})

// 组件挂载时加载数据
onMounted(async () => {
  await Promise.all([loadFaculties(), loadPublicSystemInfo()])
  // 加载验证码
  refreshCaptcha()
})

// 组件卸载时清除定时器，防止内存泄漏
onUnmounted(() => {
  if (captchaTimer.value) {
    clearTimeout(captchaTimer.value)
    captchaTimer.value = null
  }
})

// 加载公开系统信息，获取申请时间
const loadPublicSystemInfo = async () => {
  try {
    settingsLoading.value = true
    const response = await api.getPublicSystemInfo()

    // 格式化申请时间 - 数据在response.data对象中
    if (response.data && response.data.applicationStartTime) {
      applicationTimeStart.value = formatDate(response.data.applicationStartTime)
    }
    if (response.data && response.data.applicationEndTime) {
      applicationTimeEnd.value = formatDate(response.data.applicationEndTime)
    }
  } catch (error) {
    console.error('加载公开系统信息失败:', error)
    console.log('使用默认时间:', applicationTimeStart.value, applicationTimeEnd.value)
  } finally {
    settingsLoading.value = false
  }
}

// 格式化日期时间（参考SystemSettings.vue的方式，正确处理UTC+8时区）
const formatDate = (dateString) => {
  try {
    if (typeof dateString === 'string') {
      // 检查是否是纯日期格式 YYYY-MM-DD
      const dateOnlyRegex = /^(\d{4})-(\d{2})-(\d{2})$/
      if (dateOnlyRegex.test(dateString)) {
        const dateMatch = dateString.match(dateOnlyRegex)
        const year = dateMatch[1]
        const month = dateMatch[2]
        const day = dateMatch[3]

        const result = `${year}年${month}月${day}日`
        return result
      }

      // 对于带时间的格式，参考SystemSettings.vue中的处理方式
      // 首先确保日期字符串包含有效的时间信息
      let processedDateString = dateString

      // 如果没有时区信息，添加UTC+8时区标记
      if (!dateString.includes('+') && !dateString.includes('Z')) {
        // 如果是空格分隔的格式，转换为T分隔的ISO格式
        if (dateString.includes(' ')) {
          processedDateString = dateString.replace(' ', 'T')
        }
        // 添加UTC+8时区标记
        processedDateString = processedDateString + '+08:00'
      }

      // 创建Date对象处理时间，确保正确解析带时区的时间
      const date = new Date(processedDateString)

      // 检查是否为有效日期
      if (isNaN(date.getTime())) {
        console.warn('无效的日期格式:', dateString)
        return dateString
      }

      // 格式化显示为本地时间（UTC+8）
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')

      const result = `${year}年${month}月${day}日 ${hours}:${minutes}`
      return result
    }

    console.error('无法解析的日期:', dateString)
    return String(dateString)
  } catch (error) {
    console.error('日期格式化错误:', error)
    return String(dateString)
  }
}

// 加载学院列表（注册用）
const loadFaculties = async () => {
  try {
    loadingOptions.value = true
    const response = await api.getFaculties()
    faculties.value = response.faculties
  } catch (error) {
    console.error('加载学院列表失败:', error)
    toastStore.error('加载学院列表失败，请刷新页面重试')
  } finally {
    loadingOptions.value = false
  }
}

// 加载系列表（注册用）
const loadDepartments = async (facultyId) => {
  try {
    loadingOptions.value = true
    if (facultyId) {
      const response = await api.getDepartmentsByFaculty(facultyId)
      departments.value = response.departments
      // 重置系和专业选择
      registerForm.departmentId = ''
      registerForm.majorId = ''
      majors.value = []
    }
  } catch (error) {
    console.error('加载系列表失败:', error)
    toastStore.error('加载系列表失败，请重试')
  } finally {
    loadingOptions.value = false
  }
}

// 加载专业列表（注册用）
const loadMajors = async (departmentId) => {
  try {
    loadingOptions.value = true
    if (departmentId) {
      const response = await api.getMajorsByDepartment(departmentId)
      majors.value = response.majors
      // 重置专业选择
      registerForm.majorId = ''
    }
  } catch (error) {
    console.error('加载专业列表失败:', error)
    toastStore.error('加载专业列表失败，请重试')
  } finally {
    loadingOptions.value = false
  }
}

// 角色变化处理（注册用）
const handleRoleChange = () => {
  // 重置学院、系和专业选择
  registerForm.facultyId = ''
  registerForm.departmentId = ''
  registerForm.majorId = ''
  departments.value = []
  majors.value = []
}

// 学院变化处理（注册用）
const handleFacultyChange = () => {
  if (registerForm.facultyId) {
    loadDepartments(registerForm.facultyId)
  } else {
    // 重置系和专业选择
    registerForm.departmentId = ''
    registerForm.majorId = ''
    departments.value = []
    majors.value = []
  }
}

// 系变化处理（注册用）
const handleDepartmentChange = () => {
  if (registerForm.departmentId) {
    loadMajors(registerForm.departmentId)
  } else {
    // 重置专业选择
    registerForm.majorId = ''
    majors.value = []
  }
}

// 登录处理
const handleLogin = async () => {
  // 验证验证码是否输入
  if (!loginForm.captcha.trim()) {
    toastStore.error('请输入验证码')
    return
  }

  // 验证验证码token是否存在
  if (!captchaToken.value) {
    toastStore.error('验证码已失效，请刷新页面重新获取验证码')
    return
  }

  // 演示构建使用固定账号，避免后端状态和申请时间校验阻断角色体验。
  if (import.meta.env.MODE === 'demo') {
    const demoAccounts = new Set(['student001', 'teacher001', 'admin001'])
    const username = loginForm.username.trim()

    if (
      !demoAccounts.has(username) ||
      loginForm.password !== 'demo123' ||
      loginForm.captcha.trim() !== '1234'
    ) {
      toastStore.error('账号、密码或验证码错误，请使用页面提供的演示账号登录')
      refreshCaptcha()
      return
    }
  }

  loading.value = true

  try {
    // 使用auth store的登录方法，包含验证码和验证码token
    await authStore.login(
      loginForm.username,
      loginForm.password,
      loginForm.captcha,
      captchaToken.value
    )

    // 演示账号完成认证后直接进入对应角色首页；正式环境继续执行下方业务校验。
    if (import.meta.env.MODE === 'demo') {
      const demoRouteMap = {
        student: '/student',
        teacher: '/teacher',
        admin: '/admin'
      }
      await router.replace(demoRouteMap[authStore.role] || '/login')
      toastStore.success('登录成功')
      return
    }

    // 检查系统维护状态
    try {
      const systemInfoResponse = await api.getPublicSystemInfo()
      const systemStatus = systemInfoResponse.data?.status

      // 如果系统处于维护模式且用户不是管理员，则阻止登录
      if (systemStatus === '维护中' && authStore.role !== 'admin') {
        await authStore.logout()
        toastStore.error('系统正在维护中，暂时无法登录，请稍后再试')
        return
      }
    } catch (systemStatusError) {
      console.error('系统状态检查失败:', systemStatusError)
      // 如果获取系统状态失败，继续登录流程
    }

    // 学生角色登录时间验证
    if (authStore.role === 'student') {
      const now = new Date()

      // 尝试重新获取最新的系统信息，确保时间准确
      try {
        const systemInfoResponse = await api.getPublicSystemInfo()
        const startTimeStr = systemInfoResponse.data?.applicationStartTime
        const endTimeStr = systemInfoResponse.data?.applicationEndTime

        // 直接使用API返回的原始时间字符串，确保包含时区信息
        if (!startTimeStr || !endTimeStr) {
          throw new Error('系统时间配置不完整')
        }

        // 确保时间字符串包含时区信息
        const processTimeString = (timeStr) => {
          if (typeof timeStr === 'string') {
            if (!timeStr.includes('+') && !timeStr.includes('Z')) {
              // 如果没有时区信息，添加UTC+8时区标记
              return timeStr.replace(' ', 'T') + '+08:00'
            }
            return timeStr
          }
          return timeStr
        }

        const processedStartTime = processTimeString(startTimeStr)
        const processedEndTime = processTimeString(endTimeStr)

        const startTime = new Date(processedStartTime)
        const endTime = new Date(processedEndTime)

        // 检查是否为有效日期
        if (isNaN(startTime.getTime()) || isNaN(endTime.getTime())) {
          throw new Error('系统时间格式错误')
        }

        // 检查当前时间是否在申请时间范围内
        if (now < startTime) {
          // 退出登录并提示错误
          await authStore.logout()
          toastStore.error(`申请未开始，开始时间：${formatDate(startTimeStr)}`)
          return
        } else if (now > endTime) {
          await authStore.logout()
          toastStore.error(`申请已结束，结束时间：${formatDate(endTimeStr)}`)
          return
        }
      } catch (systemInfoError) {
        console.error('时间验证失败:', systemInfoError)
        // 获取失败时使用更明确的错误处理
        await authStore.logout()
        toastStore.error(`系统时间验证失败，请联系管理员`)
        return
      }
    }

    // 登录成功，根据角色跳转
    const routeMap = {
      student: '/student',
      teacher: '/teacher',
      admin: '/admin'
    }

    router.push(routeMap[authStore.role])
  } catch (error) {
    console.error('登录错误:', error)
    toastStore.error(error.message || '登录失败，请稍后重试')
    // 登录失败后刷新验证码
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}

// 注册处理
const handleRegister = async () => {
  // 检测输入框是否为空
  if (!registerForm.username.trim()) {
    toastStore.error('请输入学号/工号')
    return
  }
  if (!registerForm.name.trim()) {
    toastStore.error('请输入姓名')
    return
  }
  if (!registerForm.password) {
    toastStore.error('请设置密码')
    return
  }
  if (!registerForm.confirmPassword) {
    toastStore.error('请确认密码')
    return
  }
  if (!registerForm.role) {
    toastStore.error('请选择角色')
    return
  }
  if (!registerForm.facultyId) {
    toastStore.error('请选择学院')
    return
  }
  if (registerForm.role === 'student' && !registerForm.departmentId) {
    toastStore.error('请选择系')
    return
  }
  if (registerForm.role === 'student' && !registerForm.majorId) {
    toastStore.error('请选择专业')
    return
  }
  // 验证码验证
  if (!registerForm.captcha.trim()) {
    toastStore.error('请输入验证码')
    return
  }
  if (!captchaToken.value) {
    toastStore.error('验证码已失效，请刷新验证码')
    return
  }

  // 用户名长度验证
  if (registerForm.username.length < 5 || registerForm.username.length > 20) {
    toastStore.error('学号/工号长度必须在5-20个字符之间')
    return
  }

  // 姓名长度验证
  if (registerForm.name.length < 2 || registerForm.name.length > 20) {
    toastStore.error('姓名长度必须在2-20个字符之间')
    return
  }

  // 密码一致性和长度验证
  if (registerForm.password !== registerForm.confirmPassword) {
    toastStore.error('两次输入的密码不一致')
    return
  }
  if (registerForm.password.length < 6) {
    toastStore.error('密码长度不能少于6位')
    return
  }

  loading.value = true

  try {
    // 使用auth store的注册方法，包含验证码和验证码token
    await authStore.register({
      username: registerForm.username,
      name: registerForm.name,
      password: registerForm.password,
      role: registerForm.role,
      facultyId: registerForm.facultyId,
      departmentId: registerForm.departmentId,
      majorId: registerForm.majorId,
      captcha: registerForm.captcha,
      captchaToken: captchaToken.value
    })

    // 注册成功后跳转到登录标签页
    toastStore.success('注册成功！请使用您的账号密码登录')
    switchTab('login')
    // 清空注册表单
    Object.assign(registerForm, {
      username: '',
      name: '',
      password: '',
      confirmPassword: '',
      role: '',
      facultyId: '',
      departmentId: '',
      majorId: ''
    })
  } catch (error) {
    console.error('注册错误:', error)
    toastStore.error(`注册失败: ${error.message || '请稍后重试'}`)
    // 注册失败后刷新验证码
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}

// 密码重置处理
const handleResetPassword = async () => {
  // 检测输入框是否为空
  if (!resetForm.username.trim()) {
    toastStore.error('请输入学号/工号')
    return
  }
  if (!resetForm.newPassword) {
    toastStore.error('请设置新密码')
    return
  }
  if (!resetForm.confirmPassword) {
    toastStore.error('请确认新密码')
    return
  }
  // 验证码验证
  if (!resetForm.captcha.trim()) {
    toastStore.error('请输入验证码')
    return
  }
  if (!captchaToken.value) {
    toastStore.error('验证码已失效，请刷新验证码')
    return
  }

  // 密码一致性和长度验证
  if (resetForm.newPassword !== resetForm.confirmPassword) {
    toastStore.error('两次输入的密码不一致')
    return
  }
  if (resetForm.newPassword.length < 6) {
    toastStore.error('密码长度不能少于6位')
    return
  }

  loading.value = true

  try {
    // 调用密码重置函数，包含验证码和验证码token
    await authStore.resetPassword(
      resetForm.username,
      resetForm.newPassword,
      resetForm.captcha,
      captchaToken.value
    )

    toastStore.success('密码重置成功！请使用新密码登录')
    switchTab('login')
    // 清空重置表单
    Object.assign(resetForm, {
      username: '',
      newPassword: '',
      confirmPassword: ''
    })
  } catch (error) {
    console.error('密码重置错误:', error)
    toastStore.error(`密码重置失败: ${error.message || '请稍后重试'}`)
    // 密码重置失败后刷新验证码
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped src="@/assets/styles/pages/common/login/Login.css"></style>
