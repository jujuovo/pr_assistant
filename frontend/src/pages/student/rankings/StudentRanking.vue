<template>
  <div class="student-ranking-page">
    <RankingBatch title="我的排名">
      <template #default="{ ranking }">
        <p v-if="messages[ranking.status]" class="ranking-notice" role="status">{{
          messages[ranking.status]
        }}</p>
        <dl v-if="ranking.entries[0]" class="personal-result">
          <div class="personal-rank"
            ><dt>本人名次</dt><dd>{{ ranking.entries[0].rank ?? '—' }}</dd></div
          >
          <div
            ><dt>批次总人数</dt><dd>{{ ranking.total_count }}</dd></div
          >
          <div
            ><dt>推免综合成绩</dt><dd>{{ ranking.entries[0].comprehensive_score ?? '—' }}</dd></div
          >
        </dl>
        <p v-if="ranking.entries[0]?.reason_code"
          >未纳入原因 {{ ranking.entries[0].reason_code }}</p
        >
        <p v-if="!ranking.entries.length">本批次暂无你的排名结果。</p>
      </template>
    </RankingBatch>
  </div>
</template>

<script setup>
import RankingBatch from '@/pages/common/statistics/RankingBatch.vue'

const messages = {
  draft: '本批次为试算结果。',
  stale: '试算结果已失效。',
  frozen: '本批次已冻结，等待发布。',
  withdrawn: '本批次已撤回。',
  correction_required: '本批次正在纠错。'
}
</script>

<style scoped src="@/assets/styles/pages/student/rankings/StudentRanking.css"></style>
