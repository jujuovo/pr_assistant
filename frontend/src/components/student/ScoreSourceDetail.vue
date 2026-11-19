<template>
  <Teleport to="body"
    ><div class="score-source-overlay" @click.self="emit('close')"
      ><section
        class="score-source-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="score-source-title"
        @keydown="onKeydown"
      >
        <header class="source-dialog-heading"
          ><div
            ><p>计分项目详情</p><h2 id="score-source-title">{{ row.title }}</h2></div
          ><button ref="closeButton" type="button" class="source-close" @click="emit('close')"
            >关闭详情</button
          ></header
        >
        <div class="source-dialog-body">
          <section class="source-score-summary" aria-label="该项目计分情况"
            ><div
              ><span>候选分</span><strong>{{ row.candidateScore ?? '—' }}</strong></div
            ><div
              ><span>计入分</span><strong>{{ row.includedScore ?? '0' }}</strong></div
            ><div
              ><span>计入状态</span
              ><b>{{ row.included ? '已计入' : row.reason || '未计入' }}</b></div
            ><p>{{ row.ruleLabel }}</p></section
          >
          <p v-if="loading" class="source-state" role="status">正在加载项目申报信息与原件…</p>
          <section v-else-if="error" class="source-state source-error" role="alert"
            ><p>{{ error }}</p
            ><button type="button" class="source-retry" @click="load">重新加载</button></section
          >
          <template v-else-if="detail">
            <section class="source-section"
              ><div class="source-section-heading"
                ><h3>申报信息</h3><span>{{ scoreStatusText(detail.status) }}</span></div
              ><MaterialFacts :data="detail.data"
            /></section>
            <section class="source-section"
              ><h3>证明原件</h3
              ><p v-if="!detail.attachments?.length" class="source-empty"
                >此项目暂无可预览的附件。</p
              ><MaterialImagePreview :attachments="images" /><ul
                v-if="documents.length"
                class="source-documents"
                ><li v-for="file in documents" :key="file.id"
                  ><a :href="file.url" target="_blank" rel="noopener"
                    >查看文件：{{ file.filename }}</a
                  ></li
                ></ul
              ></section
            >
            <details v-if="detail.ocr_raw_terms" class="source-ocr"
              ><summary>OCR识别结果</summary
              ><MaterialFacts
                :data="detail.ocr_raw_terms.report?.fields || detail.ocr_raw_terms.fields || {}"
            /></details>
            <section class="source-section"
              ><h3>审核与材料记录</h3
              ><p v-if="!detail.history?.length" class="source-empty">暂无审核记录。</p
              ><ol v-else class="source-history"
                ><li v-for="event in detail.history" :key="event.id"
                  ><div
                    ><strong>{{ eventLabel(event.action) }}</strong
                    ><time>{{ formatScoreTime(event.created_at) }}</time></div
                  ><p v-if="event.comment">{{ event.comment }}</p></li
                ></ol
              ></section
            >
          </template></div
        ></section
      ></div
    ></Teleport
  >
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import workflowApi from '@/services/workflowApi.js'
import { lockBodyScroll } from '@/services/bodyScrollLock.js'
import { formatScoreTime, scoreStatusText } from '@/services/scorePresentation.js'
import MaterialFacts from '@/components/common/MaterialFacts.vue'
import MaterialImagePreview from '@/components/common/MaterialImagePreview.vue'
const props = defineProps({
    row: { type: Object, required: true },
    studentId: { type: String, required: true },
    year: { type: Number, required: true }
  }),
  emit = defineEmits(['close'])
const detail = ref(null),
  loading = ref(true),
  error = ref(''),
  closeButton = ref(null)
const images = computed(() =>
  (detail.value?.attachments || []).filter(
    (file) => file.url && /\.(png|jpe?g|webp|bmp|tiff?)$/i.test(file.filename)
  )
)
const documents = computed(() =>
  (detail.value?.attachments || []).filter(
    (file) => file.url && !/\.(png|jpe?g|webp|bmp|tiff?)$/i.test(file.filename)
  )
)
const eventLabel = (action) =>
  ({
    created: '建立草稿',
    edited: '更新申报信息',
    attachments_added: '上传证明原件',
    submitted: '提交审核',
    withdrawn: '撤回材料',
    reviewed: '完成核验',
    competition_approved: '审核通过并计分',
    competition_returned: '退回修改',
    competition_ocr_started: '后台OCR入队',
    competition_ocr_cancelled: '取消OCR',
    ocr_confirmed: '核对识别结果',
    correction_created: '建立补正材料',
    approved: '审核通过',
    rejected: '审核未通过',
    needs_correction: '退回补充'
  })[action] || '材料状态更新'
let controller = null,
  alive = true,
  releaseScroll = null
async function load() {
  controller?.abort()
  const requestController = new AbortController()
  controller = requestController
  loading.value = true
  error.value = ''
  try {
    const result = await workflowApi.getScoreSource(
      props.studentId,
      props.year,
      props.row.sourceType,
      props.row.sourceId,
      requestController.signal
    )
    if (alive && controller === requestController) detail.value = result
  } catch (e) {
    if (alive && controller === requestController && e.name !== 'AbortError')
      error.value =
        e.status === 403
          ? '没有访问此项目详情的权限，请确认当前账号。'
          : e.status === 404
            ? '项目原记录暂不可用，请刷新加分统计后重试。'
            : e.message || '详情加载失败，请重新加载。'
  } finally {
    if (alive && controller === requestController) loading.value = false
  }
}
function onKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    emit('close')
    return
  }
  if (event.key !== 'Tab') return
  const controls = Array.from(
    event.currentTarget.querySelectorAll('button,a[href],summary')
  ).filter(
    (el) =>
      !el.disabled &&
      (!el.closest('details') || el.closest('details').open || el.tagName === 'SUMMARY')
  )
  const first = controls[0],
    last = controls.at(-1)
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}
onMounted(async () => {
  releaseScroll = lockBodyScroll()
  await nextTick()
  if (alive) {
    closeButton.value?.focus()
    load()
  }
})
onBeforeUnmount(() => {
  alive = false
  controller?.abort()
  releaseScroll?.()
})
</script>
<style scoped>
.score-source-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(20, 36, 57, 0.46);
  font-family: Inter, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #20334b;
  font-size: 14px;
  line-height: 1.65;
}
.score-source-dialog {
  width: min(880px, 100%);
  max-height: 90vh;
  max-height: 90dvh;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 24px 80px rgba(20, 40, 70, 0.24);
  overflow: hidden;
}
.source-dialog-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 28px;
  border-bottom: 1px solid #e6edf6;
  background: #f7fbff;
}
.source-dialog-heading p {
  margin: 0 0 4px;
  color: #76869d;
  font-size: 12px;
}
.source-dialog-heading h2 {
  margin: 0;
  font-size: 21px;
  font-weight: 650;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.source-close,
.source-retry {
  min-height: 40px;
  padding: 8px 14px;
  border: 1px solid #c8d9ed;
  border-radius: 7px;
  background: #fff;
  color: #145d9e;
  white-space: nowrap;
  cursor: pointer;
}
.source-dialog-body {
  padding: 24px 28px;
  overflow-y: auto;
  display: grid;
  gap: 24px;
}
.source-score-summary {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr;
  gap: 12px 24px;
  padding: 18px 22px;
  background: #eef6ff;
  border: 1px solid #dceafb;
  border-radius: 10px;
}
.source-score-summary > div {
  display: grid;
  gap: 5px;
}
.source-score-summary span {
  font-size: 12px;
  color: #6c819a;
}
.source-score-summary strong {
  font-size: 25px;
  font-weight: 650;
  color: #115ea8;
  font-variant-numeric: tabular-nums;
}
.source-score-summary b {
  font-weight: 500;
  color: #335879;
  overflow-wrap: anywhere;
}
.source-score-summary > p {
  grid-column: 1/-1;
  margin: 0;
  padding-top: 10px;
  border-top: 1px solid #d6e4f3;
  font-size: 12px;
  color: #607895;
}
.source-section h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.source-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}
.source-section-heading > span {
  font-size: 12px;
  color: #4e739a;
}
.source-state {
  padding: 18px;
  border-radius: 8px;
  background: #f6f9fd;
  color: #6b7f99;
}
.source-state p {
  margin: 0 0 12px;
}
.source-error {
  background: #fff7f4;
  color: #9c5946;
}
.source-empty {
  margin: 12px 0 0;
  color: #7b899c;
  font-size: 13px;
}
.source-documents {
  padding-left: 20px;
  margin: 12px 0 0;
}
.source-documents a {
  color: #155fa8;
}
.source-ocr {
  border-top: 1px solid #e8edf5;
  border-bottom: 1px solid #e8edf5;
  padding: 12px 0;
}
.source-ocr summary {
  color: #4d6889;
  cursor: pointer;
  font-size: 13px;
}
.source-history {
  list-style: none;
  padding: 0;
  margin: 16px 0 0;
  display: grid;
  gap: 0;
}
.source-history li {
  padding: 0 0 18px 18px;
  border-left: 2px solid #dce8f7;
  position: relative;
}
.source-history li:last-child {
  padding-bottom: 0;
}
.source-history li:before {
  content: '';
  width: 8px;
  height: 8px;
  position: absolute;
  left: -5px;
  top: 7px;
  border-radius: 50%;
  background: #6296cf;
}
.source-history li > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.source-history strong {
  font-weight: 500;
  font-size: 13px;
}
.source-history time {
  font-size: 12px;
  color: #8190a3;
  font-variant-numeric: tabular-nums;
}
.source-history p {
  margin: 5px 0 0;
  color: #6c7d94;
  font-size: 13px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .score-source-overlay {
    padding: 12px;
  }
  .source-dialog-heading {
    padding: 18px;
  }
  .source-dialog-heading h2 {
    font-size: 18px;
  }
  .source-dialog-body {
    padding: 18px;
    gap: 22px;
  }
  .source-score-summary {
    grid-template-columns: 1fr 1fr;
    padding: 16px;
    gap: 12px;
  }
  .source-score-summary > div:last-of-type {
    grid-column: 1/-1;
  }
  .source-history li > div {
    flex-direction: column;
    gap: 3px;
  }
  .source-close {
    padding: 7px 10px;
  }
}
</style>
