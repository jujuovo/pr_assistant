<template>
  <section class="certificate-report card compact-card">
    <div class="card-title">证书识别辅助</div>
    <p v-if="loading">正在读取识别状态…</p>
    <p v-if="error" class="warning">{{ error }} <button type="button" @click="load">重新读取</button></p>
    <template v-if="result">
      <p>{{ labels[result.status] || result.status }}</p>
      <p class="note" v-if="['queued','processing'].includes(result.status)">后台正在处理，结果会自动更新。可继续查看申请与原件。</p>
      <p class="note" v-else-if="result.project === 'manual'">该项目完全通过人工核验，不计算自动判断置信度。</p>
      <template v-else>
        <p class="note">识别结果仅用于核对。水印匹配不代表真实，处理图仅用于 OCR；请结合原件及官方记录审核。</p>
        <p class="warning" v-if="result.error">{{ result.error }}</p>
        <p v-if="result.report?.message" class="note">{{ result.report.message }}</p>
        <article v-for="(page, index) in result.report?.pages || []" :key="index" class="page-result">
          <strong>{{ page.filename }}<span v-if="page.page"> · 第{{ page.page }}页</span></strong>
          <p>{{ labels[page.status] || page.status }} · {{ page.message }}</p>
          <p v-if="page.watermark">水印检查：{{ watermarkLabels[page.watermark.watermark_status || page.watermark.status] || '待人工核对' }}</p>
          <p class="warning" v-if="page.quality && !page.quality.acceptable">{{ page.quality.reason }}。请通过编辑申请替换材料。</p>
          <table v-if="page.raw_fields">
            <thead><tr><th>字段</th><th>原图识别</th><th>处理图识别</th></tr></thead>
            <tbody><tr v-for="(label, key) in fields" :key="key" :class="{ difference: differs(page,key) }">
              <th>{{ label }}</th><td>{{ page.raw_fields[key] || '未识别' }}</td><td>{{ page.processed_fields?.[key] || '未识别' }}</td>
            </tr></tbody>
          </table>
          <ul v-if="page.warnings?.length"><li v-for="(warning, i) in page.warnings" :key="i" class="warning">{{ warning.message }}</li></ul>
          <details v-if="page.artifacts?.original || page.artifacts?.processed">
            <summary>查看原图与 OCR 辅助图</summary>
            <div class="images">
              <figure v-if="page.artifacts.original"><img :src="url(page.artifacts.original)" alt="保留原图"><figcaption>原图（审核依据）</figcaption></figure>
              <figure v-if="page.artifacts.processed"><img :src="url(page.artifacts.processed)" alt="ZigZag处理图"><figcaption>处理图（OCR 辅助）</figcaption></figure>
            </div>
          </details>
          <a v-if="page.artifacts?.source" :href="url(page.artifacts.source)" target="_blank" rel="noopener">查看上传原件</a>
        </article>
        <button type="button" v-if="!['queued','processing'].includes(result.status) && ['draft','pending'].includes(applicationStatus)" :disabled="retrying" @click="retry">{{ retrying ? '正在排队…' : '重新识别' }}</button>
      </template>
    </template>
  </section>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import api from '../../utils/api'
const props = defineProps({ applicationId: { type: [Number, String], required: true }, applicationStatus: String })
const result = ref(null), error = ref(''), loading = ref(false), retrying = ref(false)
let timer, generation = 0, disposed = false
const labels = { queued: '等待识别', processing: '识别中', manual: '人工核验通道', manual_review: '需要人工核对', recognized: '识别完成，等待教师核验', needs_reupload: '请补充清晰材料', failed: '识别失败，可重试或人工核验' }
const watermarkLabels = { matched: '蓝桥杯文字匹配', missing: '未发现预期水印', mismatched: '水印文字不匹配', uncertain: '无法可靠确定' }
const fields = { school: '学校', student: '姓名', teacher: '指导教师', edition: '届次', track: '赛道', group: '组别', region: '赛区', award: '奖项', certificate_no: '证书编号', date: '日期' }
const differs = (page, key) => page.differences?.some(d => d.field === key) || page.warnings?.some(w => w.field === key)
const url = (path) => `/api/certificates/applications/${props.applicationId}/artifacts/${result.value.version}/${path.split('/').map(encodeURIComponent).join('/')}`
async function load() {
  clearTimeout(timer)
  const current = generation
  loading.value = !result.value
  error.value = ''
  if (import.meta.env.MODE === 'demo') { loading.value = false; result.value = { status:'manual', project:'manual' }; return }
  try {
    const response = await api.apiRequest(`/certificates/applications/${props.applicationId}`)
    if (disposed || current !== generation) return
    result.value = response
    if (['queued','processing'].includes(response.status)) timer = setTimeout(load, 2500)
  } catch (e) { if (!disposed && current === generation) error.value = e.message }
  finally { if (!disposed && current === generation) loading.value = false }
}
async function retry() {
  retrying.value = true
  try { await api.apiRequest(`/certificates/applications/${props.applicationId}/retry`, 'POST', { version:result.value.version }); await load() }
  catch (e) { error.value = e.message }
  finally { retrying.value = false }
}
watch(() => props.applicationId, () => { generation++; result.value = null; load() }, { immediate: true })
onBeforeUnmount(() => { disposed = true; generation++; clearTimeout(timer) })
</script>

<style scoped>
.certificate-report { font-size: 13px; line-height: 1.6; }
.note { color:#65748a; }.warning { color:#9a540b; }.page-result { border-top:1px solid #e4e9f0; margin-top:12px; padding-top:12px; }
table { width:100%; border-collapse:collapse; font-size:12px; } th,td { text-align:left; padding:6px; border-bottom:1px solid #edf0f5; word-break:break-word; } .difference { background:#fff4db; }
.images { display:grid; grid-template-columns:1fr 1fr; gap:8px; } figure { margin:6px 0; } img { width:100%; height:auto; } figcaption { text-align:center; color:#65748a; }
button { padding:6px 12px; border:1px solid #cbd5e1; border-radius:6px; background:#fff; cursor:pointer; margin-top:8px; }
</style>
