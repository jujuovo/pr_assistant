<template>
  <section class="page-content material-history">
    <header
      ><div
        ><h1>我的材料</h1
        ><p>查看已保存材料、后台识别进度与审核结果。新材料请从“提交材料”入口申报。</p></div
      ><button class="btn btn-outline" :disabled="loading" @click="load">刷新状态</button></header
    >
    <nav aria-label="材料历史类型"
      ><button class="btn btn-outline" @click="legacy = false">材料记录</button
      ><button class="btn btn-outline" @click="legacy = true">历史兼容记录</button></nav
    >
    <ApplicationHistory v-if="legacy" @edit-application="$emit('edit-application', $event)" />
    <template v-else>
      <label
        >筛选状态<select v-model="filter"
          ><option value="">全部</option
          ><option v-for="(label, key) in states" :key="key" :value="key">{{
            label
          }}</option></select
        ></label
      >
      <p v-if="loading" role="status">正在加载材料记录…</p
      ><p v-if="error" role="alert">{{ error }} <button @click="load">重试</button></p>
      <p v-if="!loading && !filtered.length" class="empty">暂无符合条件的材料记录。</p>
      <article v-for="row in filtered" :key="row.category + '-' + row.id" class="history-card">
        <header
          ><div
            ><span class="badge">{{
              states[row.workflow_state] || states[row.status] || '处理中'
            }}</span
            ><h2>{{
              row.data?.project_name ||
              row.data?.competition_name ||
              row.data?.certification_name ||
              categoryNames[row.category] ||
              '证明材料'
            }}</h2></div
          ><small>{{ row.year }} 年 · 材料 #{{ row.id }}</small></header
        >
        <p v-if="row.last_review" class="review-banner" role="note">
          <strong>{{ row.last_review.decision === 'return' ? '教师已退回' : '教师已通过' }}</strong>
          <span>：{{ row.last_review.comment || '未填写具体意见' }}</span>
          <small v-if="row.last_review.actor"
            >（{{ row.last_review.actor.name }} · {{ formatScoreTime(row.last_review.at) }}）</small
          >
        </p>
        <OcrAssessment v-if="row.category === 'competition'" :advice="row.ocr_assessment" />
        <p v-else-if="row.manual_only">此项通过人工通道核验，不自动计分。</p
        ><p v-else>根据该类别的现行规则审核计分。</p>
        <p v-if="row.category === 'volunteer' && row.analysis?.submitted_hours">
          本次有效工时 {{ row.analysis.submitted_hours.effective_hours }} 小时。
          审核通过后计入周期累计；最终得分请查看加分统计。
        </p>
        <details
          ><summary>申报信息与原件</summary
          ><MaterialFacts
            :data="row.data"
            :labels="
              row.category === 'volunteer'
                ? { award_date: '服务记录日期' }
                : row.category === 'arts_sports'
                  ? { award_date: '获得时间' }
                  : {}
            " /><MaterialImagePreview :attachments="row.attachments || []" /><h3
            v-if="row.ocr_raw_terms"
            >OCR识别结果</h3
          ><MaterialFacts
            v-if="row.ocr_raw_terms && row.category !== 'volunteer'"
            :data="row.ocr_raw_terms?.report?.fields || row.ocr_raw_terms?.fields || {}"
        /></details>
        <VolunteerOcrAssessment
          :assessment="row.volunteer_ocr"
          :appeal="row.appeal"
          :priority="row.priority_review"
          :reports="row.ocr_raw_terms?.reports || []"
        />
        <form v-if="appealOpen === row.id" class="appeal-form" @submit.prevent="appeal(row)">
          <label :for="'appeal-' + row.id"
            >申诉理由<textarea
              :id="'appeal-' + row.id"
              v-model="appealReasons[row.id]"
              maxlength="2000"
              required
              placeholder="说明识别错误或无法识别的原因，教师将结合原件重点核验。"
            />
          </label>
          <button class="btn btn-primary" :disabled="busy">提交申诉并转人工审核</button>
          <button type="button" class="btn btn-outline" :disabled="busy" @click="appealOpen = null"
            >取消</button
          >
        </form>
        <div class="actions">
          <button
            v-if="row.allowed_actions?.includes('recognize')"
            class="btn btn-outline"
            :disabled="busy"
            @click="retryOcr(row)"
            >重新识别</button
          >
          <button
            v-if="row.allowed_actions?.includes('appeal')"
            class="btn btn-outline"
            :disabled="busy"
            @click="appealOpen = row.id"
            >提出申诉</button
          >
          <button
            v-if="row.allowed_actions?.includes('edit')"
            class="btn btn-outline"
            :disabled="busy"
            @click="edit(row)"
            >编辑草稿</button
          >
          <button
            v-if="
              row.category === 'competition' &&
              ['failed', 'stale'].includes(row.ocr_assessment?.job?.status) &&
              row.allowed_actions?.includes('edit')
            "
            class="btn btn-outline"
            :disabled="busy"
            @click="retryOcr(row)"
            >重新识别</button
          >
          <button
            v-if="canSubmit(row)"
            class="btn btn-primary"
            :disabled="busy"
            @click="command(row, 'submit')"
            >正式提交审核</button
          >
          <span v-if="['ocr_queued', 'ocr_running'].includes(row.workflow_state)"
            >识别完成后可查看评估再正式提交；可继续申报其他项目。</span
          >
          <button
            v-if="row.allowed_actions?.includes('withdraw')"
            class="btn btn-outline"
            :disabled="busy"
            @click="command(row, 'withdraw')"
            >撤回为草稿</button
          >
          <button
            v-if="row.allowed_actions?.includes('create_correction')"
            class="btn btn-outline"
            :disabled="busy"
            @click="correct(row)"
            >补正材料</button
          >
          <button
            v-if="row.status === 'rule_reconfirmation_required'"
            class="btn btn-outline"
            :disabled="busy"
            @click="reconfirm(row)"
            >确认新规则并重提</button
          >
          <button
            v-if="row.allowed_actions?.includes('abandon')"
            class="btn btn-outline"
            :disabled="busy"
            @click="command(row, 'abandon')"
            >{{ row.status === 'draft' ? '删除草稿' : '放弃材料' }}</button
          >
        </div></article
      >
      <button v-if="hasMore" class="btn btn-outline" :disabled="loading" @click="loadMore"
        >加载更多历史记录</button
      >
      <p v-if="notice" role="status">{{ notice }}</p>
    </template></section
  >
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import materialApi, { MATERIAL_CATEGORIES } from '@/services/materialApi.js'
import { formatScoreTime } from '@/services/scorePresentation.js'
import MaterialFacts from '@/components/common/MaterialFacts.vue'
import MaterialImagePreview from '@/components/common/MaterialImagePreview.vue'
import OcrAssessment from '@/components/common/OcrAssessment.vue'
import VolunteerOcrAssessment from '@/components/common/VolunteerOcrAssessment.vue'
import ApplicationHistory from './ApplicationHistory.vue'
import { buildCompetitionFacts } from '@/services/competitionMaterial.js'
defineEmits(['edit-application'])
const router = useRouter(),
  records = ref([]),
  loading = ref(false),
  error = ref(''),
  busy = ref(false),
  filter = ref(''),
  notice = ref(''),
  legacy = ref(false),
  cursors = ref({})
const appealOpen = ref(null),
  appealReasons = ref({})
const categoryNames = {
  volunteer: '志愿服务累计工时',
  academic: '学业成绩',
  language: '外语能力',
  student_work: '学生工作',
  honor: '荣誉称号',
  social_practice: '社会实践',
  research: '研究成果',
  arts_sports: '文体活动',
  competition_evidence: '其他竞赛'
}
const states = {
  draft: '草稿',
  ocr_queued: 'OCR队列中',
  ocr_running: 'OCR识别中',
  ready_to_submit: '待提交',
  ocr_failed: '识别异常·可人工核验',
  pending_review: '待审核',
  approved: '已通过',
  approved_ineligible: '已核验·不计分',
  rejected: '已驳回',
  needs_correction: '已退回·待补正',
  rule_reconfirmation_required: '规则更新·待确认',
  rule_unmatched: '规则未匹配',
  rule_available: '待确认规则',
  abandoned: '已放弃'
}
const filtered = computed(() =>
  records.value
    .filter((r) => !filter.value || (r.workflow_state || r.status) === filter.value)
    .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))
)
const hasMore = computed(() => Object.values(cursors.value).some(Boolean))
let timer = null,
  alive = true
async function fetchRows(more = false) {
  const cats = more ? MATERIAL_CATEGORIES.filter((c) => cursors.value[c]) : MATERIAL_CATEGORIES
  const results = await Promise.allSettled(
    cats.map((c) => materialApi.listRecords(c, more ? { after_id: cursors.value[c] } : {}))
  )
  if (!alive) return
  const next = more ? [...records.value] : []
  const failures = []
  results.forEach((result, i) => {
    const c = cats[i]
    if (result.status === 'fulfilled') {
      next.push(...(result.value.records || []))
      cursors.value[c] = result.value.next_after_id
    } else {
      failures.push(categoryNames[c] || c)
      if (!more) next.push(...records.value.filter((r) => r.category === c))
    }
  })
  records.value = next
  error.value = failures.length ? '以下类别未能加载，请重试：' + failures.join('、') : ''
}
async function load() {
  if (loading.value) return
  loading.value = true
  try {
    await fetchRows()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function loadMore() {
  loading.value = true
  try {
    await fetchRows(true)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function canSubmit(row) {
  return (
    row.allowed_actions?.includes('submit') &&
    !['ocr_queued', 'ocr_running'].includes(row.workflow_state) &&
    row.attachments?.length
  )
}
function edit(row) {
  router.push({ query: { page: 'materials', category: row.category, editId: row.id } })
}
async function command(row, action) {
  if (busy.value) return
  if (action === 'abandon') {
    // 放弃是不可逆动作：先讲清楚后果，避免误点把材料处理路径断掉。
    const message = row.supersedes_record_id
      ? '放弃这份补正稿后，原本被退回的材料会重新变为可补正。确定放弃吗？'
      : '放弃后该材料不再参与审核与计分，且无法恢复。确定放弃吗？'
    if (!window.confirm(message)) return
  }
  busy.value = true
  try {
    await materialApi[action](row.category, row.id, row.version)
    notice.value = action === 'submit' ? '材料已正式提交，等待教师审核。' : '材料状态已更新。'
    await load()
  } catch (e) {
    error.value = e.message + '；请刷新后重试。'
  } finally {
    busy.value = false
  }
}
async function retryOcr(row) {
  busy.value = true
  try {
    if (row.category === 'volunteer') await materialApi.startVolunteerOcr(row.id, row.version)
    else await materialApi.startCompetitionOcr(row.id, row.version)
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function appeal(row) {
  const reason = appealReasons.value[row.id]?.trim()
  if (!reason) {
    error.value = '请填写申诉理由。'
    return
  }
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await materialApi.appealVolunteer(row.id, row.version, reason)
    appealOpen.value = null
    notice.value = '申诉已提交，已转人工审核并标记为重点核验。'
    await load()
  } catch (e) {
    error.value = e.status === 409 ? '材料状态已变化，请刷新后重试。申诉理由已保留。' : e.message
  } finally {
    busy.value = false
  }
}
async function correct(row) {
  busy.value = true
  try {
    const entry = await materialApi.getCompetitionCatalogItem(row.data.competition_id)
    const correction = await materialApi.createCorrection(
      'competition',
      row.id,
      row.version,
      buildCompetitionFacts(row.data, entry.field_schema)
    )
    edit(correction)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function reconfirm(row) {
  busy.value = true
  try {
    const entry = await materialApi.getCompetitionCatalogItem(row.data.competition_id)
    await materialApi.reconfirmCompetition(
      row.id,
      row.version,
      buildCompetitionFacts(row.data, entry.field_schema)
    )
    notice.value = '已确认当前规则并重新提交审核。'
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function refreshActive() {
  if (!alive || legacy.value || busy.value || loading.value) return
  const pending = records.value.filter((row) =>
    ['ocr_queued', 'ocr_running'].includes(row.workflow_state)
  )
  const result = await Promise.allSettled(
    pending.map((row) => materialApi.getRecord(row.category, row.id))
  )
  if (!alive || busy.value || loading.value) return
  result.forEach((r, i) => {
    if (r.status === 'fulfilled') {
      const index = records.value.findIndex(
        (row) => row.id === pending[i].id && row.category === pending[i].category
      )
      if (index >= 0) records.value[index] = r.value
    } else {
      error.value = '后台进度暂未更新，请点击刷新状态重试。'
    }
  })
}
onMounted(async () => {
  await load()
  if (alive) timer = setInterval(refreshActive, 5000)
})
onBeforeUnmount(() => {
  alive = false
  clearInterval(timer)
})
</script>
<style scoped>
.review-banner {
  margin: 0.5rem 0;
  padding: 0.6rem 0.9rem;
  border-left: 3px solid #d97706;
  border-radius: 0.35rem;
  background: rgba(217, 119, 6, 0.08);
  font-size: 0.9rem;
}
.review-banner small {
  opacity: 0.75;
}
.appeal-form {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  padding: 16px;
  border: 1px solid #e6c98d;
  border-radius: 10px;
  background: #fffaf0;
}
.appeal-form label {
  display: grid;
  gap: 8px;
  width: 100%;
}
.appeal-form textarea {
  min-height: 90px;
  padding: 12px;
  border: 1px solid #b9c7d8;
  border-radius: 8px;
  font: inherit;
}
.material-history {
  display: grid;
  gap: 20px;
}
.material-history header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
}
.material-history h1 {
  margin: 0;
}
.material-history p {
  color: #59677b;
  line-height: 1.7;
}
.history-card {
  padding: 24px;
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
  display: grid;
  gap: 18px;
}
.history-card h2 {
  font-size: 19px;
}
.badge {
  padding: 5px 10px;
  border-radius: 20px;
  background: #eef5ff;
  color: #18528b;
}
.actions,
nav {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
select {
  padding: 9px;
  margin-left: 12px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
.empty {
  padding: 32px;
  text-align: center;
  background: #f8fafc;
  border-radius: 12px;
}
.btn {
  min-height: 40px;
  padding: 8px 15px;
}
.history-card details {
  padding: 14px;
  background: #f8fafc;
  border-radius: 8px;
}
@media (max-width: 640px) {
  .material-history header {
    align-items: flex-start;
    flex-direction: column;
  }
  .history-card {
    padding: 16px;
  }
  .actions button {
    width: 100%;
  }
}
</style>
