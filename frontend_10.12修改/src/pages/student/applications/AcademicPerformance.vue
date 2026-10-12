<template>
  <div class="academic-page">
    <header class="academic-header">
      <div>
        <p class="academic-kicker">评测项目</p>
        <h1>学业成绩</h1>
        <p class="academic-description">集中查看课程成绩、学分情况与当前专业排名。</p>
      </div>
      <button type="button" class="back-button" @click="$emit('back-to-categories')">
        <font-awesome-icon :icon="['fas', 'arrow-left']" aria-hidden="true" />
        <span>返回评测项目</span>
      </button>
    </header>

    <section class="academic-content" aria-live="polite">
      <p v-if="loading" class="state-message">正在读取学业成绩…</p>
      <div v-else-if="error" class="state-message error-message">
        <span>{{ error }}</span>
        <button type="button" @click="loadAcademicPerformance">重新加载</button>
      </div>

      <template v-else>
        <div class="metrics-grid">
          <article v-for="metric in metrics" :key="metric.label" class="metric-card">
            <span class="metric-label">{{ metric.label }}</span>
            <strong class="metric-value">{{ metric.value }}</strong>
            <span class="metric-unit">{{ metric.unit }}</span>
          </article>
        </div>

        <article class="ranking-card">
          <div class="ranking-copy">
            <span class="metric-label">绩点排名</span>
            <strong class="ranking-value">{{ rankingText }}</strong>
            <span class="ranking-caption">{{ rankingPercentText }}</span>
          </div>
          <div class="ranking-visual" :aria-label="rankingPercentText">
            <div class="ranking-track" aria-hidden="true">
              <span class="ranking-fill" :style="{ width: rankingBarWidth }"></span>
            </div>
            <div class="ranking-scale">
              <span>专业前列</span>
              <span>专业总人数</span>
            </div>
          </div>
        </article>

        <p class="data-note">成绩数据以教务系统和学院最终核定结果为准。</p>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useApplicationsStore } from '@/stores/applications.js'

defineEmits(['back-to-categories'])

const authStore = useAuthStore()
const applicationsStore = useApplicationsStore()
const loading = ref(false)
const error = ref('')
const academic = reactive({
  gpa: null,
  weightedScore: null,
  totalCourses: null,
  totalCredits: null,
  ranking: null,
  totalStudents: null
})

const displayNumber = (value, digits = 2) => {
  if (value === null || value === undefined || value === '') return '待同步'
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits).replace(/\.00$/, '') : String(value)
}

const metrics = computed(() => [
  { label: '学分绩点', value: displayNumber(academic.gpa), unit: 'GPA' },
  { label: '加权成绩', value: displayNumber(academic.weightedScore), unit: '分' },
  {
    label: '总课程门数',
    value: displayNumber(academic.totalCourses, 0),
    unit: academic.totalCourses == null ? '' : '门'
  },
  {
    label: '总学分数',
    value: displayNumber(academic.totalCredits, 1),
    unit: academic.totalCredits == null ? '' : '学分'
  }
])

const hasRanking = computed(
  () => Number(academic.ranking) > 0 && Number(academic.totalStudents) > 0
)
const rankingPercent = computed(() =>
  hasRanking.value
    ? Math.min(100, Math.max(0, (Number(academic.ranking) / Number(academic.totalStudents)) * 100))
    : null
)
const rankingText = computed(() =>
  hasRanking.value ? `${academic.ranking} / ${academic.totalStudents}` : '待同步'
)
const rankingPercentText = computed(() =>
  rankingPercent.value === null
    ? '排名百分比待同步'
    : `位于专业前 ${rankingPercent.value.toFixed(1)}%`
)
const rankingBarWidth = computed(() =>
  rankingPercent.value === null ? '0%' : `${Math.max(4, rankingPercent.value)}%`
)

const loadAcademicPerformance = async () => {
  loading.value = true
  error.value = ''
  try {
    const studentId = authStore.user?.studentId || 'student'
    const data = await applicationsStore.fetchStatistics(studentId)
    academic.gpa = data.gpa ?? null
    academic.weightedScore = data.weighted_score ?? data.academic_score ?? null
    academic.totalCourses = data.total_courses ?? data.total_course_count ?? null
    academic.totalCredits = data.total_credits ?? data.credit_total ?? null
    academic.ranking = data.ranking ?? data.major_ranking ?? null
    academic.totalStudents = data.major_total_students ?? data.total_students ?? null
  } catch (loadError) {
    console.error('加载学业成绩失败:', loadError)
    error.value = '暂时无法读取学业成绩，请稍后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(loadAcademicPerformance)
</script>

<style scoped src="@/assets/styles/pages/student/applications/AcademicPerformance.css"></style>
