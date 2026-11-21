<template>
  <div class="fields-editor"
    ><label v-for="field in visible" :key="field"
      >{{ labels[field] || fieldLabel(field) }}<span v-if="required.includes(field)"> *</span>
      <select
        v-if="field === 'document_type'"
        :value="modelValue[field]"
        @change="change(field, $event.target.value)"
        ><option value="">请选择</option
        ><option v-for="item in kinds" :key="item" :value="item">{{
          displayValue(item)
        }}</option></select
      >
      <textarea
        v-else-if="ARRAY_FIELDS.has(field)"
        :value="text(modelValue[field])"
        @input="change(field, $event.target.value)"
        placeholder="多项用换行分隔"
        rows="2"
      ></textarea>
      <input
        v-else
        :list="suggestions[field] ? listId + field : undefined"
        :type="isDate(field) ? 'date' : 'text'"
        :value="modelValue[field] ?? ''"
        @input="change(field, $event.target.value)"
        :required="required.includes(field)"
      />
      <datalist v-if="suggestions[field]" :id="listId + field"><option v-for="value in suggestions[field]" :key="value" :value="value" /></datalist>
    </label>
    <fieldset v-for="(role, index) in modelValue.appointments || []" :key="index"
      ><legend>任职记录 {{ index + 1 }}</legend
      ><label v-for="field in roleFields" :key="field"
        >{{ fieldLabel(field)
        }}<input
          :type="isDate(field) ? 'date' : 'text'"
          :value="role[field] ?? ''"
          @input="roleChange(index, field, $event.target.value)"
          :required="field !== 'end_date'" /></label></fieldset
  ></div>
</template>
<script setup>
import { computed, useId } from 'vue'
import {
  ARRAY_FIELDS,
  fieldLabel,
  displayValue,
  INTERNAL_FIELDS
} from '@/services/materialFields.js'
const listId = useId()
const suggestions = { database: ['SCI-E', 'EI Compendex', 'Scopus', 'CNKI'], requester_school: ['厦门大学'] }
const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  fields: { type: Array, default: () => [] },
  required: { type: Array, default: () => [] }
  ,labels: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:modelValue'])
const roleFields = [
  'organization',
  'position',
  'position_level',
  'start_date',
  'end_date',
  'assessment_result'
]
const kinds = [
  'practice_proof',
  'platform_screenshot',
  'team_list',
  'research_report',
  'csp_transcript'
]
const visible = computed(() =>
  [...new Set([...props.fields, ...Object.keys(props.modelValue)])].filter(
    (k) => k !== 'appointments' && k !== 'evidence' && !INTERNAL_FIELDS.has(k)
  )
)
const text = (value) => (Array.isArray(value) ? value.join(String.fromCharCode(10)) : (value ?? ''))
const isDate = (field) => field === 'as_of' || field.endsWith('_date')
function change(field, value) {
  const parsed = ARRAY_FIELDS.has(field)
    ? value
        .split(new RegExp('[' + String.fromCharCode(10) + '、,，]+'))
        .map((x) => x.trim())
        .filter(Boolean)
    : value
  emit('update:modelValue', { ...props.modelValue, [field]: parsed })
}
function roleChange(index, field, value) {
  const appointments = props.modelValue.appointments.map((role, i) =>
    i === index ? { ...role, [field]: field === 'end_date' && !value ? null : value } : role
  )
  emit('update:modelValue', { ...props.modelValue, appointments })
}
</script>
<style scoped>
.fields-editor {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.fields-editor label {
  display: grid;
  gap: 6px;
  color: #33445b;
}
.fields-editor input,
.fields-editor select,
.fields-editor textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
  background: #fff;
}
.fields-editor fieldset {
  grid-column: 1/-1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  border: 1px solid #dce5ef;
  border-radius: 8px;
  padding: 14px;
}
@media (max-width: 600px) {
  .fields-editor,
  .fields-editor fieldset {
    grid-template-columns: 1fr;
  }
}
</style>
