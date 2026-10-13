import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api.js'
import { getFileFullUrl } from '@/services/api.js'

const storageKey = import.meta.env.MODE === 'demo' ? 'gradpush-demo-auth' : 'user'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const role = ref(null)
  const isAuthenticated = ref(false)

  const userName = computed(() => {
    return user.value?.name || '张三'
  })
  const userAvatar = computed(() => {
    const avatarUrl = user.value?.avatar
    if (!avatarUrl || avatarUrl === '') {
      // 默认头像在前端public目录下，直接返回相对路径
      return '/images/default-avatar.jpg'
    }

    // 使用getFileFullUrl函数处理头像URL
    return getFileFullUrl(avatarUrl)
  })

  // 获取当前用户信息
  const getCurrentUser = async () => {
    try {
      // 使用当前已有的username调用API
      const username = user.value?.username
      if (!username) {
        throw new Error('用户名不可用')
      }
      const response = await api.getCurrentUser(username)
      // 确保提取正确的用户数据结构
      const userData = response.user || response
      user.value = userData
      role.value = userData.role
      isAuthenticated.value = true
      localStorage.setItem(storageKey, JSON.stringify(userData))
      return userData
    } catch (error) {
      console.error('获取当前用户失败:', error)
      // 失败时不抛出错误，继续使用当前数据
      return user.value
    }
  }

  const updateUserInfo = async (userData) => {
    try {
      // 直接使用传入的userData更新用户信息
      user.value = userData
      localStorage.setItem(storageKey, JSON.stringify(userData))
      return userData
    } catch (error) {
      console.error('更新用户信息失败:', error)
      throw error
    }
  }

  // 登录
  const login = async (username, password, captcha, captchaToken) => {
    try {
      const data = await api.apiRequest('/login', 'POST', {
        username,
        password,
        captcha,
        captchaToken
      })
      user.value = data.user
      role.value = data.user.role
      isAuthenticated.value = true
      localStorage.setItem(storageKey, JSON.stringify(data.user))
      return data.user
    } catch (error) {
      console.error('登录错误:', error)
      throw error
    }
  }

  // 用户注册
  const register = async (userData) => {
    try {
      // 使用api.register方法进行注册
      const result = await api.register(userData)
      return result
    } catch (error) {
      console.error('注册错误:', error)
      throw error
    }
  }

  // 密码重置
  const resetPassword = async (username, newPassword, captcha, captchaToken) => {
    try {
      // 构造数据对象并使用api.resetPassword方法
      const data = { username, newPassword, captcha, captchaToken }
      const message = await api.resetPassword(data)
      return message
    } catch (error) {
      console.error('密码重置错误:', error)
      throw error
    }
  }

  const logout = async () => {
    try {
      // 调用后端登出API
      await api.logout()
    } catch (error) {
      console.error('调用后端登出API失败:', error)
      // 即使API调用失败，也清除前端状态
    } finally {
      // 清除前端状态
      user.value = null
      role.value = null
      isAuthenticated.value = false
      localStorage.removeItem(storageKey)
    }
  }

  const initialize = async () => {
    const savedUser = localStorage.getItem(storageKey)
    if (savedUser) {
      const userData = JSON.parse(savedUser)

      // 验证用户数据是否有效，防止username为"student"等错误值
      if (userData.username && userData.username !== 'student') {
        // 先调用sessionCheck API验证后端会话是否有效
        try {
          const sessionResponse = await api.sessionCheck()

          if (sessionResponse.logged_in) {
            // 后端会话有效，使用localStorage中的用户数据
            user.value = userData
            role.value = userData.role
            isAuthenticated.value = true

            // 初始化后尝试从API获取最新的用户信息
            try {
              await getCurrentUser()
            } catch (error) {
              console.error('初始化时获取用户信息失败:', error)
              // 失败时继续使用localStorage中的数据
            }
          } else {
            // 后端会话无效，清除前端状态
            // console.log('后端会话已过期或无效，清除前端状态')
            localStorage.removeItem(storageKey)
            user.value = null
            role.value = null
            isAuthenticated.value = false
          }
        } catch (error) {
          console.error('会话检查失败:', error)
          // API调用失败时，保守处理，清除前端状态
          localStorage.removeItem(storageKey)
          user.value = null
          role.value = null
          isAuthenticated.value = false
        }
      } else {
        // 如果用户数据无效，清除localStorage并重置状态
        localStorage.removeItem(storageKey)
        user.value = null
        role.value = null
        isAuthenticated.value = false
        console.log('检测到无效的用户数据，已清除')
      }
    }
  }

  return {
    user,
    role,
    isAuthenticated,
    userName,
    userAvatar,
    login,
    register,
    resetPassword,
    logout,
    initialize,
    getCurrentUser,
    updateUserInfo
  }
})
