<template>
  <section class="manual-draft"
    ><button type="button" class="btn btn-outline" @click="open">{{
      category === 'volunteer' ? '填写志愿服务材料' : '人工填写材料'
    }}</button>
    <form v-if="visible && spec" @submit.prevent="save"
      ><h3 v-if="category === 'volunteer'">人工填写材料</h3
      ><p v-if="category === 'volunteer'">{{
        category === 'volunteer'
          ? '请手填本次工时、工时类别和服务记录日期。信用时数、荣誉时数截图按普通志愿服务核对：信用填写签退当天日期，荣誉填写录入当天日期。后台比对三项，一致后可提交教师审核；有差异可申诉。'
          : '此通道仅供人工核验，不运行 OCR 或计算加分。'
      }}</p
      ><label
        >{{ category === 'volunteer' ? '推免周期' : '材料年度'
        }}<input
          v-model.number="year"
          type="number"
          min="2000"
          max="2100"
          :readonly="category === 'volunteer'"
          required /></label
      ><div v-if="category === 'volunteer'" class="volunteer-fields">
        <label
          >本次工时类别<select v-model="volunteerType"
            ><option value="regular">普通志愿服务</option
            ><option value="reduced">大型赛会或支教</option></select
          ></label
        >
        <label
          >本次工时（小时）<input
            v-model="volunteerHours"
            type="number"
            min="0.0001"
            max="100000"
            step="0.0001"
            required
        /></label>
        <label>服务记录日期<input v-model="data.award_date" type="date" required /></label
        ><p class="date-guidance"
          >信用时数同时核对签到、签退时间，跨日按签退日期；荣誉时数按录入日期。不同日期请分次申报。</p
        > </div
      ><PolicyMaterialFields
        v-else-if="['research_paper', 'invention_patent', 'innovation_training'].includes(category)"
        v-model="data"
        :category="category"
      />
      <MaterialFieldsEditor
        v-else
        v-model="data"
        :fields="fields"
        :required="spec.required"
        :document-types="spec.document_types || []"
        :labels="
          category === 'volunteer'
            ? { award_date: '服务记录日期' }
            : category === 'arts_sports'
              ? { award_date: '获得时间' }
              : {}
        "
      /><label
        >证明原件<input
          type="file"
          multiple
          @change="files = Array.from($event.target.files || [])"
          required /></label
      ><MaterialImagePreview :files="files" /><button class="btn btn-primary" :disabled="busy">{{
        busy ? '保存中…' : category === 'volunteer' ? '保存并后台识别' : '保存人工材料草稿'
      }}</button></form
    >
    <p v-if="loading" role="status">正在加载填写项目…</p
    ><p v-if="error" role="alert">{{ error }}</p></section
  >
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import materialApi from '@/services/materialApi.js'
import PolicyMaterialFields from '@/components/common/PolicyMaterialFields.vue'
import MaterialFieldsEditor from '@/components/common/MaterialFieldsEditor.vue'
import MaterialImagePreview from '@/components/common/MaterialImagePreview.vue'
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
const volunteerType = ref('regular')
const volunteerHours = ref('')
const subtypeFields = {
  practice_proof: ['team', 'period_as_printed'],
  platform_screenshot: ['submitter', 'honor_name', 'honor_date'],
  team_list: ['teams']
}
const fields = computed(() => [
  ...(spec.value?.required || []),
  ...(subtypeFields[data.value.document_type] || []),
  ...(spec.value?.fields || []).filter(
    (field) =>
      !(spec.value?.required || []).includes(field) &&
      !(subtypeFields[data.value.document_type] || []).includes(field) &&
      field !== 'reference_id'
  )
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
  files.value = []
  visible.value = true
  loading.value = true
  error.value = ''
  try {
    const context = await materialApi.getTypes()
    spec.value = context.types.find((t) => t.key === props.category)
    if (
      [
        'research_paper',
        'invention_patent',
        'innovation_training',
        'student_work',
        'volunteer'
      ].includes(props.category)
    ) {
      if (!context.cycle_code || context.cycle_code < 2028)
        throw new Error('请先由管理员启用2028届或之后的推免周期。')
      year.value = context.cycle_code
    }
    if (!spec.value) throw new Error('此类材料尚未开放，请返回选择其他类别。')
    data.value = Object.fromEntries(spec.value.required.map((k) => [k, '']))
    volunteerType.value = 'regular'
    volunteerHours.value = ''
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
  if (props.category === 'volunteer') {
    const hours = Number(volunteerHours.value)
    if (!Number.isFinite(hours) || hours <= 0 || hours > 100000) {
      error.value = '请填写大于 0 的本次工时。'
      return
    }
    data.value = {
      award_date: data.value.award_date,
      regular_hours: volunteerType.value === 'regular' ? String(volunteerHours.value) : '0',
      reduced_hours: volunteerType.value === 'reduced' ? String(volunteerHours.value) : '0'
    }
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
.date-guidance {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #52667c;
}
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
.volunteer-fields {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.volunteer-fields label {
  display: grid;
  gap: 6px;
}
.volunteer-fields select {
  padding: 9px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
@media (max-width: 600px) {
  .volunteer-fields {
    grid-template-columns: 1fr;
  }
}
.manual-draft button {
  justify-self: start;
}
</style>
