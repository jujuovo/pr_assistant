<template>
  <dialog ref="dialog" class="ranking-dialog">
    <form @submit.prevent="download">
      <h2>导出排名名单</h2>
      <label>导出用途
        <textarea v-model.trim="purpose" class="form-control" required maxlength="500" />
      </label>
      <p v-if="error" role="alert">{{ error }}</p>
      <button type="button" class="btn btn-outline" :disabled="busy" @click="dialog.close()">取消</button>
      <button class="btn btn-primary" :disabled="busy || !purpose">导出 CSV</button>
    </form>
  </dialog>
</template>

<script setup>
import { ref } from 'vue'
import workflowApi from '@/services/workflowApi.js'
import { workflowErrorMessage } from '@/services/workflowPresentation.js'

const dialog = ref(null)
const purpose = ref('')
const error = ref('')
const busy = ref(false)
let batchId

function open(ranking) {
  batchId = ranking.batch_id
  purpose.value = error.value = ''
  dialog.value.showModal()
}

function csvCell(value) {
  const text = String(value ?? '')
  const safe = /^[=+\-@\t\r\n]/.test(text.trimStart()) ? "'" + text : text
  return '"' + safe.replaceAll('"', '""') + '"'
}

async function download() {
  if (busy.value || !purpose.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await workflowApi.exportRanking(batchId, purpose.value)
    const rows = [['学号', '推免综合成绩', '名次', '未纳入原因'],
      ...result.entries.map(row => [row.student_id, row.comprehensive_score, row.rank, row.reason_code])]
    const url = URL.createObjectURL(new Blob(['\uFEFF', rows.map(row => row.map(csvCell).join(',')).join('\r\n')],
      { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `排名批次-${batchId}.csv`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    dialog.value.close()
  } catch (cause) {
    error.value = workflowErrorMessage(cause)
  } finally {
    busy.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.ranking-dialog { position: fixed; inset: 0; margin: auto; padding: 1.5rem; width: min(32rem, calc(100% - 2rem)); border: 1px solid #dce5ef; border-radius: .85rem; }
.ranking-dialog::backdrop { background: rgb(10 28 48 / 45%); }
textarea { display: block; margin: .5rem 0 1rem; }
</style>
