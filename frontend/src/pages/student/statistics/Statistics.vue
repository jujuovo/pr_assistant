<template>
  <section class="page-content authoritative-score-page">
    <header class="statistics-heading"
      ><div
        ><p class="statistics-eyebrow">我的推免 · 成绩总览</p><h1>加分统计</h1
        ><p>查看已审核材料的计分结果与明细</p></div
      ><span v-if="score && score.status !== 'no_authoritative_snapshot'" class="score-status">{{
        scoreStatusText(score.status)
      }}</span></header
    >
    <p v-if="loading" class="statistics-state" role="status">正在加载计分结果…</p>
    <div v-if="error" class="statistics-state statistics-error" role="alert"
      >{{ error }} <button class="btn btn-outline" @click="load">重新加载</button></div
    >
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
            ><h2>推免综合成绩</h2
            ><div class="score-main-value"
              ><strong>{{ score.comprehensive_score }}</strong
              ><span>分</span></div
            ><p>本周期综合计分结果</p></div
          >
          <dl class="score-components"
            ><div
              ><dt>学业基础分</dt><dd>{{ score.base.academic_score }}</dd></div
            ><div
              ><dt>学术专长最终实际计分</dt><dd>{{ score.categories.academic.effective_score }}</dd></div
            ><div
              ><dt>综合表现最终实际计分</dt
              ><dd>{{ score.categories.comprehensive.effective_score }}</dd></div
            ></dl
          >
        </section>
        <small v-if="score.categories.academic.note" class="score-cap-note">{{ score.categories.academic.note }}</small>
        <div class="score-metadata"
          ><span>计分结果：第{{ score.snapshot_version }}版</span
          ><span>更新时间（北京时间）：{{ formatScoreTime(score.updated_at) }}</span></div
        >
        <details class="score-policy"
          ><summary
            ><span>计分依据</span
            ><span class="score-policy-name">{{ scoreRuleVersions(score) }}</span
            ><span class="score-policy-toggle"
              >查看公式 <span aria-hidden="true">⌄</span></span
            ></summary
          ><p>计算公式：{{ scoreFormulaText(score.formula) }}</p></details
        >
      </template>
      <section class="score-details-panel">
        <div class="score-details-heading"
          ><h2>加分明细</h2><span>共 {{ rows.length }} 项材料</span></div
        >
        <section v-for="group in groups" :key="group.key" class="score-group">
          <h3>{{ group.label }} · 实际加分 {{ score.categories[group.key]?.effective_score ?? '—' }} 分</h3>
        <div class="score-table-container"
          ><table class="application-table"
            ><thead
              ><tr
                ><th scope="col">材料</th><th scope="col">材料状态</th><th scope="col">计分规则</th
                ><th scope="col" class="numeric-cell">候选分</th
                ><th scope="col" class="numeric-cell">逐项加分</th
                ><th scope="col">计入状态／排除原因</th><th scope="col">更新时间</th
                ><th scope="col">操作</th></tr
              ></thead
            ><tbody>
              <tr v-for="row in group.rows" :key="row.id"
                ><td class="material-title">{{ row.title }}</td
                ><td>{{ statusText(row) }}</td
                ><td class="rule-cell">{{ row.ruleLabel }}</td
                ><td class="numeric-cell">{{ row.candidateScore ?? '—' }}</td
                ><td class="numeric-cell included-score">{{ row.includedScore ?? '0' }}</td
                ><td
                  ><span :class="{ 'included-label': row.included }">{{
                    row.included ? '已计入' : row.reason || '未计入'
                  }}</span></td
                ><td class="time-cell">{{ formatScoreTime(row.updatedAt) }}</td
                ><td
                  ><div class="score-row-actions"
                    ><button
                      type="button"
                      class="btn score-details-button"
                      :aria-label="'查看详情：' + row.title"
                      @click="openDetails(row, $event)"
                      >查看详情</button
                    ><button
                      v-if="
                        row.allowedActions.includes('confirm_submit') ||
                        row.scoringStatus === 'rule_available'
                      "
                      class="btn btn-primary"
                      :disabled="reconfirmingId === row.sourceId"
                      @click="reconfirm(row)"
                      >{{
                        reconfirmingId === row.sourceId ? '正在提交…' : '确认规则并重新提交'
                      }}</button
                    ></div
                  ></td
                ></tr
              >
              <tr v-if="!rows.length"
                ><td colspan="8" class="statistics-empty"
                  >暂无计分明细，审核完成后会在这里展示。</td
                ></tr
              >
            </tbody></table
          ></div
        >
        </section>
        <p v-if="!rows.length">暂无计分明细</p>
      </section>
    </template>
    <ScoreSourceDetail
      v-if="selected"
      :row="selected"
      :student-id="studentId"
      :year="score.year"
      @close="closeDetails"
    />
  </section>
</template>
<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useWorkflowStore } from '@/stores/workflow.js'
import {
  scoreRows,
  scoreStatusText,
  scoreRuleVersions,
  scoreFormulaText,
  formatScoreTime
} from '@/services/scorePresentation.js'
import materialApi from '@/services/materialApi.js'
import ScoreSourceDetail from '@/components/student/ScoreSourceDetail.vue'
const auth = useAuthStore(),
  workflow = useWorkflowStore(),
  loading = ref(false),
  error = ref(''),
  reconfirmingId = ref(null),
  selected = ref(null)
const studentId = computed(() => auth.user?.studentId || auth.user?.student_id)
const score = computed(() => workflow.score),
  rows = computed(() => scoreRows(score.value))
const groups = computed(() => [
  { key: 'academic', label: '学术专长' },
  { key: 'comprehensive', label: '综合表现' }
].map(group => ({ ...group, rows: rows.value.filter(row => row.group === group.key) }))
  .filter(group => group.rows.length))
const statusText = (row) => scoreStatusText(row.scoringStatus || row.verificationStatus)
let detailTrigger = null
function openDetails(row, event) {
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
async function reconfirm(row) {
  reconfirmingId.value = row.sourceId
  error.value = ''
  try {
    await materialApi.reconfirmSubmit(
      row.category,
      Number(row.sourceId),
      row.sourceVersion,
      row.ruleVersionId
    )
    await load()
  } catch (e) {
    error.value = e.message || '重新提交失败'
  } finally {
    reconfirmingId.value = null
  }
}
onMounted(load)
</script>
<style scoped src="@/assets/styles/pages/student/statistics/Statistics.2.css"></style>
