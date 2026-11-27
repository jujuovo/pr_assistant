<template>
  <details v-if="events?.length" class="review-timeline">
    <summary>完整审核记录（{{ events.length }}）</summary>
    <ol>
      <li v-for="(event, index) in events" :key="index">
        <strong>{{ stages[event.review_stage] || '材料操作' }}</strong>
        · {{ event.actor?.name || '系统' }}（{{ roles[event.actor?.role] || '系统' }}）
        <span v-if="event.decision"> · {{ decisions[event.decision] || event.decision }}</span>
        <p v-if="event.comment">{{ event.comment }}</p>
        <time>{{ formatScoreTime(event.created_at) }}</time>
      </li>
    </ol>
  </details>
</template>
<script setup>
import { formatScoreTime } from '@/services/scorePresentation.js'
defineProps({ events: Array })
const stages = { 1: '一级审核', 2: '二级审核', 3: '教师终审' }
const roles = { reviewer_level1: '一级审核员', reviewer_level2: '二级审核员', teacher: '教师', admin: '管理员', student: '学生' }
const decisions = { approve: '通过', verified: '通过', return: '退回修改', needs_correction: '退回修改', rejected: '退回修改' }
</script>
<style scoped>
.review-timeline { margin-block: 12px; }
li { margin-block: 12px; overflow-wrap: anywhere; }
time { display: block; color: var(--system-ink-muted, #667085); font-size: 13px; }
</style>
