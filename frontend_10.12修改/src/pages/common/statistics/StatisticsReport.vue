<template>
  <div class="page-content">
    <div class="page-title">
      <span>统计报表</span>
    </div>

    <!-- 筛选区域 -->
    <div class="filters">
      <div class="filter-group">
        <span class="filter-label">当前学院:</span>
        <select class="form-control" v-model="filters.faculty" @change="handleFacultyChange">
          <option value="">请选择学院</option>
          <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">{{
            faculty.name
          }}</option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">所在系:</span>
        <select
          class="form-control"
          v-model="filters.department"
          @change="handleDepartmentChange"
          :disabled="!filters.faculty"
        >
          <option value="">请选择系</option>
          <option v-for="department in departments" :key="department.id" :value="department.id"
            >{{ department.name }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">所在专业:</span>
        <select
          class="form-control"
          v-model="filters.major"
          @change="handleMajorChange"
          :disabled="!filters.department"
        >
          <option value="">请选择专业</option>
          <option v-for="major in majors" :key="major.id" :value="major.id">{{
            major.name
          }}</option>
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">当前学年:</span>
        <span class="form-control"
          >{{ currentYear }}-{{ currentYear ? parseInt(currentYear) + 1 : '' }}</span
        >
      </div>
      <button class="btn btn-outline" @click="clearFilters">清空筛选</button>
      <button class="btn btn-outline" @click="generateReport">生成报表</button>
    </div>

    <!-- 成绩分布总表 -->
    <div class="card">
      <!-- 加载状态指示器 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">数据加载中...</div>
      </div>
      <div class="card-title">学生成绩分布总表</div>
      <div class="table-wrapper">
        <!-- 顶部滚动条辅助容器 -->
        <div class="top-scroll-container" ref="topScrollContainer">
          <div class="top-scroll-content"></div>
        </div>
        <!-- 主表格容器 -->
        <div class="table-container" ref="tableContainer">
          <!-- 未选择专业时显示提示 -->
          <div v-if="!filters.major" class="no-data"> 请选择专业 </div>
          <table v-else class="application-table comprehensive-table" ref="dataTable">
            <thead>
              <tr>
                <!-- A-H: 学生基本信息 -->
                <th>序号</th>
                <th>学院</th>
                <th>系</th>
                <th>专业</th>
                <th>学号</th>
                <th>姓名</th>
                <th>性别</th>
                <th>CET4成绩</th>
                <th>CET6成绩</th>
                <!-- I-J: 学业综合成绩（占总分80%） -->
                <th>推免绩点(满分4分)</th>
                <th>换算后的成绩(满分100分)</th>
                <!-- K-S: 学术专长成绩（占总分12%） -->
                <th>学术专长项目</th>
                <th>学术专长获奖时间</th>
                <th>学术专长奖项级别</th>
                <th>学术专长个人或集体</th>
                <th>学术专长集体奖项排序</th>
                <th>学术专长自评加分</th>
                <th>学术专长加分依据</th>
                <th>学术专长学院核定加分</th>
                <th>学术专长学院核定总分</th>
                <!-- T-AB: 综合表现加分（占总分8%） -->
                <th>综合表现项目</th>
                <th>综合表现获奖时间</th>
                <th>综合表现奖项级别</th>
                <th>综合表现个人或集体</th>
                <th>综合表现集体奖项排序</th>
                <th>综合表现自评加分</th>
                <th>综合表现加分依据</th>
                <th>综合表现学院核定加分</th>
                <th>综合表现学院核定总分</th>
                <!-- AC-AF: 总分与排名 -->
                <th>考核综合成绩总分</th>
                <th>综合成绩</th>
                <th>专业成绩排名</th>
                <th>排名人数</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(student, index) in filteredStudents"
                :key="`${student.studentId}-${index}`"
                :class="{ 'student-group-start': student.isFirstRow }"
              >
                <!-- A-H: 学生基本信息 -->
                <td v-if="student.isFirstRow">{{ student.sequence }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ getFacultyText(student.faculty_id) }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.department || '-' }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.major || '-' }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.studentId }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.studentName }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.gender }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.cet4Score }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.cet6Score }}</td>
                <td v-else></td>
                <!-- I-J: 学业综合成绩（占总分80%） -->
                <td v-if="student.isFirstRow">{{ student.gpa ? student.gpa.toFixed(3) : 0 }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{
                  student.academicScore ? student.academicScore.toFixed(4) : 0
                }}</td>
                <td v-else></td>
                <!-- K-S: 学术专长成绩（占总分12%） -->
                <td v-if="student.academicItem.projectName">
                  {{ student.academicItem.projectName }}
                </td>
                <td v-else></td>
                <td v-if="student.academicItem.projectName">
                  {{ student.academicItem.awardTime }}
                </td>
                <td v-else></td>
                <td v-if="student.academicItem.projectName">
                  {{ student.academicItem.awardLevel }}
                </td>
                <td v-else></td>
                <td v-if="student.academicItem.projectName">
                  {{ student.academicItem.individualCollective }}
                </td>
                <td v-else></td>
                <td v-if="student.academicItem.projectName">
                  {{ student.academicItem.authorOrder }}
                </td>
                <td v-else></td>
                <td v-if="student.academicItem.projectName">
                  {{
                    student.academicItem.selfEvalScore
                      ? student.academicItem.selfEvalScore.toFixed(4)
                      : 0
                  }}
                </td>
                <td v-else></td>
                <td v-if="student.academicItem.projectName">
                  {{ student.academicItem.scoreBasis }}
                </td>
                <td v-else></td>
                <td v-if="student.academicItem.projectName">
                  {{
                    student.academicItem.collegeApprovedScore
                      ? student.academicItem.collegeApprovedScore.toFixed(4)
                      : 0
                  }}
                </td>
                <td v-else></td>
                <td v-if="student.isFirstRow">
                  {{ student.specialtyScore ? student.specialtyScore.toFixed(4) : 0 }}
                </td>
                <td v-else></td>
                <!-- T-AB: 综合表现加分（占总分8%） -->
                <td v-if="student.comprehensiveItem.projectName">
                  {{ student.comprehensiveItem.projectName }}
                </td>
                <td v-else></td>
                <td v-if="student.comprehensiveItem.projectName">
                  {{ student.comprehensiveItem.awardTime }}
                </td>
                <td v-else></td>
                <td v-if="student.comprehensiveItem.projectName">
                  {{ student.comprehensiveItem.awardLevel }}
                </td>
                <td v-else></td>
                <td v-if="student.comprehensiveItem.projectName">
                  {{ student.comprehensiveItem.individualCollective }}
                </td>
                <td v-else></td>
                <td v-if="student.comprehensiveItem.projectName">
                  {{ student.comprehensiveItem.authorOrder }}
                </td>
                <td v-else></td>
                <td v-if="student.comprehensiveItem.projectName">
                  {{
                    student.comprehensiveItem.selfEvalScore
                      ? student.comprehensiveItem.selfEvalScore.toFixed(4)
                      : 0
                  }}
                </td>
                <td v-else></td>
                <td v-if="student.comprehensiveItem.projectName">
                  {{ student.comprehensiveItem.scoreBasis }}
                </td>
                <td v-else></td>
                <td v-if="student.comprehensiveItem.projectName">
                  {{
                    student.comprehensiveItem.collegeApprovedScore
                      ? student.comprehensiveItem.collegeApprovedScore.toFixed(4)
                      : 0
                  }}
                </td>
                <td v-else></td>
                <td v-if="student.isFirstRow">
                  {{ student.comprehensiveScore ? student.comprehensiveScore.toFixed(4) : 0 }}
                </td>
                <td v-else></td>
                <!-- AC-AF: 总分与排名 -->
                <td v-if="student.isFirstRow">{{
                  student.totalComprehensiveScore ? student.totalComprehensiveScore.toFixed(4) : 0
                }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{
                  student.finalScore ? student.finalScore.toFixed(4) : 0
                }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.majorRanking }}</td>
                <td v-else></td>
                <td v-if="student.isFirstRow">{{ student.majorTotalStudents }}</td>
                <td v-else></td>
              </tr>
              <tr v-if="filteredStudents.length === 0">
                <td colspan="34" class="no-data">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useApplicationsStore } from '@/stores/applications.js'
import { useToastStore } from '@/stores/toast.js'
import { useAuthStore } from '@/stores/auth.js'
import * as XLSX from 'xlsx'
import api from '@/services/api.js'

const applicationsStore = useApplicationsStore()
const toastStore = useToastStore()
const authStore = useAuthStore()
const filters = reactive({
  faculty: '',
  department: '',
  major: '',
  academicYear: ''
})

// 当前学年
const currentYear = ref('2023')

// 学院列表
const faculties = ref([])
// 系列表
const departments = ref([])
// 专业列表
const majors = ref([])
// 学生排名数据
const studentsRanking = ref([])
// 所有申请记录
const allApplications = ref([])
// 加载状态
const loading = ref(false)

// 加载学院列表
const loadFaculties = async () => {
  loading.value = true
  try {
    const response = await api.getFacultiesAdmin()
    faculties.value = response.faculties || []

    // 将老师所在的学院设置为默认选中值
    const teacherFacultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    if (teacherFacultyId) {
      filters.faculty = teacherFacultyId.toString()
      // 根据默认学院加载系
      await handleFacultyChange()
    }
  } catch (error) {
    console.error('加载学院数据失败:', error)
    // 添加默认学院数据作为备选
    faculties.value = [
      { id: 1, name: '计算机科学与技术学院' },
      { id: 2, name: '电子工程学院' },
      { id: 3, name: '机械工程学院' },
      { id: 4, name: '经济管理学院' },
      { id: 5, name: '外国语学院' }
    ]
  } finally {
    loading.value = false
  }
}

// 从API获取学生排名数据
const fetchStudentsRanking = async () => {
  loading.value = true
  try {
    // 直接使用后端学生排名API
    const responseData = await applicationsStore.fetchStudentsRanking({
      faculty: filters.faculty,
      department: filters.department,
      major: filters.major
    })

    // 转换为表格行数据
    let formattedStudents = []
    // 从响应中获取学生数组
    const rankingData = responseData.students || []
    rankingData.forEach((student) => {
      // 转换字段名称以匹配前端期望的格式
      const formattedStudent = {
        // 基本信息
        studentId: student.student_id || student.studentId,
        studentName: student.student_name || student.studentName,
        departmentId: student.department_id || student.departmentId,
        department: student.department,
        majorId: student.major_id || student.majorId,
        major: student.major,
        facultyId: student.faculty_id || student.facultyId,
        faculty: student.faculty,
        gender: student.gender,
        cet4Score: student.cet4_score || student.cet4Score,
        cet6Score: student.cet6_score || student.cet6Score,
        gpa: student.gpa,
        academicScore: student.academic_score || student.academicScore,
        majorRanking: student.major_ranking || student.majorRanking,
        majorTotalStudents: student.major_total_students || student.majorTotalStudents,
        sequence: student.sequence,

        // 分数信息
        specialtyScore: student.specialty_score || student.specialtyScore,
        // 综合表现学院核定总分
        comprehensiveScore: student.comprehensive_performance_total || student.comprehensiveScore,
        // 综合成绩
        actualComprehensiveScore: student.comprehensive_score || student.actualComprehensiveScore,
        totalScore: student.total_score || student.totalScore,
        totalComprehensiveScore:
          student.total_comprehensive_score || student.totalComprehensiveScore,
        finalScore: student.final_score || student.finalScore,
        finalComprehensiveScore:
          student.final_comprehensive_score || student.finalComprehensiveScore,

        // 项目信息（转换为驼峰命名）
        academicItems: student.academic_items || student.academicItems || [],
        comprehensiveItems: student.comprehensive_items || student.comprehensiveItems || []
      }

      // 获取学术专长项目和综合表现项目的最大数量
      const maxItemsCount = Math.max(
        formattedStudent.academicItems.length || 0,
        formattedStudent.comprehensiveItems.length || 0
      )

      // 循环创建行，让学术专长项目和综合表现项目按索引一一对应显示
      for (let i = 0; i < Math.max(1, maxItemsCount); i++) {
        // 至少创建一行
        // 获取当前索引的学术专长项目，如果不存在则使用空对象
        const rawAcademicItem = (formattedStudent.academicItems || [])[i]
        // 转换学术专长项目的字段名（蛇形命名法转驼峰命名法）
        const academicItem = rawAcademicItem
          ? {
              projectName: rawAcademicItem.project_name || '',
              awardTime: rawAcademicItem.award_time || '',
              awardLevel: rawAcademicItem.award_level || '',
              individualCollective: rawAcademicItem.individual_collective || '',
              authorOrder: rawAcademicItem.author_order || '',
              selfEvalScore: rawAcademicItem.self_eval_score || 0,
              scoreBasis: rawAcademicItem.score_basis || '',
              collegeApprovedScore: rawAcademicItem.college_approved_score || 0,
              totalScore: rawAcademicItem.total_score || 0
            }
          : {
              projectName: '',
              awardTime: '',
              awardLevel: '',
              individualCollective: '',
              authorOrder: '',
              selfEvalScore: 0,
              scoreBasis: '',
              collegeApprovedScore: 0,
              totalScore: 0
            }

        // 获取当前索引的综合表现项目，如果不存在则使用空对象
        const rawComprehensiveItem = (formattedStudent.comprehensiveItems || [])[i]
        // 转换综合表现项目的字段名（蛇形命名法转驼峰命名法）
        const comprehensiveItem = rawComprehensiveItem
          ? {
              projectName: rawComprehensiveItem.project_name || '',
              awardTime: rawComprehensiveItem.award_time || '',
              awardLevel: rawComprehensiveItem.award_level || '',
              individualCollective: rawComprehensiveItem.individual_collective || '',
              authorOrder: rawComprehensiveItem.author_order || '',
              selfEvalScore: rawComprehensiveItem.self_eval_score || 0,
              scoreBasis: rawComprehensiveItem.score_basis || '',
              collegeApprovedScore: rawComprehensiveItem.college_approved_score || 0,
              totalScore: rawComprehensiveItem.total_score || 0
            }
          : {
              projectName: '',
              awardTime: '',
              awardLevel: '',
              individualCollective: '',
              authorOrder: '',
              selfEvalScore: 0,
              scoreBasis: '',
              collegeApprovedScore: 0,
              totalScore: 0
            }

        const row = {
          ...formattedStudent,
          faculty_id: formattedStudent.facultyId, // 确保字段名一致
          department_id: formattedStudent.departmentId, // 确保字段名一致
          major_id: formattedStudent.majorId, // 确保字段名一致
          isFirstRow: i === 0, // 只有第一行显示基本信息
          itemType: 'both', // 每一行都可能同时显示两种类型的项目
          academicItem,
          comprehensiveItem
        }
        formattedStudents.push(row)
      }
    })

    studentsRanking.value = formattedStudents
  } catch (error) {
    console.error('获取学生排名失败:', error)
    studentsRanking.value = []
  } finally {
    loading.value = false
  }
}

// 计算属性 - 筛选后的学生排名
const filteredStudents = computed(() => {
  let students = studentsRanking.value

  if (filters.faculty) {
    const facultyId = parseInt(filters.faculty)
    students = students.filter((student) => student.faculty_id === facultyId)
  }

  if (filters.department) {
    const departmentId = parseInt(filters.department)
    students = students.filter((student) => student.department_id === departmentId)
  }

  if (filters.major) {
    const majorId = parseInt(filters.major)
    students = students.filter((student) => student.major_id === majorId)
  }

  // 按专业成绩排名显示
  // 1. 首先将学生数据按学生ID分组
  const studentGroups = new Map()
  students.forEach((student) => {
    if (!studentGroups.has(student.studentId)) {
      studentGroups.set(student.studentId, [])
    }
    studentGroups.get(student.studentId).push(student)
  })

  // 2. 对学生组进行排序，按照专业排名从小到大
  const sortedGroups = Array.from(studentGroups.values()).sort((groupA, groupB) => {
    // 获取每个学生的第一行（包含排名信息）
    const studentA = groupA.find((s) => s.isFirstRow)
    const studentB = groupB.find((s) => s.isFirstRow)

    // 按专业排名排序
    const rankingA = studentA ? studentA.majorRanking || Infinity : Infinity
    const rankingB = studentB ? studentB.majorRanking || Infinity : Infinity

    return rankingA - rankingB
  })

  // 3. 重新组合所有行数据
  return sortedGroups.flat()
})

// 计算属性 - 总体统计信息
const totalStats = computed(() => {
  const allApps = applicationsStore.applications
  const totalApplications = allApps.length

  // 计算学生总数
  const studentIds = new Set(allApps.map((app) => app.studentId))
  const totalStudents = studentIds.size

  // 计算平均总分
  const avgTotalScore =
    filteredStudents.value.length > 0
      ? filteredStudents.value.reduce((sum, student) => sum + student.totalScore, 0) /
        filteredStudents.value.length
      : 0

  // 计算最高分数
  const maxScore =
    filteredStudents.value.length > 0
      ? Math.max(...filteredStudents.value.map((student) => student.totalScore))
      : 0

  return {
    totalStudents,
    totalApplications,
    avgTotalScore,
    maxScore
  }
})

// 方法
const getFacultyText = (facultyId) => {
  // 确保输入的facultyId是数字类型
  const id = typeof facultyId === 'string' ? parseInt(facultyId) : facultyId

  // 检查id是否有效
  if (isNaN(id)) {
    return '未知学院'
  }

  // 从学院列表中查找学院名称
  const faculty = faculties.value.find((f) => f.id === id)

  return faculty ? faculty.name : '未知学院'
}

// 学院选择变化时的处理函数
const handleFacultyChange = async () => {
  // 重置系和专业选择
  filters.department = ''
  filters.major = ''
  departments.value = []
  majors.value = []

  // 如果选择了学院，加载对应的系列表
  if (filters.faculty) {
    try {
      const response = await api.getDepartmentsAdmin(filters.faculty)
      departments.value = response.departments || []
    } catch (error) {
      console.error('加载系列表失败:', error)
      departments.value = []
    }
  }

  // 刷新数据
  refreshData()
}

// 系选择变化时的处理函数
const handleDepartmentChange = async () => {
  // 重置专业选择
  filters.major = ''
  majors.value = []

  // 如果选择了系，加载对应的专业列表
  if (filters.department) {
    try {
      const response = await api.getMajorsAdmin(filters.department)
      majors.value = response.majors || []
    } catch (error) {
      console.error('加载专业列表失败:', error)
      majors.value = []
    }
  }

  // 刷新数据
  refreshData()
}

// 专业选择变化时的处理函数
const handleMajorChange = () => {
  // 刷新数据
  refreshData()
}

// 清空所有筛选条件
const clearFilters = () => {
  // 保留学院选择不变（如果是用户自己的学院）
  filters.faculty = ''
  filters.department = ''
  filters.major = ''
  // 保持当前学年不变
  filters.academicYear = currentYear.value

  // 清空系和专业列表
  departments.value = []
  majors.value = []

  // 刷新数据
  refreshData()
}

const generateReport = () => {
  if (filteredStudents.value.length === 0) {
    toastStore.error('当前没有数据可导出')
    return
  }

  // 准备导出数据
  const exportData = []

  // 添加表头
  const headers = [
    '序号',
    '学院',
    '系',
    '专业',
    '学号',
    '姓名',
    '性别',
    'CET4成绩',
    'CET6成绩',
    '推免绩点(满分4分)',
    '换算后的成绩(满分100分)',
    '学术专长项目',
    '学术专长获奖时间',
    '学术专长奖项级别',
    '学术专长个人或集体',
    '学术专长集体奖项排序',
    '学术专长自评加分',
    '学术专长加分依据',
    '学术专长学院核定加分',
    '学术专长学院核定总分',
    '综合表现项目',
    '综合表现获奖时间',
    '综合表现奖项级别',
    '综合表现个人或集体',
    '综合表现集体奖项排序',
    '综合表现自评加分',
    '综合表现加分依据',
    '综合表现学院核定加分',
    '综合表现学院核定总分',
    '考核综合成绩总分',
    '综合成绩',
    '专业成绩排名',
    '排名人数'
  ]
  exportData.push(headers)

  // 处理学生数据
  const studentMap = new Map()

  // 先按学生ID分组，确保每个学生只处理一次
  filteredStudents.value.forEach((row) => {
    const studentId = row.studentId
    if (!studentMap.has(studentId)) {
      studentMap.set(studentId, {
        studentData: row,
        academicItems: [],
        comprehensiveItems: []
      })
    }

    const student = studentMap.get(studentId)
    if (row.academicItem && row.academicItem.projectName) {
      student.academicItems.push(row.academicItem)
    }
    if (row.comprehensiveItem && row.comprehensiveItem.projectName) {
      student.comprehensiveItems.push(row.comprehensiveItem)
    }
  })

  // 将分组后的数据转换为Excel行
  const studentEntries = Array.from(studentMap.entries())
  studentEntries.forEach(([studentId, student], index) => {
    const { studentData, academicItems, comprehensiveItems } = student
    // 确保即使没有项目也至少生成一行数据
    const maxItems = Math.max(academicItems.length, comprehensiveItems.length, 1)

    for (let i = 0; i < maxItems; i++) {
      const row = []

      // 基本信息（仅第一行显示）
      if (i === 0) {
        row.push(studentData.sequence)
        row.push(getFacultyText(studentData.faculty_id))
        row.push(studentData.department)
        row.push(studentData.major)
        row.push(studentData.studentId)
        row.push(studentData.studentName)
        row.push(studentData.gender)
        row.push(studentData.cet4Score)
        row.push(studentData.cet6Score)
        row.push(studentData.gpa ? studentData.gpa.toFixed(3) : 0)
        row.push(studentData.academicScore ? studentData.academicScore.toFixed(4) : 0)
      } else {
        // 非第一行基本信息留空
        for (let j = 0; j < 11; j++) {
          row.push('')
        }
      }

      // 学术专长信息
      const academicItem = academicItems[i] || {}
      row.push(academicItem.projectName || '')
      row.push(academicItem.awardTime || '')
      row.push(academicItem.awardLevel || '')
      row.push(academicItem.individualCollective || '')
      row.push(academicItem.authorOrder || '')
      row.push(academicItem.selfEvalScore ? academicItem.selfEvalScore.toFixed(4) : 0)
      row.push(academicItem.scoreBasis || '')
      row.push(academicItem.collegeApprovedScore ? academicItem.collegeApprovedScore.toFixed(4) : 0)
      row.push(
        i === 0 ? (studentData.specialtyScore ? studentData.specialtyScore.toFixed(4) : 0) : ''
      )

      // 综合表现信息
      const comprehensiveItem = comprehensiveItems[i] || {}
      row.push(comprehensiveItem.projectName || '')
      row.push(comprehensiveItem.awardTime || '')
      row.push(comprehensiveItem.awardLevel || '')
      row.push(comprehensiveItem.individualCollective || '')
      row.push(comprehensiveItem.authorOrder || '')
      row.push(comprehensiveItem.selfEvalScore ? comprehensiveItem.selfEvalScore.toFixed(4) : 0)
      row.push(comprehensiveItem.scoreBasis || '')
      row.push(
        comprehensiveItem.collegeApprovedScore
          ? comprehensiveItem.collegeApprovedScore.toFixed(4)
          : 0
      )
      row.push(
        i === 0
          ? studentData.comprehensiveScore
            ? studentData.comprehensiveScore.toFixed(4)
            : 0
          : ''
      )

      // 总分与排名（仅第一行显示）
      if (i === 0) {
        row.push(
          studentData.totalComprehensiveScore ? studentData.totalComprehensiveScore.toFixed(4) : 0
        )
        row.push(studentData.finalScore ? studentData.finalScore.toFixed(4) : 0)
        row.push(studentData.majorRanking)
        row.push(studentData.majorTotalStudents)
      } else {
        // 非第一行总分与排名留空
        for (let j = 0; j < 4; j++) {
          row.push('')
        }
      }

      exportData.push(row)
    }

    // 在每个学生的行数据之后添加一个空行，最后一个学生除外
    if (index < studentEntries.length - 1) {
      // 创建一个与表头长度相同的空行
      const emptyRow = new Array(headers.length).fill('')
      exportData.push(emptyRow)
    }
  })

  // 创建工作簿
  const wb = XLSX.utils.book_new()

  // 创建工作表
  const ws = XLSX.utils.aoa_to_sheet(exportData)

  // 设置列宽
  ws['!cols'] = [
    { wch: 6 }, // 序号
    { wch: 15 }, // 学院
    { wch: 15 }, // 系
    { wch: 15 }, // 专业
    { wch: 15 }, // 学号
    { wch: 8 }, // 姓名
    { wch: 6 }, // 性别
    { wch: 10 }, // CET4成绩
    { wch: 15 }, // CET6成绩
    { wch: 15 }, // 推免绩点
    { wch: 18 }, // 换算后的成绩
    { wch: 20 }, // 学术专长项目
    { wch: 15 }, // 学术专长获奖时间
    { wch: 15 }, // 学术专长奖项级别
    { wch: 15 }, // 学术专长个人或集体
    { wch: 18 }, // 学术专长集体奖项排序
    { wch: 15 }, // 学术专长自评加分
    { wch: 20 }, // 学术专长加分依据
    { wch: 18 }, // 学术专长学院核定加分
    { wch: 18 }, // 学术专长学院核定总分
    { wch: 20 }, // 综合表现项目
    { wch: 15 }, // 综合表现获奖时间
    { wch: 15 }, // 综合表现奖项级别
    { wch: 15 }, // 综合表现个人或集体
    { wch: 18 }, // 综合表现集体奖项排序
    { wch: 15 }, // 综合表现自评加分
    { wch: 20 }, // 综合表现加分依据
    { wch: 18 }, // 综合表现学院核定加分
    { wch: 18 }, // 综合表现学院核定总分
    { wch: 18 }, // 考核综合成绩总分
    { wch: 10 }, // 综合成绩
    { wch: 12 }, // 专业成绩排名
    { wch: 10 } // 排名人数
  ]

  // 为所有单元格应用靠右对齐样式
  for (const cellAddress in ws) {
    // 跳过特殊属性
    if (cellAddress.startsWith('!')) continue

    // 获取单元格对象
    const cell = ws[cellAddress]

    // 设置单元格格式为文本并靠右对齐
    // 使用XLSX库的数字格式和对齐方式
    cell.z = '@' // 文本格式
    cell.s = cell.s || {}
    cell.s.alignment = { horizontal: 'right' }
  }

  // 添加工作表到工作簿
  XLSX.utils.book_append_sheet(wb, ws, '学生成绩分布')

  // 生成文件名
  const fileName = `统计报表_${filters.academicYear}-${parseInt(filters.academicYear) + 1}学年_${getFacultyText(filters.faculty)}_${new Date().toISOString().split('T')[0]}.xlsx`

  // 导出文件
  XLSX.writeFile(wb, fileName)
}

// 加载当前学年
const loadCurrentYear = async () => {
  try {
    const response = await api.getSystemSettings()
    const settings = response.settings
    currentYear.value = settings.academicYear
    filters.academicYear = settings.academicYear
  } catch (error) {
    console.error('加载当前学年失败:', error)
    // 如果获取失败，使用默认值2023
    currentYear.value = '2023'
    filters.academicYear = '2023'
  }
}

// 重新加载数据
const refreshData = () => {
  fetchStudentsRanking()
}

// 监听筛选条件变化
watch(
  filters,
  () => {
    fetchStudentsRanking()
  },
  { deep: true }
)

// 监听学生排名数据变化，更新滚动条宽度
watch(
  studentsRanking,
  () => {
    setTimeout(() => {
      updateTopScrollWidth()
    }, 300)
  },
  { deep: true }
)

// 顶部滚动条引用
const topScrollContainer = ref(null)
const tableContainer = ref(null)
const dataTable = ref(null)

// 同步顶部滚动条
const syncScroll = () => {
  if (tableContainer.value && topScrollContainer.value) {
    topScrollContainer.value.scrollLeft = tableContainer.value.scrollLeft
  }
}

// 反向同步滚动
const reverseSyncScroll = () => {
  if (tableContainer.value && topScrollContainer.value) {
    tableContainer.value.scrollLeft = topScrollContainer.value.scrollLeft
  }
}

// 更新顶部滚动条宽度
const updateTopScrollWidth = () => {
  if (dataTable.value && topScrollContainer.value) {
    const contentWidth = dataTable.value.offsetWidth
    const topScrollContent = topScrollContainer.value.querySelector('.top-scroll-content')
    if (topScrollContent) {
      topScrollContent.style.width = `${contentWidth}px`
      // 调试信息
    }
  }
}
// 生命周期
onMounted(async () => {
  // 获取当前学年
  await loadCurrentYear()
  await loadFaculties()
  await fetchStudentsRanking()

  // 等待DOM更新后再初始化滚动条
  setTimeout(() => {
    updateTopScrollWidth()

    // 添加滚动事件监听器
    if (tableContainer.value) {
      tableContainer.value.addEventListener('scroll', syncScroll)
    }
    if (topScrollContainer.value) {
      topScrollContainer.value.addEventListener('scroll', reverseSyncScroll)
    }

    // 监听窗口大小变化
    window.addEventListener('resize', updateTopScrollWidth)

    // 强制触发一次滚动同步
    if (tableContainer.value) {
      tableContainer.value.scrollLeft = 0
      syncScroll()
    }
  }, 500) // 增加延迟时间，确保表格数据完全加载
})
</script>

<style scoped src="@/assets/styles/pages/common/statistics/StatisticsReport.css"></style>
