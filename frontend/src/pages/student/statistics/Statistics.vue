<template>
  <section class="page-content authoritative-score-page">
    <header class="statistics-heading"><h1>加分统计</h1><p>以下结果全部来自后端权威计分快照。</p></header>
    <p v-if="loading" role="status">正在加载权威快照…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="score">
      <section v-if="score.status === 'no_authoritative_snapshot'" class="detail-panel" role="status">
        尚无权威计分快照；待审核或待重新确认材料不会被前端估分。
      </section>
      <template v-else>
        <section class="score-overview" aria-label="权威快照总览">
          <article><strong>学业基础分</strong><span>{{ score.base.academic_score }}</span></article>
          <article><strong>学术专长计入分</strong><span>{{ score.categories.academic.effective_score }}</span></article>
          <article><strong>综合表现计入分</strong><span>{{ score.categories.comprehensive.effective_score }}</span></article>
          <article><strong>推免综合成绩</strong><span>{{ score.comprehensive_score }}</span></article>
        </section>
        <p>快照版本：{{ score.snapshot_version }}；状态：{{ score.status }}；更新时间：{{ score.updated_at }}</p>
        <p>规则版本：{{ score.rule_version_ids.join(', ') || '无' }}；公式：{{ score.formula }}</p>
      </template>

      <section class="detail-panel">
        <div class="detail-panel-title"><span>权威计分明细</span></div>
        <table class="application-table">
          <thead><tr><th>材料</th><th>材料状态</th><th>规则版本</th><th>候选分</th><th>计入分</th><th>计入状态/排除原因</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td>{{ row.title }}</td><td>{{ statusText(row) }}</td><td>{{ row.ruleVersionId ?? '-' }}</td>
              <td>{{ row.candidateScore ?? '-' }}</td><td>{{ row.includedScore ?? '0' }}</td>
              <td>{{ row.included ? '已计入' : (row.reason || '未计入') }}</td><td>{{ row.updatedAt || '-' }}</td>
              <td><button v-if="row.allowedActions.includes('confirm_submit') || row.scoringStatus === 'rule_available'"
                class="btn btn-primary" :disabled="reconfirmingId === row.sourceId" @click="reconfirm(row)">
                {{ reconfirmingId === row.sourceId ? '正在提交…' : '确认规则并重新提交' }}
              </button><span v-else>仅查看</span></td>
            </tr>
            <tr v-if="rows.length === 0"><td colspan="8">暂无权威计分明细</td></tr>
          </tbody>
        </table>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useWorkflowStore } from '@/stores/workflow.js'
import { scoreRows } from '@/services/scorePresentation.js'
import materialApi from '@/services/materialApi.js'

const auth = useAuthStore()
const workflow = useWorkflowStore()
const loading = ref(false)
const error = ref('')
const reconfirmingId = ref(null)
const score = computed(() => workflow.score)
const rows = computed(() => scoreRows(score.value))
const statusText = row => row.scoringStatus || row.verificationStatus || '待处理'

async function load() {
  loading.value = true; error.value = ''
  try { await workflow.loadCurrentScore(auth.user?.studentId || auth.user?.student_id) }
  catch (cause) { error.value = cause.message || '加载权威计分快照失败' }
  finally { loading.value = false }
}
async function reconfirm(row) {
  reconfirmingId.value = row.sourceId; error.value = ''
  try {
    await materialApi.reconfirmSubmit(row.category, Number(row.sourceId), row.sourceVersion, row.ruleVersionId)
    await load()
  } catch (cause) { error.value = cause.message || '重新提交失败' }
  finally { reconfirmingId.value = null }
}
onMounted(load)
</script>

<style scoped src="@/assets/styles/pages/student/statistics/Statistics.2.css"></style>
