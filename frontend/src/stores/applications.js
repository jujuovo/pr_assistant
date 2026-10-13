import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api.js'

export const useApplicationsStore = defineStore('applications', () => {
  // 辅助函数：字段名转换
  const transformFieldNames = (data) => {
    // 字段名映射：前端驼峰式命名 -> 后端下划线命名
    const fieldMapping = {
      studentId: 'student_id',
      studentName: 'student_name',
      name: 'student_name', // 兼容前端使用name字段的情况
      facultyId: 'faculty_id',
      departmentId: 'department_id',
      majorId: 'major_id',
      applicationType: 'application_type',
      selfScore: 'self_score',
      projectName: 'project_name',
      awardDate: 'award_date',
      finalScore: 'final_score',
      reviewComment: 'review_comment',
      reviewedAt: 'reviewed_at',
      reviewedBy: 'reviewed_by',
      appliedAt: 'applied_at',
      createdAt: 'created_at',
      updatedAt: 'updated_at',
      dynamicCoefficients: 'dynamic_coefficients'
    }

    // 创建反向映射：后端下划线命名 -> 前端驼峰式命名
    const reverseFieldMapping = {}
    for (const [frontendKey, backendKey] of Object.entries(fieldMapping)) {
      reverseFieldMapping[backendKey] = frontendKey
    }

    // 如果不是对象或为null，直接返回
    if (typeof data !== 'object' || data === null) {
      return data
    }

    // 转换数据字段
    const transformedData = {}
    for (const [key, value] of Object.entries(data)) {
      let newKey

      // 检查是否需要进行字段名转换
      if (fieldMapping[key]) {
        // 前端到后端：使用fieldMapping转换
        newKey = fieldMapping[key]
      } else if (reverseFieldMapping[key]) {
        // 后端到前端：使用reverseFieldMapping转换
        newKey = reverseFieldMapping[key]
      } else {
        // 不需要转换的字段
        newKey = key
      }

      // 处理嵌套对象
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        // 特殊处理dynamicCoefficients/dynamic_coefficients对象，不转换内部字段
        if (key === 'dynamicCoefficients' || key === 'dynamic_coefficients') {
          transformedData[newKey] = { ...value }
        } else {
          // 递归转换其他嵌套对象
          transformedData[newKey] = transformFieldNames(value)
        }
      } else {
        // 非对象类型直接赋值
        transformedData[newKey] = value
      }
    }

    return transformedData
  }

  // 状态定义
  const applications = ref([])
  const loading = ref(false)
  const error = ref(null)

  // 计算属性
  const pendingApplications = computed(() => {
    return applications.value.filter((app) => app.status === 'pending')
  })

  const reviewedApplications = computed(() => {
    return applications.value.filter(
      (app) => app.status === 'approved' || app.status === 'rejected'
    )
  })

  const totalApplications = computed(() => applications.value.length)

  // 从API获取所有申请
  const fetchApplications = async (filters = {}) => {
    loading.value = true
    error.value = null

    try {
      const queryParams = new URLSearchParams()
      if (filters.studentId) queryParams.append('studentId', filters.studentId)
      if (filters.studentName) queryParams.append('studentName', filters.studentName)
      if (filters.faculty) {
        queryParams.append('facultyId', filters.faculty)
      }
      // 使用departmentId而不是department来传递系ID
      if (filters.department && filters.department !== 'all') {
        queryParams.append('departmentId', filters.department)
      }
      // 使用majorId而不是major来传递专业ID
      if (filters.major && filters.major !== 'all') {
        queryParams.append('majorId', filters.major)
      }
      if (filters.status) queryParams.append('status', filters.status)
      if (filters.applicationType) queryParams.append('applicationType', filters.applicationType)
      if (filters.rule) queryParams.append('ruleId', filters.rule)
      if (filters.reviewedBy) queryParams.append('reviewedBy', filters.reviewedBy)
      if (filters.reviewedStartDate)
        queryParams.append('reviewedStartDate', filters.reviewedStartDate)
      if (filters.reviewedEndDate) queryParams.append('reviewedEndDate', filters.reviewedEndDate)

      const queryString = queryParams.toString() ? `?${queryParams.toString()}` : ''
      const data = await api.apiRequest(`/applications${queryString}`)
      applications.value = data
      return data
    } catch (err) {
      console.error('加载申请数据失败:', err)
      error.value = '加载数据失败，请刷新页面重试'
      applications.value = []
      throw err
    } finally {
      loading.value = false
    }
  }

  // 从API获取单个申请详情
  const fetchApplicationById = async (applicationId) => {
    loading.value = true
    error.value = null

    try {
      const data = await api.apiRequest(`/applications/${applicationId}`)
      // 转换字段名，确保前端使用正确的命名方式
      const transformedData = transformFieldNames(data)
      return transformedData
    } catch (err) {
      console.error('加载申请详情失败:', err)
      error.value = '加载申请详情失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  // 从API获取待审核申请
  const fetchPendingApplications = async (filters = {}) => {
    loading.value = true
    error.value = null

    try {
      const queryParams = new URLSearchParams()
      if (filters.faculty) {
        queryParams.append('facultyId', filters.faculty)
      }
      // 使用departmentId而不是department来传递系ID
      if (filters.department && filters.department !== 'all') {
        queryParams.append('departmentId', filters.department)
      }
      // 使用majorId而不是major来传递专业ID
      if (filters.major && filters.major !== 'all') {
        queryParams.append('majorId', filters.major)
      }
      if (filters.applicationType) queryParams.append('applicationType', filters.applicationType)
      if (filters.rule) queryParams.append('ruleId', filters.rule)
      if (filters.studentId) queryParams.append('studentId', filters.studentId)
      if (filters.studentName) queryParams.append('studentName', filters.studentName)

      const queryString = queryParams.toString() ? `?${queryParams.toString()}` : ''
      const data = await api.apiRequest(`/applications/pending${queryString}`)
      // 将获取到的待审核申请保存到store中
      applications.value = data
      return data
    } catch (err) {
      console.error('加载待审核申请失败:', err)
      error.value = '加载待审核申请失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  // 添加新申请
  const addApplication = async (application) => {
    loading.value = true
    error.value = null

    try {
      // 创建FormData对象来处理文件上传
      const formData = new FormData()

      // 将非文件字段添加到FormData
      const applicationData = { ...application }
      // 处理files字段，只保留后端需要的信息
      if (applicationData.files) {
        applicationData.files = applicationData.files.map((file) => {
          // 只保留后端需要的字段，不包含File实例
          if (file.isBackendFile) {
            return { id: file.id, name: file.name, path: file.path, size: file.size }
          }
          return { name: file.name }
        })
      }
      // 保存原始files数组用于单独处理File实例
      const files = application.files || []

      // 使用辅助函数转换字段名
      const transformedData = transformFieldNames(applicationData)

      // 将转换后的application数据作为JSON字符串添加到FormData
      formData.append('application', JSON.stringify(transformedData))

      // 添加文件到FormData - 只添加新上传的浏览器File对象
      // 从后端加载的文件（非File实例）不会被添加，后端会保留这些文件
      files.forEach((file) => {
        if (file instanceof File) {
          formData.append('files', file)
        }
      })

      // 发送请求
      const data = await api.apiRequest('/applications', 'POST', formData)

      // 获取完整的申请数据
      const newApplication = await fetchApplicationById(data.id)
      applications.value.unshift(newApplication)
      return data.id // 返回新创建的申请ID
    } catch (err) {
      console.error('创建申请失败:', err)
      error.value = '创建申请失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // 更新申请状态（审核）
  const updateApplicationStatus = async (
    applicationId,
    status,
    reviewComment,
    finalScore,
    reviewedBy
  ) => {
    loading.value = true
    error.value = null

    try {
      // 处理不同组件传递的不同字段名（reviewComment vs approveComment/rejectComment）
      const comment =
        reviewComment.comment ||
        reviewComment.approveComment ||
        reviewComment.rejectComment ||
        reviewComment

      const updatedData = {
        status,
        reviewComment: comment,
        finalScore,
        reviewedBy
      }

      // 使用审核接口而不是通用更新接口，以触发自动评分逻辑
      await api.apiRequest(`/applications/${applicationId}/review`, 'POST', updatedData)

      // 更新本地状态
      const application = applications.value.find((app) => app.id === applicationId)
      if (application) {
        Object.assign(application, {
          status,
          reviewComment,
          finalScore,
          reviewedAt: new Date().toISOString(),
          reviewedBy
        })
      }

      return true
    } catch (err) {
      console.error('更新申请状态失败:', err)
      error.value = '更新申请状态失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // 批准申请
  const approveApplication = async (applicationId, finalScore, comment, reviewedBy) => {
    return await updateApplicationStatus(applicationId, 'approved', comment, finalScore, reviewedBy)
  }

  // 驳回申请
  const rejectApplication = async (applicationId, comment, reviewedBy) => {
    return await updateApplicationStatus(applicationId, 'rejected', comment, 0, reviewedBy)
  }

  // 删除申请
  const deleteApplication = async (applicationId) => {
    loading.value = true
    error.value = null

    try {
      await api.apiRequest(`/applications/${applicationId}`, 'DELETE')

      // 更新本地状态
      const index = applications.value.findIndex((app) => app.id === applicationId)
      if (index !== -1) {
        applications.value.splice(index, 1)
      }

      return true
    } catch (err) {
      console.error('删除申请失败:', err)
      error.value = '删除申请失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // 更新申请信息
  const updateApplication = async (applicationId, applicationData) => {
    loading.value = true
    error.value = null

    try {
      // 创建FormData对象来处理文件上传
      const formData = new FormData()

      // 将非文件字段添加到FormData
      const data = { ...applicationData }
      // 处理files字段，只保留后端需要的信息
      if (data.files) {
        data.files = data.files.map((file) => {
          // 只保留后端需要的字段，不包含File实例
          if (file.isBackendFile) {
            return { id: file.id, name: file.name, path: file.path, size: file.size }
          }
          return { name: file.name }
        })
      }
      // 保存原始files数组用于单独处理File实例
      const files = applicationData.files || []

      // 使用辅助函数转换字段名
      const transformedData = transformFieldNames(data)

      // 将转换后的application数据作为JSON字符串添加到FormData
      formData.append('application', JSON.stringify(transformedData))

      // 添加文件到FormData - 只添加新上传的浏览器File对象
      // 从后端加载的文件（非File实例）不会被添加，后端会保留这些文件
      files.forEach((file, index) => {
        if (file instanceof File) {
          formData.append(`files[${index}]`, file)
        }
      })

      // 发送请求
      await api.apiRequest(`/applications/${applicationId}`, 'PUT', formData)

      // 更新本地状态
      const application = applications.value.find((app) => app.id === applicationId)
      if (application) {
        Object.assign(application, applicationData)
      }

      return true
    } catch (err) {
      console.error('更新申请失败:', err)
      error.value = '更新申请失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // 获取单个申请详情（从本地状态或API）
  const getApplicationById = async (applicationId) => {
    // 先从本地状态查找
    const localApp = applications.value.find((app) => app.id === applicationId)
    if (localApp) {
      return localApp
    }

    // 如果本地没有，从API获取
    return await fetchApplicationById(applicationId)
  }

  // 过滤申请（按多种条件）
  const filterApplications = (filters = {}) => {
    return applications.value.filter((application) => {
      // 按学院筛选
      if (filters.faculty && filters.faculty !== 'all' && filters.faculty !== undefined) {
        const filterFaculty = String(filters.faculty)
        const appFaculty = String(application.facultyId || '')
        if (appFaculty !== filterFaculty) {
          return false
        }
      }

      // 按部门筛选 - 改进的ID匹配逻辑
      if (filters.department && filters.department !== 'all' && filters.department !== undefined) {
        const filterDept = String(filters.department)

        // 尝试匹配多种可能的字段格式
        const matchFields = [
          application.departmentId, // 标准ID字段
          application.department, // 可能包含ID的字段
          application.deptId, // 可能的备用字段名
          application.dept // 可能的备用字段名
        ]

        // 检查是否有任何字段匹配
        let matched = false
        for (const field of matchFields) {
          if (field && String(field) === filterDept) {
            matched = true
            break
          }
        }

        if (!matched) {
          return false
        }
      }

      // 按专业筛选 - 改进的ID匹配逻辑
      if (filters.major && filters.major !== 'all' && filters.major !== undefined) {
        const filterMajor = String(filters.major)

        // 尝试匹配多种可能的字段格式
        const matchFields = [
          application.majorId, // 标准ID字段
          application.major, // 可能包含ID的字段
          application.majId, // 可能的备用字段名
          application.maj // 可能的备用字段名
        ]

        // 检查是否有任何字段匹配
        let matched = false
        for (const field of matchFields) {
          if (field && String(field) === filterMajor) {
            matched = true
            break
          }
        }

        if (!matched) {
          return false
        }
      }

      // 按类型筛选
      if (filters.type && filters.type !== 'all' && application.applicationType !== filters.type) {
        return false
      }

      // 按规则筛选
      if (filters.rule && filters.rule !== 'all' && application.ruleId !== filters.rule) {
        return false
      }

      // 按学生学号筛选（模糊匹配）
      if (filters.studentId) {
        const searchTerm = filters.studentId.toLowerCase()
        const studentId = (application.studentId || '').toLowerCase()
        if (!studentId.includes(searchTerm)) {
          return false
        }
      }

      // 按学生姓名筛选（模糊匹配）
      if (filters.studentName) {
        const searchTerm = filters.studentName.toLowerCase()
        const studentName = (application.studentName || '').toLowerCase()
        if (!studentName.includes(searchTerm)) {
          return false
        }
      }

      // 按时间段筛选
      if (filters.startDate) {
        const applicationDate = new Date(application.appliedAt)
        const startDate = new Date(filters.startDate)
        if (applicationDate < startDate) {
          return false
        }
      }

      if (filters.endDate) {
        const applicationDate = new Date(application.appliedAt)
        const endDate = new Date(filters.endDate)
        endDate.setHours(23, 59, 59, 999) // 设置为当天结束时间
        if (applicationDate > endDate) {
          return false
        }
      }

      // 按审核人筛选（模糊匹配）
      if (filters.reviewedBy && filters.reviewedBy !== 'all') {
        const searchTerm = filters.reviewedBy.toLowerCase()
        const reviewedBy = (application.reviewedBy || '').toLowerCase()
        if (!reviewedBy.includes(searchTerm)) {
          return false
        }
      }

      // 只显示我审核的
      if (filters.myReviewsOnly) {
        if (application.reviewedBy !== filters.myReviewsOnly) {
          return false
        }
      }

      return true
    })
  }

  // 获取学生加分统计数据
  const fetchStatistics = async (studentId) => {
    loading.value = true
    error.value = null

    try {
      const data = await api.getStatistics(studentId)
      return data
    } catch (err) {
      console.error('加载加分统计数据失败:', err)
      error.value = '加载加分统计数据失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  // 获取学生推免成绩排名
  const fetchStudentsRanking = async (filters = {}) => {
    loading.value = true
    error.value = null

    try {
      const queryParams = new URLSearchParams()
      if (filters.faculty) {
        // 确保facultyId是数字类型
        const facultyId = parseInt(filters.faculty, 10)
        if (!isNaN(facultyId)) queryParams.append('facultyId', facultyId)
      }
      if (filters.department) {
        // 确保departmentId是数字类型
        const departmentId = parseInt(filters.department, 10)
        if (!isNaN(departmentId)) queryParams.append('departmentId', departmentId)
      }
      if (filters.major) {
        // 确保majorId是数字类型
        const majorId = parseInt(filters.major, 10)
        if (!isNaN(majorId)) queryParams.append('majorId', majorId)
      }

      const queryString = queryParams.toString() ? `?${queryParams.toString()}` : ''
      const data = await api.apiRequest(`/students/ranking${queryString}`)
      return data
    } catch (err) {
      console.error('加载学生排名数据失败:', err)
      error.value = '加载学生排名数据失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    // 状态
    applications,
    loading,
    error,

    // 计算属性
    pendingApplications,
    reviewedApplications,
    totalApplications,

    // 方法
    fetchApplications,
    fetchApplicationById,
    fetchPendingApplications,
    addApplication,
    updateApplicationStatus,
    updateApplication,
    deleteApplication,
    getApplicationById,
    filterApplications,
    approveApplication,
    rejectApplication,
    fetchStatistics,
    fetchStudentsRanking
  }
})
