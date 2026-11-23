<template>
  <dl class="material-facts"
    ><template v-for="[key, value] in visible" :key="key"
      ><dt>{{ labels[key] || fieldLabel(key) }}</dt
      ><dd :class="{ 'fact-difference': highlightedFields.includes(key) }" :data-field="key">{{ displayValue(value) }}<small v-if="highlightedFields.includes(key)" class="difference-mark">待核对</small></dd></template
    ><p v-if="!visible.length">暂无识别内容，可按原件人工填写。</p></dl
  >
</template>
<script setup>
import { computed } from 'vue'
import { fieldLabel, displayValue, INTERNAL_FIELDS } from '@/services/materialFields.js'
const props = defineProps({
  data: { type: Object, default: () => ({}) },
  labels: { type: Object, default: () => ({}) },
  highlightedFields: { type: Array, default: () => [] }
})
const visible = computed(() =>
  Object.entries(props.data || {}).filter(([k]) => !INTERNAL_FIELDS.has(k))
)
</script>
<style scoped>
.material-facts {
  display: grid;
  grid-template-columns: minmax(90px, 1fr) 3fr;
  gap: 8px 14px;
  margin: 12px 0;
}
.material-facts dt {
  color: #536479;
}
.material-facts dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.material-facts .fact-difference { color: #b42335; font-weight: 600; background: #fff0f2; border-radius: 4px; }
.difference-mark { margin-left: 8px; font-size: 12px; font-weight: 400; }
@media (max-width: 550px) {
  .material-facts {
    grid-template-columns: 1fr;
    gap: 5px;
  }
  .material-facts dd {
    margin-bottom: 8px;
  }
}
</style>
