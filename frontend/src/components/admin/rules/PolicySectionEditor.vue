<template>
  <section class="policy-section">
    <h3>{{ title }}</h3>
    <div class="fields">
      <label v-for="field in fields" :key="field.key">
        {{ field.label }}
        <input class="form-control" :aria-label="field.label" type="number" min="0" :max="field.max" :step="field.integer ? 1 : 'any'"
          :disabled="dirty" :value="modelValue[field.key] ?? ''" @input="update(field.key, $event)" />
      </label>
    </div>
    <p v-if="dirty" role="status">此模块有未应用的 JSON 修改。应用或撤销后即可继续编辑表单。</p>
    <details :open="dirty || undefined">
      <summary>展开 JSON</summary>
      <textarea class="form-control" :aria-label="title + ' JSON'" :value="dirty ? buffer : formatted" rows="10"
        @input="editJson($event.target.value)" />
      <button class="btn btn-outline" type="button" :disabled="!dirty" @click="applyJson">应用 JSON</button>
      <button class="btn btn-outline" type="button" :disabled="!dirty" @click="reset">撤销未应用编辑</button>
      <p v-if="error" role="alert">{{ error }}</p>
    </details>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  fields: { type: Array, default: () => [] }
})
const modelValue = defineModel({ type: Object, required: true })
const dirty = defineModel('dirty', { type: Boolean, default: false })
const formatted = computed(() => JSON.stringify(modelValue.value, null, 2))
const buffer = ref('')
const error = ref('')

function update(key, event) {
  const next = { ...modelValue.value }
  if (event.target.value === '') delete next[key]
  else next[key] = event.target.valueAsNumber
  modelValue.value = next
}

function editJson(value) {
  buffer.value = value
  dirty.value = value !== formatted.value
  error.value = ''
}

function reset() {
  dirty.value = false
  error.value = ''
}

function applyJson() {
  try {
    const next = JSON.parse(buffer.value)
    if (!next || typeof next !== 'object' || Array.isArray(next)) {
      throw new Error('章节 JSON 必须是对象')
    }
    for (const field of props.fields) {
      if (!Object.hasOwn(next, field.key)) continue
      const value = next[field.key]
      if (!Number.isFinite(value) || value < 0 || value > (field.max ?? Infinity) ||
          (field.integer && !Number.isSafeInteger(value))) {
        throw new Error(field.label + '的值超出允许范围或格式不正确')
      }
    }
    modelValue.value = next
    reset()
  } catch (e) {
    error.value = e instanceof SyntaxError ? 'JSON 格式有误，请检查括号、逗号和引号' : e.message
  }
}
</script>

<style scoped>
.policy-section { border-top: 1px solid #dce5ef; padding: 1.5rem 0; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr)); gap: 1.25rem; margin: 1rem 0 1.25rem; }
label { display: grid; gap: .4rem; }
textarea { display: block; width: 100%; margin: .6rem 0; font-family: monospace; }
</style>
