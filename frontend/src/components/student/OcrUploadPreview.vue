<template>
  <section class="ocr-upload"
    ><h3>上传证书辅助填写</h3
    ><p>请选择已适配项目并上传清晰图片，识别后核对再填入表单。原图会保留供教师核验。</p>
    <label
      >识别项目<select v-model="project" :disabled="busy"
        ><option value="">请选择</option
        ><option v-for="p in projects" :key="p.key" :value="p.key">{{ p.name }}</option></select
      ></label
    >
    <label
      >证书图片<input
        type="file"
        accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff"
        :disabled="busy"
        @change="file = $event.target.files?.[0]"
    /></label>
    <button
      type="button"
      class="btn btn-outline"
      :disabled="busy || !project || !file"
      @click="recognize"
      >{{ busy ? '正在识别…' : '识别图片' }}</button
    >
    <p v-if="busy" role="status">识别处理中，您可以保留此页等待，也可继续人工填写。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="result?.mapping"
      ><MaterialFacts :data="result.report?.fields || {}" /><p
        v-for="warning in result.mapping.warnings"
        :key="warning"
        class="warning"
        >{{ warning }}</p
      >
      <a
        v-if="result.artifact_urls?.original"
        :href="result.artifact_urls.original"
        target="_blank"
        rel="noopener"
        >查看原始图片</a
      >
      <button
        type="button"
        class="btn btn-primary"
        data-test="use-ocr"
        :disabled="busy"
        @click="$emit('use', result)"
        >使用识别建议并核对</button
      ></template
    >
  </section>
</template>
<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import ocrApi from '@/services/ocrApi.js'
import MaterialFacts from '@/components/common/MaterialFacts.vue'
const props = defineProps({ formalOnly: { type: Boolean, default: false } })
defineEmits(['use'])
const projects = ref([]),
  project = ref(''),
  file = ref(null),
  busy = ref(false),
  error = ref(''),
  result = ref(null)
let controller = null,
  timer = null,
  disposed = false
onMounted(async () => {
  try {
    const data = await ocrApi.getCategories()
    if (!disposed)
      projects.value = data.categories.filter(
        (p) =>
          !props.formalOnly ||
          ['lanqiao', 'computer-design', 'challenge-cup', 'csp'].includes(p.key)
      )
  } catch {
    error.value = '识别目录暂不可用，您仍可手工填写。'
  }
})
onBeforeUnmount(() => {
  disposed = true
  controller?.abort()
  clearTimeout(timer)
})
async function poll(id) {
  try {
    const row = await ocrApi.getJob(id, controller.signal)
    if (disposed) return
    result.value = row
    if (['queued', 'processing'].includes(row.status)) timer = setTimeout(() => poll(id), 1200)
    else {
      busy.value = false
      if (row.status === 'failed') error.value = row.error || '识别失败，请换清晰图片或手工填写。'
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      busy.value = false
      error.value = e.message
    }
  }
}
async function recognize() {
  busy.value = true
  error.value = ''
  result.value = null
  controller?.abort()
  clearTimeout(timer)
  controller = new AbortController()
  try {
    const row = await ocrApi.recognize(project.value, file.value, controller.signal)
    await poll(row.id)
  } catch (e) {
    busy.value = false
    if (e.name !== 'AbortError') error.value = e.message || '上传失败，请稍后重试。'
  }
}
</script>
<style scoped>
.ocr-upload {
  padding: 20px;
  background: #f6f9fd;
  border: 1px solid #dce5ef;
  border-radius: 12px;
  display: grid;
  gap: 12px;
  margin: 16px 0;
}
.ocr-upload h3,
.ocr-upload p {
  margin: 0;
}
.ocr-upload label {
  display: grid;
  gap: 5px;
}
.ocr-upload select {
  padding: 9px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
.ocr-upload .warning {
  color: #805500;
}
.ocr-upload button {
  justify-self: start;
}
</style>
