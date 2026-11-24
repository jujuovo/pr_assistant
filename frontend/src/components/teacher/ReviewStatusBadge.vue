<template>
  <span class="status-badge">{{ scoreStatusText(status) }}</span>
</template>

<script setup>
import { scoreStatusText } from '@/services/scorePresentation.js'

defineProps({ status: { type: String, required: true } })
</script>

<style scoped>
.status-badge {
  display: inline-block;
  width: max-content;
  padding: 4px 8px;
  border-radius: 999px;
  background: #fff2d3;
  color: #805500;
  font-size: 12px;
}
</style>
