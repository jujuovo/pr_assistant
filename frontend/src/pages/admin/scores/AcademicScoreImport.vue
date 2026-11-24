<template>
  <div class="academic-import">
    <p class="import-help" id="academic-import-help">
      支持 .xlsx。按学号匹配本学院学生，空白成绩会跳过并保留现有成绩。
    </p>
    <form class="import-actions" @submit.prevent="preview">
      <label class="import-file">
        选择 Excel 文件
        <input class="form-control" type="file" accept=".xlsx" :disabled="busy"
          aria-describedby="academic-import-help" @change="selectFile" />
      </label>
      <div class="import-buttons">
        <button class="btn" type="submit" :disabled="!file || busy">预览</button>
        <a class="btn btn-outline import-download" :href="exampleFile"
          download="学业成绩导入示例.xlsx">下载示例</a>
        <button class="btn btn-outline" type="button" :disabled="busy" @click="$emit('close')">
          关闭
        </button>
      </div>
    </form>
    <p v-if="busy" role="status" class="import-feedback status-pending">正在处理文件…</p>
    <p v-if="error" role="alert" class="import-feedback status-rejected">{{ error }}</p>
    <p v-if="result" role="status" class="import-feedback status-approved">
      已导入 {{ result.imported_count }} 条，跳过 {{ result.skipped_count }} 条。
    </p>
    <template v-if="plan">
      <p v-if="!result" role="status">可导入 {{ plan.ready_count }} 条，共 {{ plan.rows.length }} 条。</p>
      <div class="table-container preview-table" tabindex="0" role="region" aria-label="导入预览，可横向滚动">
        <table class="application-table" aria-label="学业成绩导入预览">
          <thead>
            <tr><th scope="col">行号</th><th scope="col">学号</th><th scope="col">姓名</th>
              <th scope="col">当前成绩</th><th scope="col">文件成绩</th><th scope="col">处理结果</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in plan.rows" :key="row.line">
              <td>{{ row.line }}</td><td>{{ row.student_id || '未提供' }}</td>
              <td>{{ row.name || '未提供' }}</td><td>{{ row.previous ?? '未录入' }}</td>
              <td>{{ row.score ?? '—' }}</td>
              <td>
                <span class="status-badge" :class="row.issues.length ? 'status-pending' : 'status-approved'">
                  {{ row.issues.length ? '跳过' : result ? '已导入' : '可导入' }}
                </span>
                <span v-if="row.issues.length" class="import-reason">{{ row.issues.join('、') }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <button v-if="!result" class="btn btn-primary" type="button" :disabled="busy || !plan.ready_count"
        @click="confirm">确认导入</button>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '@/services/api.js'
import exampleFile from '@/assets/academic-score-import-example.xlsx?url'

const emit = defineEmits(['close', 'imported'])
const file = ref(null)
const plan = ref(null)
const result = ref(null)
const error = ref('')
const busy = ref(false)

function selectFile(event) {
  file.value = event.target.files[0] || null
  plan.value = null
  result.value = null
  error.value = ''
}

async function preview() {
  if (!file.value || busy.value) return
  plan.value = null
  result.value = null
  error.value = ''
  busy.value = true
  try {
    plan.value = await api.importAcademicScores(file.value)
  } catch (cause) {
    error.value = cause.message || '无法预览文件'
  } finally {
    busy.value = false
  }
}

async function confirm() {
  if (busy.value || result.value || !plan.value?.ready_count) return
  busy.value = true
  error.value = ''
  try {
    result.value = await api.importAcademicScores(file.value, plan.value.token)
    emit('imported')
  } catch (cause) {
    if (cause.code === 'stale_preview') plan.value = null
    error.value = cause.message || '导入失败'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
@import '@/assets/styles/shared/content.css';

.import-help { margin: 0 0 12px; }
.import-actions { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.import-file { display: grid; gap: 6px; min-width: 0; max-width: 100%; font-weight: 600; }
.import-file input { width: 100%; min-width: 0; box-sizing: border-box; }
.import-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
.import-download { text-decoration: none; }
.import-feedback { padding: 10px 12px; border-radius: 6px; }
.preview-table { overflow: auto; max-height: 360px; margin-bottom: 14px; }
.application-table { min-width: 40rem; }
.import-reason { display: block; margin-top: 6px; }
</style>
