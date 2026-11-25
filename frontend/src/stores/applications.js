import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api.js'

export const useApplicationsStore = defineStore('student-scores', () => {
  const loading = ref(false)
  const error = ref(null)

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

  return { loading, error, fetchStatistics, fetchStudentsRanking }
})
