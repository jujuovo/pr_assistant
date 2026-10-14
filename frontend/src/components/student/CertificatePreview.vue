<template>
  <section v-if="project === 'lanqiao'" class="ocr-preview" aria-live="polite">
    <h3>识别预览与申报内容</h3>
    <p v-if="busy">{{ result ? '正在识别，请稍候…' : '正在上传材料…' }}</p>
    <p v-else-if="!result && !error">选择证书图片后自动上传并识别，完成后在此核对。</p>
    <p v-if="error" role="alert">{{ error }} <button v-if="result" type="button" @click="refresh">重新查询</button></p>
    <template v-if="result && !busy">
      <p v-if="result.error">识别失败：{{ result.error }}，请重新选择清晰材料。</p>
      <p v-if="result && !result.preview_flow">这是旧流程申请。请返回申请记录查看结果；使用新流程请重新创建申请并上传材料。</p>
      <p v-if="ready">请核对以下内容。有异议可直接修改“学生申报值”，正式提交后由教师审核整份申请。原始识别结果不会被覆盖。</p>
      <article v-for="(page, index) in pages" :key="index">
        <h4>{{ page.filename }} · 第 {{ index + 1 }} 页</h4>
        <a v-if="page.artifacts?.source" :href="artifact(page.artifacts.source)" target="_blank" rel="noopener">查看上传原件</a>
        <img v-if="page.artifacts?.original" :src="artifact(page.artifacts.original)" alt="学生上传原图" class="original">
        <p>{{ page.message }}</p>
        <p v-for="(warning, i) in page.warnings || []" :key="i">{{ warning.message }}</p>
        <table v-if="values[index]">
          <thead><tr><th>字段</th><th>OCR识别值</th><th>学生申报值（可修改）</th></tr></thead>
          <tbody><tr v-for="(label, field) in fields" :key="field">
            <th>{{ label }}</th><td>{{ recognized(page, field) || '未识别' }}</td>
            <td><input v-model="values[index][field]" :aria-label="`第${index + 1}页${label}申报值`" maxlength="200" :disabled="saving || result.application_status !== 'draft'"></td>
          </tr></tbody>
        </table>
      </article>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import certificateApi from '@/services/certificateApi.js'
const props = defineProps({ files: { type: Array, default: () => [] }, project: String, existingId: [Number, String] })
const emit = defineEmits(['recognized', 'saving'])
const fields = { school:'学校', student:'姓名', teacher:'指导教师', edition:'届次', track:'赛道', group:'组别', region:'赛区', award:'奖项', certificate_no:'证书编号', date:'日期' }
const result = ref(null), values = ref([]), error = ref(''), busy = ref(false), saving = ref(false)
const pages = computed(() => result.value?.report?.pages || [])
const ready = computed(() => !busy.value && !error.value && pages.value.length > 0 && result.value?.preview_flow && result.value?.application_status === 'draft')
const recognized = (page, field) => page.processed_fields?.[field] || page.raw_fields?.[field] || ''
const artifact = path => certificateApi.getArtifactUrl(result.value.application_id, result.value.version, path)
let generation = 0, timer, controller
function stop() { generation++; clearTimeout(timer); controller?.abort() }
function apply(response) {
  result.value = response
  busy.value = ['queued', 'processing'].includes(response.status)
  if (!busy.value) {
    values.value = pages.value.map((page, index) => ({ ...Object.fromEntries(Object.keys(fields).map(key => [key, String(recognized(page, key))])), ...response.student_values?.[index] }))
    emit('recognized', values.value)
  }
}
async function poll(id, current) {
  try {
    const response = await certificateApi.getAssessment(id, controller.signal)
    if (current !== generation) return
    apply(response)
    if (busy.value) timer = setTimeout(() => poll(id, current), 2000)
  } catch (e) {
    if (current !== generation || e.name === 'AbortError') return
    error.value = e.message; busy.value = false
  }
}
async function start() {
  stop(); const current = generation
  controller = new AbortController(); error.value = ''; result.value = null; values.value = []; busy.value = false
  if (props.project !== 'lanqiao') return
  if (import.meta.env.MODE === 'demo') { error.value = '真实OCR请使用正常开发模式'; return }
  const files = props.files.filter(file => file instanceof File)
  if (!files.length) {
    if (props.existingId) { busy.value = true; await poll(props.existingId, current) }
    return
  }
  busy.value = true
  try {
    const response = await certificateApi.createPreview(files, controller.signal)
    if (current !== generation) return
    apply(response)
    await poll(response.application_id, current)
  } catch (e) {
    if (current !== generation || e.name === 'AbortError') return
    error.value = `${e.message}。请先到申请记录确认是否已有识别草稿，避免重复上传。`; busy.value = false
  }
}
function refresh() {
  if (!result.value || saving.value) return
  clearTimeout(timer); error.value = ''; busy.value = true
  poll(result.value.application_id, generation)
}
async function confirm(data, submit) {
  if (saving.value) throw new Error('正在保存，请勿重复操作')
  if (!ready.value) throw new Error('请等待识别完成并核对预览表格；失败时重新选择材料')
  saving.value = true; emit('saving', true)
  try {
    const response = await certificateApi.confirmPreview(result.value.application_id, {
      version: result.value.version, project_name: data.projectName, award_date: data.awardDate,
      rule_id: Number(data.ruleId), student_values: values.value, submit
    })
    apply(response)
    return response.application_id
  } catch (e) { throw e }
  finally { saving.value = false; emit('saving', false) }
}
watch(() => [props.project, props.files, props.existingId], start, { immediate: true })
onBeforeUnmount(stop)
defineExpose({ confirm })
</script>

<style scoped>
.ocr-preview { padding:20px; border:1px solid #a9c8ee; border-radius:12px; margin:16px 0; }
table { width:100%; border-collapse:collapse; } th,td { text-align:left; border-bottom:1px solid #ddd; padding:8px; } input { width:100%; box-sizing:border-box; padding:8px; } .original { display:block; max-width:100%; max-height:240px; margin:12px 0; } article { margin-top:16px; } [role=alert] { color:#a22; }
</style>
