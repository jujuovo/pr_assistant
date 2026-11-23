<template>
  <section class="page-content teacher-student-summary">
    <header class="page-title">
      <div>
        <h1>学生竞赛计分汇总</h1>
        <p> 按学号和周期查看竞赛材料、候选分、计入分与排除原因。 </p>
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
      <h2 class="summary-result-title">{{ summary.student_id }} · {{ summary.year }} 周期</h2>
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

      <div v-else class="summary-scroll" tabindex="0" role="region" aria-label="竞赛计分明细"
        ><table class="application-table summary-table">
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
                <button
                  v-if="item.attachments?.length"
                  type="button"
                  class="btn btn-outline"
                  @click="openEvidence(item, $event)"
                >
                  查看原件{{ item.attachments.length > 1 ? `（${item.attachments.length}）` : '' }}
                </button>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table></div
      >

      <p class="summary-footnote">
        该页面不允许编辑材料、规则、候选分或计入分。候选分按原规则版本保留，限项按本周期当前规则统一重算。
        <template v-if="hiddenNote"> {{ hiddenNote }}</template>
      </p>
    </template>

    <p v-else class="review-state" role="status">
      输入学生学号后查询该生当前周期的竞赛计分汇总。
    </p>
    <dialog ref="evidenceDialog" class="evidence-dialog" aria-labelledby="summary-evidence-title" @close="closeEvidence">
      <header class="evidence-header">
        <h2 id="summary-evidence-title">{{ evidence?.project_name || '证明原件' }}</h2>
        <button type="button" class="btn btn-outline" autofocus @click="evidenceDialog.close()">关闭</button>
      </header>
      <template v-if="evidence">
        <label v-if="evidence.attachments.length > 1" class="evidence-select">
          选择附件
          <select v-model="attachmentIndex">
            <option v-for="(file, index) in evidence.attachments" :key="file.id" :value="index">
              {{ file.filename }}
            </option>
          </select>
        </label>
        <p v-if="previewLoading" role="status">正在加载原件…</p>
        <p v-else-if="previewError" role="alert">{{ previewError }}</p>
        <figure v-else-if="previewUrl" class="evidence-preview">
          <img v-if="previewKind === 'image'" :src="previewUrl" :alt="attachment.filename" @error="showPreviewError" />
          <iframe v-else :src="previewUrl" :title="attachment.filename" @error="showPreviewError"></iframe>
          <figcaption>{{ attachment.filename }}</figcaption>
        </figure>
      </template>
    </dialog>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import materialApi from '@/services/materialApi.js'
import {
  scoreStatusText,
  scoreExclusionText,
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

const evidenceDialog = ref(null)
const evidence = ref(null)
const attachmentIndex = ref(0)
const attachment = computed(() => evidence.value?.attachments[attachmentIndex.value])
const previewUrl = ref('')
const previewKind = ref('')
const previewError = ref('')
const previewLoading = ref(false)
let evidenceTrigger

function openEvidence(item, event) {
  evidenceTrigger = event.currentTarget
  attachmentIndex.value = 0
  evidence.value = item
  evidenceDialog.value.showModal()
}

function closeEvidence() {
  evidence.value = null
  evidenceTrigger?.focus()
  evidenceTrigger = null
}

function showPreviewError() {
  previewError.value = '原件无法预览，请关闭后重试。'
}

watch(attachment, async (file, _, onCleanup) => {
  previewUrl.value = ''
  previewError.value = ''
  previewLoading.value = Boolean(file)
  if (!file) return

  const request = new AbortController()
  let objectUrl
  onCleanup(() => {
    request.abort()
    if (objectUrl) URL.revokeObjectURL(objectUrl)
  })
  try {
    const url = new URL(file.url, window.location.origin)
    url.searchParams.set('inline', '1')
    const response = await fetch(url, { credentials: 'same-origin', signal: request.signal })
    if (!response.ok) throw new Error('attachment unavailable')
    const blob = await response.blob()
    if (request.signal.aborted) return
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'application/pdf'].includes(blob.type)) {
      previewError.value = '此附件格式暂不支持网页预览。'
      return
    }
    objectUrl = URL.createObjectURL(blob)
    previewKind.value = blob.type.startsWith('image/') ? 'image' : 'pdf'
    previewUrl.value = objectUrl
  } catch {
    if (!request.signal.aborted) showPreviewError()
  } finally {
    if (!request.signal.aborted) previewLoading.value = false
  }
})

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
  if (item.exclusion_reason) return scoreExclusionText(item.exclusion_reason)
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

<style scoped src="@/assets/styles/pages/teacher/students/TeacherStudentSummary.css"></style>
