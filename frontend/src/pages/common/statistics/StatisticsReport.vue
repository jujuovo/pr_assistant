<template>
  <div :class="{ 'page-content': !embedded }">
    <div v-if="!embedded" class="page-title">
      <h1>统计报表</h1>
    </div>

    <!-- 筛选区域 -->
    <div :class="['filters report-filters', { 'primary-section-frame': emphasizePrimaryFrame }]">
      <div class="report-filter-fields">
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
            :disabled="!filters.department"
          >
            <option value="">请选择专业</option>
            <option v-for="major in majors" :key="major.id" :value="major.id">{{
              major.name
            }}</option>
          </select>
        </div>
        <div class="filter-group">
          <span class="filter-label">推免周期：</span>
          <select v-model="filters.academicYear" class="form-control" aria-label="推免周期">
            <option value="" disabled>请选择推免周期</option>
            <option v-for="year in academicYears" :key="year" :value="year">{{ year }} 届</option>
          </select>
        </div>
      </div>
      <div class="report-filter-actions">
        <button class="btn btn-outline" @click="clearFilters">清空筛选</button>
        <button
          type="button"
          class="btn btn-outline"
          :disabled="hidden ? !rankingScope || !canExportRanking : !reportReady || loading || !officialReportRows.length"
          @click="exportCurrentTable"
        >
          导出统计报表
        </button>
        <slot name="filter-actions" />
      </div>
    </div>

    <p v-if="!reportReady" role="status">{{ reportHint }}</p>
    <slot v-else-if="hidden" name="ranking" :scope="rankingScope" />
    <!-- 成绩分布总表 -->
    <div v-if="!hidden && reportReady" class="card">
      <!-- 加载状态指示器 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">数据加载中...</div>
      </div>
      <div class="table-wrapper compact-report-wrapper">
        <div class="table-container" tabindex="0" role="region" aria-label="统计报表明细">
          <p v-if="officialReportError" role="alert">{{ officialReportError }}</p>
          <table v-else class="application-table official-report-table">
            <thead><tr><th v-for="[label] in reportColumns" :key="label" scope="col">{{ label }}</th></tr></thead>
            <tbody>
              <tr v-for="(row, index) in officialReportRows" :key="index">
                <td v-for="(value, column) in row" :key="column">{{ value }}</td>
              </tr>
              <tr v-if="!officialReportRows.length && !loading"><td :colspan="reportColumns.length">暂无数据</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  embedded: Boolean,
  hidden: Boolean,
  canExportRanking: Boolean,
  rankingYears: { type: Array, default: () => [] },
  emphasizePrimaryFrame: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['export-ranking'])

import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import * as XLSX from 'xlsx'
import api from '@/services/api.js'
import workflowApi from '@/services/workflowApi.js'

const authStore = useAuthStore()
const filters = reactive({
  faculty: '',
  department: '',
  major: '',
  academicYear: ''
})

// 当前学年
const currentYear = ref('')

const academicYears = computed(() => [...new Set(
  [currentYear.value, ...props.rankingYears].filter(Boolean).map(String)
)].sort((a, b) => Number(b) - Number(a)))
const rankingScope = computed(() => {
  if (!filters.faculty || !filters.department || !filters.major || !filters.academicYear) return null
  return { facultyId: Number(filters.faculty), departmentId: Number(filters.department),
    majorId: Number(filters.major), year: Number(filters.academicYear) }
})
const reportReady = computed(() => Boolean(rankingScope.value))
const reportHint = '请选择学院、系、专业和推免周期。'
const officialReport = ref(null)
const officialReportError = ref('')
const studentReportColumns = [
  ['序号', 'sequence'], ['学院', 'faculty'], ['系', 'department'], ['专业', 'major'],
  ['学号', 'student_id'], ['姓名', 'name'], ['性别', 'gender'],
  ['四级成绩', 'cet4'], ['六级成绩', 'cet6'], ['推免绩点', 'gpa'],
  ['学业基础分', 'academic_base'], ['学业成绩权重', 'academic_weight'],
  ['学术专长原始总分', 'academic_raw_total'], ['学术专长实际计入分', 'academic_total'],
  ['综合表现原始总分', 'comprehensive_raw_total'], ['综合表现实际计入分', 'comprehensive_total'],
  ['推免综合成绩', 'score'], ['报表名次', 'report_rank'], ['报表排名人数', 'ranked_count'],
  ['正式成绩状态', 'snapshot_status']
]
const projectColumns = [
  ['项目类型', 'category'], ['项目名称', 'name'], ['实际加分', 'score'], ['计入状态', 'status']
]
const reportColumns = [...studentReportColumns, ...projectColumns]
const projectTypes = {
  competition: '学业竞赛', competition_evidence: '其他竞赛',
  research: '科研成果', research_paper: '科研论文', invention_patent: '发明专利',
  innovation_training: '创新创业', volunteer: '志愿服务', social_practice: '社会实践',
  student_work: '学生工作', arts_sports: '文体活动', certification: '能力认证',
  language: '外语能力', honor: '荣誉称号', honor_title: '荣誉称号'
}
const projectReasons = {
  competition_count_limit: '超出竞赛计入项目数上限',
  competition_top_three_limit: '超出竞赛计入项目数上限',
  max_count_exceeded: '超出计入项目数上限',
  duplicate_fact: '重复项目',
  rule_total_score_cap: '达到累计分数上限',
  csp_lower_score: 'CSP 成绩仅计最高项',
  icpc_ccpc_same_year_lower_score: '同年 ICPC 和 CCPC 仅计最高项',
  same_event_lower_score: '同一赛事仅计最高项',
  same_work_lower_score: '同一作品仅计最高项'
}
const officialReportRows = computed(() => (officialReport.value?.students || []).flatMap((student, index) => {
  const values = {
    ...student,
    sequence: index + 1,
    snapshot_status: student.snapshot_status === 'no_authoritative_snapshot' ? '暂无正式成绩快照' : '正式成绩'
  }
  const projects = student.projects?.length ? student.projects : [null]
  return projects.map((project, projectIndex) => [
    ...studentReportColumns.map(([, key]) =>
      projectIndex === 0 ? values[key] ?? null : null
    ),
    project ? (projectTypes[project.category] || project.category) : null,
    project ? project.name || '未记录项目名称' : null,
    project?.score ?? null,
    project ? Number(project.score) > 0 ? '已计入'
      : projectReasons[project.exclusion_reason] || project.exclusion_reason || '未记录原因' : null
  ])
}))

// 学院列表
const faculties = ref([])
// 系列表
const departments = ref([])
// 专业列表
const majors = ref([])
const loading = ref(false)

const loadFaculties = async () => {
  try {
    const response = await api.getFacultiesAdmin()
    const facultyId = authStore.user?.faculty_id || authStore.user?.facultyId
    faculties.value = (response.faculties || []).filter(faculty => Number(faculty.id) === Number(facultyId))
    if (faculties.value.length) {
      filters.faculty = faculties.value[0].id
      await handleFacultyChange()
    }
  } catch (error) {
    console.error('加载学院数据失败:', error)
  }
}

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

}

function exportCurrentTable() {
  if (props.hidden) {
    if (rankingScope.value && props.canExportRanking) emit('export-ranking')
    return
  }
  if (!officialReportRows.value.length || loading.value) return
  const workbook = XLSX.utils.book_new()
  const sheet = XLSX.utils.aoa_to_sheet([reportColumns.map(([label]) => label), ...officialReportRows.value])
  XLSX.utils.book_append_sheet(workbook, sheet, '正式成绩报表')
  XLSX.writeFile(workbook, `统计报表_${officialReport.value.year}届.xlsx`)
}

let reportRequest = 0
watch([rankingScope, () => props.hidden], async ([scope, hidden]) => {
  const request = ++reportRequest
  officialReport.value = null
  officialReportError.value = ''
  loading.value = Boolean(scope && !hidden)
  if (!loading.value) return

  try {
    const report = await workflowApi.getTeacherScoreReport(scope)
    if (request === reportRequest) officialReport.value = report
  } catch (error) {
    if (request === reportRequest) officialReportError.value = error.message || '加载正式成绩报表失败'
  } finally {
    if (request === reportRequest) loading.value = false
  }
})

onMounted(async () => {
  try {
    const cycle = await workflowApi.getCurrentCycle()
    currentYear.value = String(cycle.cycle_code)
    filters.academicYear = currentYear.value
  } catch (error) {
    console.error('加载当前推免周期失败:', error)
  }
  await loadFaculties()
})
</script>

<style scoped src="@/assets/styles/pages/common/statistics/StatisticsReport.css"></style>
