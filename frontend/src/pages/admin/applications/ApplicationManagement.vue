<template>
  <section class="page-content">
    <label>审核范围
      <select v-model="mode" class="form-control">
        <option value="pending">待审核材料</option>
        <option value="history">审核记录</option>
      </select>
    </label>
    <PendingReview :key="mode" :history="mode === 'history'" />
  </section>
</template>

<script setup>
import { ref } from 'vue'
import PendingReview from '@/pages/teacher/reviews/PendingReview.vue'

const mode = ref('pending')
</script>
