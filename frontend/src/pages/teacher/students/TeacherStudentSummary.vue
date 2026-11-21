<template>
  <section class="page-content teacher-student-summary">
    <header class="summary-hero">
      <div>
        <p class="eyebrow">MaterialRecord · 正式竞赛链路</p>
        <h2>学生竞赛计分汇总</h2>
        <p>
          候选分、计入分与排除原因全部由后端权威投影给出；本页只读，不提供任何改分、改规则或改材料的入口。
        </p>
      </div>
      <div class="cycle-chip">
        <span>申报周期</span>
        <strong>{{ year || '—' }}</strong>
      </div>
    </header>

    <form class="filters primary-section-frame" @submit.prevent="load">
      <label>
        学生学号
        <input
          v-model.trim="studentId"
          list="summary-student-options"
          placeholder="例如 student001"
          autocomplete="off"
        />
        <datalist id="summary-student-options">
          <option v-for="id in studentCandidates" :key="id" :value="id" />
        </datalist>
      </label>
      <label>
        申报周期
        <input v-model.number="year" type="number" min="2000" max="2100" />
      </label>
      <button class="btn btn-primary" type="submit" :disabled="loading || !studentId">
        {{ loading ? '查询中…' : '查询汇总' }}
      </button>
    </form>

    <p v-if="validationError" class="review-state error" role="alert">{{ validationError }}</p>

    <p v-else-if="loading" class="review-state" role="status">正在读取该学生的竞赛计分汇总…</p>

    <section v-else-if="error" class="review-state error" role="alert">
      <p>{{ error }}</p>
      <button class="btn btn-outline" type="button" @click="load">重新加载</button>
    </section>

    <template v-else-if="summary">
      <div class="summary-metrics">
        <article>
          <span>材料总数</span><strong>{{ aggregate.record_count ?? items.length }}</strong>
        </article>
        <article class="metric-included">
          <span>计入项数</span><strong>{{ aggregate.included_count ?? '—' }}</strong>
        </article>
        <article class="metric-excluded">
          <span>排除项数</span><strong>{{ aggregate.excluded_count ?? '—' }}</strong>
        </article>
        <article>
          <span>待处理项</span><strong>{{ aggregate.pending_count ?? '—' }}</strong>
        </article>
        <article class="metric-score">
          <span>候选分合计</span><strong>{{ aggregate.total_candidate_score ?? '—' }}</strong>
        </article>
        <article class="metric-score">
          <span>计入分合计</span><strong>{{ aggregate.total_effective_score ?? '—' }}</strong>
        </article>
      </div>

      <p v-if="!items.length" class="review-state" role="status">
        {{ summary.student_id }} 在 {{ summary.year }} 周期没有竞赛材料记录。请确认学号与周期是否
        正确，学生提交材料后此处才会出现明细。
      </p>

      <table v-else class="application-table summary-table">
        <thead>
          <tr>
            <th>项目</th>
            <th>级别</th>
            <th>奖项</th>
            <th>获奖日期</th>
            <th>材料状态</th>
            <th>候选分</th>
            <th>计入分</th>
            <th>排除原因</th>
            <th>其他事实</th>
            <th>原件</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.record_id">
            <td>
              <strong>{{ item.project_name || '未命名项目' }}</strong>
              <small v-if="item.superseded_by_record_id" class="cell-replaced"
                >已被新版本（#{{ item.superseded_by_record_id }}）取代，以新版本为准</small
              >
              <small v-else class="cell-meta">{{ item.competition_id }}</small>
            </td>
            <td>{{ competitionLevelText(item.level) }}</td>
            <td>{{ competitionAwardText(item.award) }}</td>
            <td>{{ item.award_date || '—' }}</td>
            <td>
              <span class="status-badge">{{ scoreStatusText(item.status) }}</span>
            </td>
            <td>{{ item.candidate_score ?? '—' }}</td>
            <td :class="{ 'cell-zero': !item.included }">
              {{ item.effective_score ?? '—' }}
            </td>
            <td>{{ exclusionText(item) }}</td>
            <td>{{ otherFactsText(item) }}</td>
            <td>
              <a
                v-if="item.attachments && item.attachments.length"
                :href="item.attachments[0].url"
                target="_blank"
                rel="noopener"
                >查看{{ item.attachments.length > 1 ? `(${item.attachments.length})` : '' }}</a
              >
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </table>

      <p class="summary-footnote">
        该页面不允许编辑材料、规则、候选分或计入分。计分结果以教师审核通过时的规则包版本为准。
        <template v-if="hiddenNote"> {{ hiddenNote }}</template>
      </p>
    </template>

    <p v-else class="review-state" role="status">
      输入学生学号后查询该生当前周期的竞赛计分汇总。
    </p>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import materialApi from '@/services/materialApi.js'
import {
  scoreStatusText,
  competitionLevelText,
  competitionAwardText
} from '@/services/scorePresentation.js'

const studentId = ref('')
const year = ref(new Date().getFullYear())
const summary = ref(null)
const error = ref('')
const validationError = ref('')
const loading = ref(false)
const studentCandidates = ref([])

const items = computed(() => summary.value?.items || [])
const aggregate = computed(() => summary.value?.aggregate || {})
// 指标卡只统计明细内的材料，草稿与已放弃要单独说明，教师才能把总数算平。
const hiddenNote = computed(() => {
  const draft = Number(aggregate.value.draft_count || 0)
  const abandoned = Number(aggregate.value.abandoned_count || 0)
  if (!draft && !abandoned) return ''
  const parts = []
  if (draft) parts.push(`${draft} 条学生草稿`)
  if (abandoned) parts.push(`${abandoned} 条学生已放弃`)
  return `另有 ${parts.join('、')}，未提交或已作废，不计入本次汇总。`
})

function exclusionText(item) {
  if (item.exclusion_reason) return item.exclusion_reason
  if (item.status === 'needs_correction') return '审核退回，待学生补正'
  if (item.included === false) return '未计入'
  if (item.status === 'scored') return '—'
  return '待审核'
}

// 表格列已覆盖主要事实，这里补齐 key_facts 里其余权威事实：
// 核对 CSP、团队赛、分组赛道这类材料时，教师需要看到开关字段而不是被省略。
const FACT_LABELS = {
  participation_mode: '参赛方式',
  team_size: '团队人数',
  personal_rank: '本人排序',
  event_format: '赛制',
  group: '组别',
  track: '赛道',
  csp_percentile: 'CSP 百分位'
}
const FACT_VALUE_LABELS = { individual: '个人', team: '团队' }

function otherFactsText(item) {
  const facts = item.key_facts || {}
  const parts = []
  for (const [key, label] of Object.entries(FACT_LABELS)) {
    const raw = facts[key]
    if (raw === undefined || raw === null || raw === '') continue
    parts.push(`${label}：${FACT_VALUE_LABELS[raw] || raw}`)
  }
  return parts.length ? parts.join('；') : '—'
}

async function loadCycleContext() {
  // 默认周期必须来自后端当前申报周期，不能再用浏览器年份猜；
  // 竞赛周期是 2028，用本地年份会永远查不到数据。
  try {
    const workbench = await materialApi.getCompetitionWorkbenchSummary()
    if (workbench?.cycle_code) year.value = Number(workbench.cycle_code)
    const ids = new Set()
    for (const row of [...(workbench?.items || []), ...(workbench?.reviewed_items || [])]) {
      if (row.student_id) ids.add(row.student_id)
    }
    studentCandidates.value = [...ids].sort()
    if (!studentId.value && studentCandidates.value.length === 1) {
      studentId.value = studentCandidates.value[0]
    }
  } catch (cause) {
    error.value = cause.message || '当前申报周期读取失败，请手动填写周期后重试。'
  }
}

async function load() {
  validationError.value = ''
  error.value = ''
  const id = studentId.value.trim()
  const cycle = Number(year.value)
  if (!id) {
    validationError.value = '请填写学生学号后再查询。'
    summary.value = null
    return
  }
  if (!Number.isInteger(cycle) || cycle < 2000 || cycle > 2100) {
    validationError.value = '申报周期必须是 2000 至 2100 之间的整数。'
    summary.value = null
    return
  }
  loading.value = true
  try {
    summary.value = await materialApi.getTeacherCompetitionSummary(id, cycle)
  } catch (cause) {
    summary.value = null
    error.value = cause.message || '学生竞赛计分汇总加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadCycleContext()
  if (studentId.value) await load()
})
</script>

<style scoped>
.summary-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}
.summary-hero h2 {
  margin: 0.25rem 0 0.5rem;
}
.summary-hero .eyebrow {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.7;
}
.summary-hero p {
  max-width: 46rem;
  margin: 0;
}
.cycle-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.6rem 1.2rem;
  border-radius: 0.75rem;
  background: rgba(37, 99, 235, 0.08);
}
.cycle-chip span {
  font-size: 0.75rem;
  opacity: 0.75;
}
.cycle-chip strong {
  font-size: 1.4rem;
  line-height: 1.2;
}
.summary-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: 0.75rem;
  margin: 1rem 0;
}
.summary-metrics article {
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(15, 23, 42, 0.12);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.summary-metrics span {
  font-size: 0.8rem;
  opacity: 0.75;
}
.summary-metrics strong {
  font-size: 1.35rem;
  line-height: 1.2;
}
.metric-included {
  border-color: rgba(22, 163, 74, 0.35);
  background: rgba(22, 163, 74, 0.06);
}
.metric-excluded {
  border-color: rgba(220, 38, 38, 0.3);
  background: rgba(220, 38, 38, 0.05);
}
.metric-score {
  border-color: rgba(37, 99, 235, 0.3);
  background: rgba(37, 99, 235, 0.05);
}
.summary-table td small.cell-meta {
  display: block;
  font-size: 0.72rem;
  opacity: 0.6;
}
.summary-table td small.cell-replaced {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.72rem;
  color: #b45309;
}
.cell-zero {
  opacity: 0.55;
}
.summary-footnote {
  margin-top: 0.75rem;
  font-size: 0.85rem;
  opacity: 0.8;
}
</style>
