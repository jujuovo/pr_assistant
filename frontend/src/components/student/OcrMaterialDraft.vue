<template>
  <section
    ><OcrUploadPreview @use="useResult" />
    <form v-if="mapping" @submit.prevent="save" class="material-draft"
      ><h3>核对并保存材料</h3
      ><p>请对照原图核对识别字段。未识别项需要补充，姓名、队名和页面状态仍须教师核验。</p>
      <p v-if="mapping.material_category === 'competition'"
        >该材料属于正式竞赛，请前往竞赛申报继续确认。</p
      >
      <button
        v-if="mapping.material_category === 'competition'"
        type="button"
        class="btn btn-primary"
        @click="$emit('competition', job.id)"
        >前往竞赛申报</button
      >
      <button
        v-if="mapping.material_category === 'competition'"
        type="button"
        class="btn btn-outline"
        @click="manual"
        >不申请计分，仅保存人工核验材料</button
      >
      <template v-else
        ><label
          >材料年度<input
            type="number"
            v-model.number="year"
            min="2000"
            max="2100"
            required /></label
        ><MaterialFieldsEditor v-model="data" :fields="fields" :required="required" /><button
          class="btn btn-primary"
          :disabled="busy"
          >{{ busy ? '保存中…' : '确认字段并保存草稿' }}</button
        ></template
      > </form
    ><p v-if="notice" role="status">{{ notice }}</p
    ><p v-if="error" role="alert">{{ error }}</p></section
  >
</template>
<script setup>
import { ref } from 'vue'
import ocrApi from '@/services/ocrApi.js'
import materialApi from '@/services/materialApi.js'
import OcrUploadPreview from './OcrUploadPreview.vue'
import MaterialFieldsEditor from '@/components/common/MaterialFieldsEditor.vue'
const emit = defineEmits(['saved', 'competition'])
const job = ref(null),
  mapping = ref(null),
  data = ref({}),
  year = ref(new Date().getFullYear()),
  fields = ref([]),
  required = ref([]),
  busy = ref(false),
  error = ref(''),
  notice = ref(''),
  manualOnly = ref(false)
async function useResult(result) {
  error.value = ''
  manualOnly.value = false
  notice.value = ''
  job.value = result
  mapping.value = result.mapping
  if (!mapping.value?.material_category) {
    error.value = '尚未匹配到已适配材料类型，请通过人工填报提交原件。'
    mapping.value = null
    return
  }
  data.value = JSON.parse(JSON.stringify(result.mapping.data))
  try {
    const types = await materialApi.getTypes()
    const type = types.types.find((t) => t.key === mapping.value.material_category)
    required.value = type?.required || []
    fields.value = [
      ...new Set([
        ...Object.keys(data.value),
        ...required.value,
        ...(mapping.value.missing_fields || []).filter((k) => !k.includes('['))
      ])
    ]
  } catch (e) {
    error.value = e.message
  }
}
async function manual() {
  const evidence = job.value.mapping.data.evidence || job.value.mapping.evidence || {}
  const category = job.value.category === 'csp' ? 'certification' : 'competition_evidence'
  await useResult({
    ...job.value,
    mapping: { ...mapping.value, material_category: category, data: evidence, missing_fields: [] }
  })
  manualOnly.value = true
}
async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const response = await ocrApi.confirmMaterial(job.value.id, {
      year: year.value,
      data: data.value,
      manual_only: manualOnly.value
    })
    notice.value = '草稿已保存，请检查附件后提交教师审核。'
    mapping.value = null
    emit('saved', response.material)
  } catch (e) {
    error.value = e.message || '保存失败，请检查必填字段后重试。'
  } finally {
    busy.value = false
  }
}
</script>
<style scoped>
.material-draft {
  display: grid;
  gap: 16px;
  padding: 20px;
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
}
.material-draft > label {
  display: grid;
  gap: 5px;
}
.material-draft > label input {
  padding: 9px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
.material-draft button {
  justify-self: start;
}
</style>
