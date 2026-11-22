<template>
  <RankingBatch title="专业排名" show-basis>
    <template #actions="{ ranking }">
      <button v-if="ranking.allowed_actions.includes('export')" class="btn btn-outline"
        type="button" @click="exporter.open(ranking)">导出名单</button>
    </template>
  </RankingBatch>
  <RankingExport ref="exporter" />
</template>

<script setup>
import { ref } from 'vue'
import RankingBatch from '@/pages/common/statistics/RankingBatch.vue'
import RankingExport from '@/components/common/RankingExport.vue'

const exporter = ref(null)
</script>
