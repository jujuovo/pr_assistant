<template>
  <section class="manual-draft"
    ><button type="button" class="btn btn-outline" @click="open">不使用识别，直接人工填写</button>
    <form v-if="visible && spec" @submit.prevent="save"
      ><h3>人工填写材料</h3><p>此通道仅供人工核验，不运行 OCR 或计算加分。</p
      ><label
        >材料年度<input v-model.number="year" type="number" min="2000" max="2100" required /></label
      ><MaterialFieldsEditor v-model="data" :fields="fields" :required="spec.required" /><label
        >证明原件<input
          type="file"
          multiple
          @change="files = Array.from($event.target.files || [])"
          required /></label
      ><button class="btn btn-primary" :disabled="busy">{{
        busy ? '保存中…' : '保存人工材料草稿'
      }}</button></form
    >
    <p v-if="loading" role="status">正在加载填写项目…</p
    ><p v-if="error" role="alert">{{ error }}</p></section
  >
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import materialApi from '@/services/materialApi.js'
import MaterialFieldsEditor from '@/components/common/MaterialFieldsEditor.vue'
const props = defineProps({ category: { type: String, required: true } }),
  emit = defineEmits(['saved'])
const visible = ref(false),
  spec = ref(null),
  data = ref({}),
  files = ref([]),
  year = ref(new Date().getFullYear()),
  loading = ref(false),
  busy = ref(false),
  error = ref('')
const subtypeFields = {
  practice_proof: ['team', 'period_as_printed'],
  platform_screenshot: ['submitter', 'honor_name', 'honor_date'],
  team_list: ['teams']
}
const fields = computed(() => [
  ...(spec.value?.required || []),
  ...(subtypeFields[data.value.document_type] || [])
])
watch(
  () => props.category,
  () => {
    visible.value = false
    spec.value = null
    error.value = ''
  }
)
async function open() {
  visible.value = true
  loading.value = true
  error.value = ''
  try {
    spec.value = (await materialApi.getTypes()).types.find((t) => t.key === props.category)
    data.value = Object.fromEntries(spec.value.required.map((k) => [k, '']))
    if (props.category === 'social_practice') data.value.document_type = 'practice_proof'
    if (props.category === 'research') data.value.document_type = 'research_report'
    if (props.category === 'student_work')
      data.value.appointments = [
        {
          organization: '',
          position: '',
          position_level: '',
          start_date: '',
          end_date: null,
          assessment_result: ''
        }
      ]
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function save() {
  if (busy.value) return
  if (!files.value.length) {
    error.value = '请提供证明原件。'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const uploaded = await materialApi.createManualRecord(
      props.category,
      year.value,
      data.value,
      files.value
    )
    visible.value = false
    emit('saved', uploaded)
  } catch (e) {
    error.value = '保存未完成；请先检查材料列表，避免重复创建。' + e.message
  } finally {
    busy.value = false
  }
}
</script>
<style scoped>
.manual-draft {
  display: grid;
  gap: 12px;
}
.manual-draft form {
  display: grid;
  gap: 16px;
  padding: 20px;
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
}
.manual-draft label {
  display: grid;
  gap: 6px;
}
.manual-draft input {
  padding: 9px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
.manual-draft button {
  justify-self: start;
}
</style>
