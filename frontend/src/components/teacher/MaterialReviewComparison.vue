<template>
  <section class="review-comparison">
    <h4>学生申报与 OCR 对照</h4>
    <p v-if="!hasOcr">暂无 OCR 结果，请结合原件人工核对。</p>
    <p v-else>请以原件为准。OCR 字段缺失或格式不同的项目需要人工核对。</p>
    <div
      v-if="rows.length"
      class="comparison-scroll"
      tabindex="0"
      role="region"
      aria-label="字段对照表"
    >
      <table>
        <thead>
          <tr
            ><th scope="col">字段</th><th scope="col">{{ declaredHeading }}</th
            ><th scope="col">OCR 识别</th><th scope="col">核对结果</th></tr
          >
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.key"
            :class="{ 'comparison-difference': row.different }"
          >
            <th scope="row">{{ labels[row.key] || fieldLabel(row.key) }}</th>
            <td>{{ !hasValue(row.declared) ? '未填写' : displayValue(row.declared) }}</td>
            <td>{{ hasValue(row.recognized) ? displayValue(row.recognized) : '未识别' }}</td>
            <td>{{ row.result }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { displayValue, fieldLabel, INTERNAL_FIELDS } from '@/services/materialFields.js'

const props = defineProps({
  declaredHeading: { type: String, default: '学生申报' },
  declared: { type: Object, default: () => ({}) },
  recognized: { type: Object, default: () => ({}) },
  differences: { type: Array, default: null },
  labels: { type: Object, default: () => ({}) }
})

const comparableFields = new Set([
  'project_name',
  'competition_name',
  'award_date',
  'certificate_no',
  'certification_name',
  'test_date',
  'activity_name',
  'volunteer_name'
])
const hasValue = (value) =>
  value != null && value !== '' && (!Array.isArray(value) || value.length > 0)
const hasOcr = computed(
  () => Object.values(props.recognized || {}).some(hasValue) || Boolean(props.differences?.length)
)
const rows = computed(() => {
  const declaredFields = props.declared || {}
  const recognizedFields = props.recognized || {}
  const differences = new Map(props.differences?.map((item) => [item.field, item]))
  const keys = new Set([
    ...Object.keys(declaredFields),
    ...Object.keys(recognizedFields),
    ...differences.keys()
  ])

  return [...keys]
    .filter((key) => !INTERNAL_FIELDS.has(key))
    .map((key) => {
      const difference = differences.get(key)
      const declared = difference ? difference.declared : declaredFields[key]
      const recognized = difference ? difference.recognized : recognizedFields[key]
      const comparable =
        props.differences === null &&
        comparableFields.has(key) &&
        typeof declared === typeof recognized &&
        ['string', 'number'].includes(typeof declared) &&
        hasValue(declared) &&
        hasValue(recognized)
      const matches = comparable && String(declared).trim() === String(recognized).trim()
      const different = Boolean(difference) || (comparable && !matches)
      return {
        key,
        declared,
        recognized,
        different,
        result: different ? '不一致' : matches ? '一致' : '需人工核对'
      }
    })
})
</script>

<style scoped src="@/assets/styles/components/teacher/MaterialReviewComparison.css"></style>
