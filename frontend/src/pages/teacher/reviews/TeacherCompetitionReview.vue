<template>
  <section class="competition-review" :aria-labelledby="historyMode ? 'competition-review-title' : undefined">
    <header v-if="historyMode" class="review-hero">
      <h2 id="competition-review-title">竞赛审核记录</h2>
    </header>
    <p v-if="loading && (historyMode || !displayItems.length)" class="review-state" role="status">正在加载竞赛待审材料…</p>
    <section v-else-if="error && !displayItems.length" class="review-state error" role="alert"
      ><p>{{ error }}</p
      ><button class="btn btn-outline" @click="load">重新加载</button></section
    >
    <p v-else-if="!displayItems.length" class="review-state review-category-empty" role="status">{{
      !historyMode
        ? '当前类别暂无待核验材料。'
        : keyword ? '暂无匹配的竞赛审核记录。' : '当前类别暂无核验记录。'
    }}</p>
    <div v-else :class="historyMode ? 'pending-grid' : 'material-review-list'"
      ><article v-for="row in displayItems" :key="row.id" class="pending-card" :class="{ 'material-review-card': !historyMode }"
        ><div v-if="historyMode"
          ><ReviewStatusBadge :status="row.status" />
          <h3>{{ row.project_name || row.competition_name }}</h3
          ><p>学生 {{ row.student_id }} · 版本 {{ row.version }}</p
          ><p v-if="historyMode && row.review" class="review-outcome"
            ><strong>{{ reviewDecisionText(row.review.decision) }}</strong
            ><span
              >· {{ row.review.actor?.name || '未知审核人' }}（{{
                ({admin: '管理员', teacher: '教师', reviewer_level1: '一级审核员', reviewer_level2: '二级审核员'}[row.review.actor?.role] || '审核人')
              }}）</span
            ><time>· {{ formatScoreTime(row.review.at) }}</time></p
          ><p v-if="historyMode && row.review?.comment" class="review-opinion"
            >审核意见：{{ row.review.comment }}</p
          ><p v-if="historyMode && row.superseded_by_record_id" class="review-opinion"
            >该记录已被新版本（#{{ row.superseded_by_record_id }}）取代，以新版本结果为准。</p
          ><p v-if="historyMode && !row.review" class="review-opinion"
            >未找到审核结论记录，请打开记录查看历史。</p
          ></div
        ><h3 v-else>学生 {{ row.student_id }} · 材料 #{{ row.id }}</h3>
        <button v-if="historyMode" class="btn btn-primary" type="button" @click="open(row.id)">
          查看记录
        </button>
        <CompetitionReviewEvidence v-else-if="detailsActive" :key="row.version"
          :record-id="row.id" @reviewed="load" />
      </article
      ></div
    >
    <p v-if="error && displayItems.length" class="review-state error" role="alert">{{ error }}
      <button class="btn btn-outline" type="button" @click="load">重新加载</button>
    </p>
    <button v-if="nextCursor" class="btn btn-outline" type="button" data-test="load-more-competition"
      :disabled="loadingMore || loading" @click="loadMore">
      {{ loadingMore ? '正在加载…' : historyMode ? '加载更多审核记录' : '加载更多待审材料' }}
    </button>
    <dialog v-if="historyRecordId" open class="review-dialog" aria-labelledby="review-dialog-title">
      <div class="dialog-shell">
        <header>
          <h3 id="review-dialog-title">竞赛材料 #{{ historyRecordId }}</h3>
          <button class="btn btn-outline" type="button" @click="historyRecordId = null">关闭</button>
        </header>
        <CompetitionReviewEvidence :key="historyRecordId" :record-id="historyRecordId" read-only />
      </div>
    </dialog>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import ReviewStatusBadge from '@/components/teacher/ReviewStatusBadge.vue'
import materialApi from '@/services/materialApi.js'
import {
  formatScoreTime,
  reviewDecisionText
} from '@/services/scorePresentation.js'
import CompetitionReviewEvidence from './CompetitionReviewEvidence.vue'
const emit = defineEmits(['pending-count'])
const props = defineProps({
  mode: { type: String, default: 'pending' },
  keyword: String,
  detailsActive: { type: Boolean, default: true }
})
const workbench = ref({ pending_count: 0, items: [] })
const historyRecordId = ref(null)
const error = ref('')
const loading = ref(true)
const historyMode = computed(() => props.mode === 'history')
const loadingMore = ref(false)
const nextCursor = computed(() => historyMode.value
  ? workbench.value.reviewed_next_before_id : workbench.value.next_before_id)
const displayItems = computed(() => {
  if (!historyMode.value) return workbench.value.items || []
  return workbench.value.reviewed_items || []
})
let loadVersion = 0
async function load() {
  const version = ++loadVersion
  loading.value = true
  loadingMore.value = false
  error.value = ''
  try {
    const result = await materialApi.getCompetitionWorkbenchSummary(undefined, undefined, {
      keyword: historyMode.value ? props.keyword : undefined
    })
    if (version !== loadVersion) return
    workbench.value = result
    emit('pending-count', historyMode.value ? displayItems.value.length : workbench.value.pending_count)
  } catch (cause) {
    if (version !== loadVersion) return
    emit('pending-count', null)
    error.value = cause.message || '竞赛待审材料加载失败'
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
async function loadMore() {
  if (loadingMore.value || !nextCursor.value) return
  const version = loadVersion
  const history = historyMode.value
  loadingMore.value = true
  error.value = ''
  try {
    const options = history ? { reviewedBeforeId: nextCursor.value } : { beforeId: nextCursor.value }
    if (history && props.keyword) options.keyword = props.keyword
    const result = await materialApi.getCompetitionWorkbenchSummary(undefined, undefined, options)
    if (version !== loadVersion) return
    const key = history ? 'reviewed_items' : 'items'
    const existing = workbench.value[key] || []
    const known = new Set(existing.map(row => row.id))
    workbench.value = { ...workbench.value,
      [key]: [...existing, ...(result[key] || []).filter(row => !known.has(row.id))],
      [history ? 'reviewed_next_before_id' : 'next_before_id']:
        result[history ? 'reviewed_next_before_id' : 'next_before_id'] }
  } catch (cause) {
    if (version === loadVersion) error.value = cause.message || '加载失败，请重试加载更多。'
  } finally {
    if (version === loadVersion) loadingMore.value = false
  }
}
function open(id) {
  historyRecordId.value = id
}
watch([() => props.keyword, () => props.mode], load, { immediate: true })
</script>
<style scoped>
@import '@/assets/styles/pages/teacher/reviews/MaterialReviewCard.css';
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

}
.review-hero,
.summary-card,
.pending-grid > .pending-card,
.dialog-shell {
  border: 1px solid #dce5ef;
  border-radius: var(--system-radius);
  background: #fff;
}
.review-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px;
  background: var(--system-surface);
}
.review-hero h2 { font-size: 22px; color: var(--system-ink-blue); }
.review-hero h2,
.review-hero p,
.pending-grid h3,
.pending-grid p {
  margin: 0;
}
.eyebrow {
  color: #0b5cab;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.pending-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.material-review-list {
  display: grid;
  gap: 14px;
}
.pending-grid > .pending-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px;
}
.pending-grid > .pending-card > div:first-child {
  display: grid;
  gap: 6px;
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
  .pending-grid > .pending-card {
    align-items: stretch;
    flex-direction: column;
  }
  .pending-grid {
    grid-template-columns: 1fr;
  }
  .summary-card {
    overflow: auto;
  }
}
</style>
