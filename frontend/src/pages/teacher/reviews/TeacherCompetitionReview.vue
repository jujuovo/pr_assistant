<template>
  <section class="competition-review" aria-labelledby="competition-review-title">
    <header class="review-hero"
      ><div
        ><p class="eyebrow">MaterialRecord · 正式竞赛链路</p
        ><h2 id="competition-review-title">{{
          historyMode ? '竞赛审核记录' : '竞赛材料待审工作台'
        }}</h2
        ><p>材料事实、规则依据和候选分均来自后端权威投影；审核动作不会修改规则或分数。</p></div
      ><div v-if="!historyMode" class="pending-total"
        ><strong>{{ workbench.pending_count || 0 }}</strong
        ><span>份待审核</span></div
      ></header
    >
    <p v-if="loading" class="review-state" role="status">正在加载竞赛待审材料…</p>
    <section v-else-if="error" class="review-state error" role="alert"
      ><p>{{ error }}</p
      ><button class="btn btn-outline" @click="load">重新加载</button></section
    >
    <p v-else-if="!displayItems.length" class="review-state" role="status">{{
      historyMode ? '当前周期没有已处理竞赛材料。' : '当前周期没有待审核竞赛材料。'
    }}</p>
    <div v-else class="pending-grid"
      ><article v-for="row in displayItems" :key="row.id" class="pending-card"
        ><div
          ><span class="status-badge">{{ scoreStatusText(row.status) }}</span
          ><h3>{{ row.project_name || row.competition_name }}</h3
          ><p>学生 {{ row.student_id }} · 版本 {{ row.version }}</p
          ><p v-if="historyMode && row.review" class="review-outcome"
            ><strong>{{ reviewDecisionText(row.review.decision) }}</strong
            ><span
              >· {{ row.review.actor?.name || '未知审核人' }}（{{
                row.review.actor?.role === 'admin' ? '管理员' : '教师'
              }}）</span
            ><time>· {{ formatScoreTime(row.review.at) }}</time></p
          ><p v-if="historyMode && row.review?.comment" class="review-opinion"
            >审核意见：{{ row.review.comment }}</p
          ><p v-if="historyMode && row.superseded_by_record_id" class="review-opinion"
            >该记录已被新版本（#{{ row.superseded_by_record_id }}）取代，以新版本结果为准。</p
          ><p v-if="historyMode && !row.review" class="review-opinion"
            >未找到审核结论记录，请打开记录查看历史。</p
          ></div
        ><button class="btn btn-primary" type="button" @click="open(row.id)">{{
          historyMode ? '查看记录' : '核对材料'
        }}</button></article
      ></div
    >
    <section class="summary-card"
      ><div><h3>授权学生汇总</h3><p>按学号读取该生当前周期的竞赛计分反馈。</p></div
      ><div class="summary-search"
        ><label for="summary-student">学生学号</label
        ><input id="summary-student" v-model.trim="studentId" class="form-control" /><button
          class="btn btn-outline"
          :disabled="!studentId"
          @click="loadSummary"
          >查看汇总</button
        ></div
      ><table v-if="summary"
        ><thead
          ><tr
            ><th>项目</th><th>关键事实</th><th>状态</th><th>候选/计入</th><th>操作</th></tr
          ></thead
        ><tbody
          ><tr v-for="item in summary.items" :key="item.record_id"
            ><td>{{ item.project_name }}</td
            ><td
              ><code>{{ JSON.stringify(item.key_facts) }}</code></td
            ><td>{{ item.status }}</td
            ><td>{{ item.candidate_score }} / {{ item.effective_score ?? '-' }}</td
            ><td
              ><button class="btn btn-outline" @click="open(item.record_id)">查看原件</button></td
            ></tr
          ></tbody
        ></table
      ></section
    >
    <dialog v-if="context" open class="review-dialog" aria-labelledby="review-dialog-title"
      ><form method="dialog" class="dialog-shell" @submit.prevent
        ><header
          ><div
            ><p class="eyebrow">只读核验</p
            ><h3 id="review-dialog-title">竞赛材料 #{{ context.record_id }}</h3></div
          ><button class="btn btn-outline" type="button" @click="context = null"
            >关闭</button
          ></header
        ><div class="detail-grid"
          ><section class="evidence-panel"
            ><h4>证明原件</h4><p v-if="!context.attachments.length">未提供附件</p
            ><figure v-for="file in context.attachments" :key="file.id" class="evidence-file"
              ><img
                v-if="file.media_type?.startsWith('image/')"
                :src="file.preview_url"
                :alt="`${file.filename} 证明原件预览`"
              /><figcaption
                ><span>{{ file.filename }}</span
                ><a :href="file.url" target="_blank" rel="noopener">下载原件</a></figcaption
              ></figure
            ></section
          ><section
            ><h4>固定规则依据</h4
            ><p>{{ context.rule_basis.competition_name }} / {{ context.rule_basis.category }}</p
            ><p
              >规则包 v{{ context.rule_basis.package_version }} · 后端候选分
              {{ context.candidate_score }}</p
            ></section
          ><section><h4>学生确认事实</h4><MaterialFacts :data="context.confirmed_terms" /></section
          ><section
            ><h4>OCR 原文（仅辅助）</h4
            ><MaterialFacts
              :data="
                context.ocr_raw_terms?.report?.fields ||
                context.ocr_raw_terms?.fields ||
                context.ocr_raw_terms ||
                {}
              "
            /> </section></div
        ><OcrAssessment :advice="context.ocr_assessment" /><label
          v-if="canReview && needsOcrConfirmation"
          class="ocr-confirmation"
          ><input
            v-model="ocrConfirmed"
            type="checkbox"
          />我已人工核对原件、OCR差异或缺失依据，确认申报事实及候选分。</label
        ><label class="comment-field" for="review-comment"
          >审核意见（通过时选填；退回时必填）<textarea
            id="review-comment"
            ref="commentInput"
            v-model="comment"
            maxlength="2000"
            :disabled="!canReview"
            :aria-invalid="Boolean(commentError)"
            :aria-describedby="commentError ? 'review-comment-error' : undefined"
          ></textarea></label
        ><small v-if="commentError" id="review-comment-error" class="field-error" role="alert">{{
          commentError
        }}</small
        ><p v-if="!canReview" class="review-state">该材料当前不可处理，页面保持只读。</p
        ><footer
          ><button
            v-if="context.allowed_actions.includes('return')"
            class="btn btn-outline"
            :disabled="reviewing"
            @click="review('return')"
            >退回修改</button
          ><button
            v-if="context.allowed_actions.includes('approve')"
            class="btn btn-primary"
            :disabled="reviewing"
            @click="review('approve')"
            >审核通过</button
          ></footer
        ></form
      ></dialog
    >
    <section v-if="context" class="summary-card history-panel"
      ><h3>历史意见与状态</h3><p v-if="!context.history?.length">暂无历史意见。</p
      ><ol v-else
        ><li v-for="(event, index) in context.history" :key="`${event.created_at}-${index}`"
          ><strong>{{ materialEventText(event.action) }}</strong
          ><span
            >{{ event.actor?.name || '系统'
            }}<template v-if="event.comment">· {{ event.comment }}</template></span
          ><time>{{ formatScoreTime(event.created_at) }}</time></li
        ></ol
      ></section
    >
  </section>
</template>
<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import materialApi from '@/services/materialApi.js'
import {
  scoreStatusText,
  formatScoreTime,
  materialEventText,
  reviewDecisionText
} from '@/services/scorePresentation.js'
import MaterialFacts from '@/components/common/MaterialFacts.vue'
import OcrAssessment from '@/components/common/OcrAssessment.vue'
const props = defineProps({ mode: { type: String, default: 'pending' } })
const workbench = ref({ pending_count: 0, items: [] }),
  context = ref(null),
  summary = ref(null),
  studentId = ref(''),
  comment = ref(''),
  commentError = ref(''),
  commentInput = ref(null),
  error = ref(''),
  loading = ref(true),
  reviewing = ref(false)
const canReview = computed(() =>
  Boolean(context.value?.allowed_actions?.some((action) => ['approve', 'return'].includes(action)))
)
const ocrConfirmed = ref(false)
const needsOcrConfirmation = computed(
  () => context.value?.ocr_assessment?.review_mode === 'manual_confirmation'
)
const historyMode = computed(() => props.mode === 'history')
const displayItems = computed(() =>
  historyMode.value ? workbench.value.reviewed_items || [] : workbench.value.items || []
)
async function load() {
  loading.value = true
  error.value = ''
  try {
    workbench.value = await materialApi.getCompetitionWorkbenchSummary()
  } catch (e) {
    error.value = e.message || '竞赛待审材料加载失败'
  } finally {
    loading.value = false
  }
}
async function open(id) {
  ocrConfirmed.value = false
  error.value = ''
  try {
    context.value = await materialApi.getCompetitionReviewContext(id)
    comment.value = ''
    commentError.value = ''
  } catch (e) {
    error.value = e.message || '材料详情加载失败'
  }
}
async function review(decision) {
  if (decision === 'return' && !comment.value.trim()) {
    commentError.value = '退回修改时，请填写具体原因。'
    await nextTick()
    commentInput.value?.focus()
    return
  }
  if (decision === 'approve' && needsOcrConfirmation.value && !ocrConfirmed.value) {
    commentError.value = '请先人工核对并勾选确认原件、OCR结果及候选分。'
    return
  }
  reviewing.value = true
  error.value = ''
  commentError.value = ''
  try {
    await materialApi.reviewCompetition(
      context.value.record_id,
      context.value.material_version,
      decision,
      comment.value,
      crypto.randomUUID(),
      needsOcrConfirmation.value ? ocrConfirmed.value : undefined
    )
    context.value = null
    await load()
    if (summary.value) await loadSummary()
  } catch (e) {
    error.value = e.message || '审核操作失败'
  } finally {
    reviewing.value = false
  }
}
async function loadSummary() {
  try {
    summary.value = await materialApi.getTeacherCompetitionSummary(
      studentId.value,
      workbench.value.cycle_code
    )
  } catch (e) {
    error.value = e.message || '学生汇总加载失败'
  }
}
onMounted(load)
</script>
<style scoped>
.review-outcome {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: baseline;
  font-size: 0.85rem;
}
.review-opinion {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  opacity: 0.85;
}
.ocr-confirmation {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  background: #fff8e8;
  border-radius: 8px;
  line-height: 1.7;
}
.ocr-confirmation input {
  margin-top: 6px;
}

.competition-review {
  display: grid;
  gap: 18px;
  margin-bottom: 24px;
}
.review-hero,
.summary-card,
.pending-card,
.dialog-shell {
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
}
.review-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px;
  background: linear-gradient(135deg, #f8fbff, #edf6ff);
}
.review-hero h2,
.review-hero p,
.pending-card h3,
.pending-card p {
  margin: 0;
}
.eyebrow {
  color: #0b5cab;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.pending-total {
  display: grid;
  place-items: center;
  min-width: 120px;
  padding: 14px;
  border-radius: 10px;
  background: #fff;
}
.pending-total strong {
  font-size: 32px;
  color: #0b5cab;
}
.pending-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.pending-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px;
}
.pending-card div {
  display: grid;
  gap: 6px;
}
.status-badge {
  width: max-content;
  padding: 4px 8px;
  border-radius: 999px;
  background: #fff2d3;
  color: #805500;
  font-size: 12px;
}
.review-state {
  display: flex;
  justify-content: space-between;
  padding: 18px;
  border: 1px dashed #aebed0;
  border-radius: 10px;
  background: #f8fafc;
}
.review-state.error {
  border-color: #d99;
  background: #fff6f6;
}
.summary-card {
  display: grid;
  gap: 16px;
  padding: 20px;
}
.summary-card h3,
.summary-card p {
  margin: 0;
}
.summary-search {
  display: flex;
  align-items: end;
  gap: 10px;
}
.summary-search label {
  display: grid;
  gap: 6px;
}
.form-control,
textarea {
  min-height: 40px;
  padding: 9px 11px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
.summary-card table {
  width: 100%;
  border-collapse: collapse;
}
.summary-card th,
.summary-card td {
  padding: 10px;
  border-top: 1px solid #e4ebf3;
  text-align: left;
}
.review-dialog {
  position: fixed;
  inset: 5vh auto auto 50%;
  width: min(900px, 92vw);
  max-height: 90vh;
  padding: 0;
  border: 0;
  background: transparent;
  transform: translateX(-50%);
  z-index: 30;
}
.review-dialog::backdrop {
  background: rgba(17, 32, 51, 0.45);
}
.dialog-shell {
  display: grid;
  gap: 18px;
  padding: 24px;
  overflow: auto;
  max-height: 90vh;
  box-shadow: 0 18px 60px rgba(13, 34, 57, 0.25);
}
.dialog-shell > header,
.dialog-shell > footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.detail-grid section {
  min-width: 0;
  padding: 14px;
  border-radius: 8px;
  background: #f7f9fc;
}
.detail-grid pre {
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
}
.evidence-panel {
  display: grid;
  align-content: start;
  gap: 10px;
}
.evidence-file {
  display: grid;
  gap: 8px;
  margin: 0;
}
.evidence-file img {
  display: block;
  width: 100%;
  max-height: 360px;
  object-fit: contain;
  border: 1px solid #d7e1ec;
  border-radius: 7px;
  background: #fff;
}
.evidence-file figcaption {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  overflow-wrap: anywhere;
}
.comment-field {
  display: grid;
  gap: 7px;
  font-weight: 600;
}
.comment-field textarea {
  min-height: 90px;
}
.btn {
  min-height: 40px;
  padding: 9px 16px;
  border: 1px solid transparent;
  border-radius: 7px;
  font-weight: 600;
}
.btn-primary {
  background: #0b5cab;
  color: #fff;
}
.btn-outline {
  border-color: #9bb1ca;
  background: #fff;
  color: #174b7d;
}
.btn:disabled {
  opacity: 0.55;
}
@media (max-width: 700px) {
  .review-hero,
  .pending-card,
  .summary-search {
    align-items: stretch;
    flex-direction: column;
  }
  .pending-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
  .pending-total {
    min-width: 0;
  }
  .summary-card {
    overflow: auto;
  }
}
</style>
