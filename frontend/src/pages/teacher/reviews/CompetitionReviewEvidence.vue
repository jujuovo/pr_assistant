<template>
  <p v-if="loading" role="status">正在加载材料详情…</p>
  <div v-else-if="loadError" role="alert">
    {{ loadError }}
    <button class="btn btn-outline" type="button" @click="load">重新加载</button>
  </div>
  <div v-if="context" class="competition-evidence">
    <ReviewEvidenceLayout :attachments="context.attachments">
      <template #attachments>
        <p v-if="!context.attachments.length">未提供附件</p>
        <ul v-else class="attachment-downloads">
          <li v-for="file in context.attachments" :key="file.id">
            <a
              :href="file.url"
              target="_blank"
              rel="noopener"
              :aria-label="'下载原件：' + file.filename"
              >下载原件</a
            >
          </li>
        </ul>
      </template>
      <MaterialReviewComparison
        :declared="context.confirmed_terms"
        :recognized="recognizedFields"
        :differences="context.ocr_assessment?.differences || []"
      />
    </ReviewEvidenceLayout>
    <details class="competition-review-details" :open="readOnly || undefined">
      <summary>计分依据与 OCR 详情</summary>
      <details v-if="context.ocr_raw_terms">
        <summary>OCR 原文（仅辅助）</summary>
        <MaterialFacts
          :data="
            context.ocr_raw_terms?.report?.fields ||
            context.ocr_raw_terms?.fields ||
            context.ocr_raw_terms
          "
        />
      </details>
      <section class="rule-basis">
        <h4>固定规则依据</h4>
        <p>{{ context.rule_basis.competition_name }} / {{ context.rule_basis.category }}</p>
        <p
          >规则包 v{{ context.rule_basis.package_version }} · 后端候选分
          {{ context.candidate_score }}</p
        ></section
      >
      <OcrAssessment :advice="context.ocr_assessment" />
      <section class="summary-card history-panel"
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
    </details>
    <label v-if="canReview && needsOcrConfirmation" class="ocr-confirmation">
      <input v-model="ocrConfirmed" type="checkbox" />
      我已人工核对原件、OCR差异或缺失依据，确认申报事实及候选分。
    </label>
    <p v-if="reviewError" class="field-error" role="alert">{{ reviewError }}</p>
    <ReviewCommentForm
      v-if="canReview"
      ref="commentInput"
      v-model="comment"
      :comment-id="commentId"
      :error="commentError"
    >
      <button
        v-if="context.allowed_actions.includes('approve')"
        class="btn btn-outline"
        type="button"
        :disabled="reviewing"
        @click="review('approve')"
        >核验通过</button
      >
      <button
        v-if="context.allowed_actions.includes('return')"
        class="btn btn-outline"
        type="button"
        :disabled="reviewing"
        @click="review('return')"
        >退回补充</button
      >
    </ReviewCommentForm>
    <p v-else class="review-state">该材料当前不可处理，页面保持只读。</p>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import materialApi from '@/services/materialApi.js'
import { formatScoreTime, materialEventText } from '@/services/scorePresentation.js'
import MaterialFacts from '@/components/common/MaterialFacts.vue'
import ReviewCommentForm from '@/components/teacher/ReviewCommentForm.vue'
import ReviewEvidenceLayout from '@/components/teacher/ReviewEvidenceLayout.vue'
import MaterialReviewComparison from '@/components/teacher/MaterialReviewComparison.vue'
import OcrAssessment from '@/components/common/OcrAssessment.vue'

const props = defineProps({
  recordId: { type: Number, required: true },
  readOnly: Boolean
})
const emit = defineEmits(['reviewed'])
const context = ref(null)
const comment = ref('')
const commentError = ref('')
const commentInput = ref(null)
const ocrConfirmed = ref(false)
const loading = ref(false)
const loadError = ref('')
const reviewError = ref('')
const reviewing = ref(false)
const commentId = computed(() => `review-comment-${props.recordId}`)
const canReview = computed(
  () =>
    !props.readOnly &&
    Boolean(
      context.value?.allowed_actions?.some((action) => ['approve', 'return'].includes(action))
    )
)
const needsOcrConfirmation = computed(
  () => context.value?.ocr_assessment?.review_mode === 'manual_confirmation'
)
const recognizedFields = computed(() => {
  const raw = context.value?.ocr_raw_terms
  return raw?.report?.fields || raw?.fields || {}
})

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    context.value = await materialApi.getCompetitionReviewContext(props.recordId)
  } catch (cause) {
    loadError.value = cause.message || '材料详情加载失败'
  } finally {
    loading.value = false
  }
}

async function review(decision) {
  if (reviewing.value || !canReview.value || !context.value.allowed_actions.includes(decision))
    return
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
  reviewError.value = ''
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
    context.value = { ...context.value, allowed_actions: [] }
    emit('reviewed')
  } catch (e) {
    reviewError.value = e.message || '审核操作失败'
  } finally {
    reviewing.value = false
  }
}
watch(() => props.recordId, load, { immediate: true })
</script>

<style scoped>
.competition-evidence {
  min-width: 0;
}
.competition-review-details {
  margin: 8px 0;
}
.ocr-confirmation {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 8px;
}
.field-error {
  color: #a12626;
}
.attachment-downloads {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}
</style>
