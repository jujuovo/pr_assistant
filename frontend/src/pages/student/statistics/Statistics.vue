<template>
  <section class="page-content authoritative-score-page">
    <header class="page-title">
      <h1>加分统计</h1>
      <span v-if="score && score.status !== 'no_authoritative_snapshot'" class="score-status">
        {{ scoreStatusText(score.status) }}</span
      >
    </header>
    <p v-if="loading" class="statistics-state" role="status">正在加载计分结果…</p>
    <div v-if="error" class="statistics-state statistics-error" role="alert"
      >{{ error }} <button class="btn btn-outline" @click="load">重新加载</button>
    </div>
    <template v-if="score">
      <section
        v-if="score.status === 'no_authoritative_snapshot'"
        class="statistics-state"
        role="status"
        >尚无正式计分结果，待材料审核完成后更新。</section
      >
      <template v-else>
        <section class="score-overview" aria-label="成绩总览">
          <div class="score-main"
            ><h2>推免综合成绩</h2>
            <div class="score-main-value"
              ><strong>{{ score.comprehensive_score }}</strong> <span>分</span> </div
            ><p>本周期综合计分结果</p>
          </div>
          <dl class="score-components"
            ><div>
              <dt>学业基础</dt>
              <dd>{{ score.base.academic_score }}</dd> </div
            ><div>
              <dt>学术专长</dt>
              <dd>{{ score.categories.academic.effective_score }}</dd> </div
            ><div>
              <dt>综合表现</dt>
              <dd>{{ score.categories.comprehensive.effective_score }}</dd>
            </div></dl
          >
          <small v-if="score.categories.academic.note" class="score-cap-note">{{
            score.categories.academic.note
          }}</small>
        </section>

        <section class="score-policy">
          <h2>计算公式</h2>
          <p class="score-formula">{{ scoreFormulaText(score.formula) }}</p>
          <small v-if="score.faculty_scoring_policy"
            >计分依据 · {{ score.faculty_scoring_policy.title }}（版本编号
            {{ score.faculty_scoring_policy.id }}）</small
          >
          <small>专项规则 · {{ scoreRuleVersions(score) }}</small>
        </section></template
      >
      <section class="score-details-panel">
        <div class="score-details-heading"
          ><h2>加分明细</h2>
          <span>共 {{ rows.length }} 项材料</span>
        </div>
        <section v-for="group in groups" :key="group.key" class="score-group">
          <h3
            >{{ group.label }} · 实际加分
            {{ score.categories[group.key]?.effective_score ?? '—' }} 分</h3
          >
          <div class="score-table-container"
            ><table class="application-table"
              ><thead>
                <tr
                  ><th scope="col">材料</th>
                  <th scope="col">材料状态</th>

                  <th scope="col" class="numeric-cell">候选分</th>
                  <th scope="col" class="numeric-cell">逐项加分</th>
                  <th scope="col">计入状态／排除原因</th>

                  <th scope="col">操作</th>
                </tr></thead
              >
              <tbody>
                <tr v-for="row in group.rows" :key="row.id"
                  ><td class="material-title"
                    >{{ row.title }}<small>计分规则 · {{ row.ruleLabel }}</small></td
                  >
                  <td>{{ statusText(row) }}</td>

                  <td class="numeric-cell">{{ row.candidateScore ?? '—' }}</td>
                  <td class="numeric-cell included-score">{{ row.includedScore ?? '0' }}</td>
                  <td
                    ><span :class="{ 'included-label': row.included }">{{
                      row.included ? '已计入' : row.reason || '未计入'
                    }}</span>
                  </td>
                  <td
                    ><div class="score-row-actions"
                      ><button
                        type="button"
                        class="btn btn-secondary score-details-button"
                        :aria-label="'查看详情：' + row.title"
                        @click="openDetails(row, $event)"
                        >查看详情</button
                      >
                    </div></td
                  >
                </tr></tbody
              >
            </table></div
          >
        </section>
        <p v-if="!rows.length" class="statistics-state">暂无计分明细，审核完成后会在这里展示。</p>
      </section></template
    >
    <ScoreSourceDetail
      v-if="selected"
      :row="selected"
      :student-id="studentId"
      :year="score.year"
      :can-reconfirm="
        selected.allowedActions.includes('confirm_submit') ||
        selected.scoringStatus === 'rule_available'
      "
      :submitting="reconfirmingId !== null"
      :submit-error="submitError"
      @reconfirm="reconfirm(selected, $event)"
      @close="closeDetails"
  /></section>
</template>
<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useWorkflowStore } from '@/stores/workflow.js'
import {
  scoreRows,
  scoreStatusText,
  scoreRuleVersions,
  scoreFormulaText
} from '@/services/scorePresentation.js'
import { buildCompetitionFacts } from '@/services/competitionMaterial.js'
import materialApi from '@/services/materialApi.js'
import ScoreSourceDetail from '@/components/student/ScoreSourceDetail.vue'
const auth = useAuthStore(),
  workflow = useWorkflowStore(),
  loading = ref(false),
  error = ref(''),
  reconfirmingId = ref(null),
  submitError = ref(''),
  selected = ref(null)
const studentId = computed(() => auth.user?.studentId || auth.user?.student_id)
const score = computed(() => workflow.score),
  rows = computed(() => scoreRows(score.value))
const groups = computed(() =>
  [
    { key: 'academic', label: '学术专长' },
    { key: 'comprehensive', label: '综合表现' }
  ]
    .map((group) => ({ ...group, rows: rows.value.filter((row) => row.group === group.key) }))
    .filter((group) => group.rows.length)
)
const statusText = (row) => scoreStatusText(row.scoringStatus || row.verificationStatus)
let detailTrigger = null
function openDetails(row, event) {
  submitError.value = ''
  detailTrigger = event.currentTarget
  selected.value = row
}
async function closeDetails() {
  selected.value = null
  await nextTick()
  if (detailTrigger?.isConnected) detailTrigger.focus()
  detailTrigger = null
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    await workflow.loadCurrentScore(studentId.value)
  } catch (e) {
    error.value = e.message || '加载计分结果失败'
  } finally {
    loading.value = false
  }
}
async function reconfirm(row, competitionRecord) {
  if (reconfirmingId.value !== null) return
  submitError.value = ''
  reconfirmingId.value = row.sourceId
  error.value = ''
  try {
    if (row.category === 'competition') {
      if (competitionRecord?.status !== 'rule_reconfirmation_required') return
      const catalog = await materialApi.getCompetitionCatalogItem(
        competitionRecord.data.competition_id
      )
      await materialApi.reconfirmCompetition(
        Number(row.sourceId),
        competitionRecord.version,
        buildCompetitionFacts(competitionRecord.data, catalog.field_schema)
      )
    } else
      await materialApi.reconfirmSubmit(
        row.category,
        Number(row.sourceId),
        row.sourceVersion,
        row.ruleVersionId
      )
    if (selected.value === row) await closeDetails()
    await load()
  } catch (e) {
    if (selected.value === row) submitError.value = e.message || '重新提交失败'
    else error.value = e.message || '重新提交失败'
  } finally {
    reconfirmingId.value = null
  }
}
onMounted(load)
</script>
<style scoped src="@/assets/styles/pages/student/statistics/Statistics.2.css"></style>
