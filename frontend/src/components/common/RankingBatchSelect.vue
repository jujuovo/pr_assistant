<template>
  <label class="ranking-select">
    <span>排名批次</span>
    <select v-model="selection" class="form-control" :disabled="disabled">
      <option value="" disabled>请选择排名批次</option>
      <option v-for="batch in batches" :key="batch.batch_id" :value="batch.batch_id">
        {{ rankingBatchLabel(batch) }}
      </option>
    </select>
  </label>
</template>

<script>
const statuses = {
  draft: '试算', stale: '试算已失效', frozen: '已冻结', published: '已发布',
  withdrawn: '已撤回', correction_required: '纠错中'
}

export function rankingBatchLabel(batch) {
  const scope = batch.major_name || '学院范围'
  return [`${batch.year} 届`, scope, `第 ${batch.version} 版`, statuses[batch.status] || batch.status].join(' · ')
}
</script>

<script setup>
defineProps({ batches: { type: Array, required: true }, disabled: Boolean })
const selection = defineModel({ type: [String, Number], required: true })
</script>

<style scoped>
.ranking-select { display: grid; gap: .5rem; width: min(100%, 36rem); }
</style>
