<template>
  <section class="page-content teacher-statistics">
    <header class="page-title">
      <h1>统计报表</h1>
    </header>
    <StatisticsReport
      embedded
      :hidden="rankingOnly"
      :ranking-years="rankingYears"
      :can-export-ranking="Boolean(exportableRanking)"
      emphasize-primary-frame
      @export-ranking="exportRanking"
    >
      <template #filter-actions>
        <label class="ranking-toggle">
          <input type="checkbox" :checked="rankingOnly" @change="changeMode($event.target.checked)" />
          只看排名
        </label>
      </template>
      <template #ranking="{ scope }">
        <RankingBatch
          :key="`${scope.majorId}-${scope.year}`"
          ref="batchView"
          title="专业排名"
          show-basis
          embedded
          prefer-latest
          :scope="scope"
        />
        <RankingExport :key="`${scope.majorId}-${scope.year}`" ref="exporter" />
      </template>
    </StatisticsReport>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RankingBatch from '@/pages/common/statistics/RankingBatch.vue'
import StatisticsReport from '@/pages/common/statistics/StatisticsReport.vue'
import workflowApi from '@/services/workflowApi.js'
import RankingExport from '@/components/common/RankingExport.vue'

const route = useRoute()
const router = useRouter()
const exporter = ref(null)
const batchView = ref(null)
const exportableRanking = computed(() => batchView.value?.exportableRanking)

function exportRanking() {
  if (rankingOnly.value && exportableRanking.value) exporter.value?.open(exportableRanking.value)
}
const rankingOnly = computed(() => route.query.page === 'rankings' || route.query.ranking_only === '1')
const rankingYears = ref([])
const yearRequest = new AbortController()
onMounted(async () => {
  try {
    const options = await workflowApi.listRankings(yearRequest.signal)
    rankingYears.value = options.items.map((batch) => batch.year)
  } catch {
    // The current academic year remains selectable when batch options are unavailable.
  }
})
onUnmounted(() => yearRequest.abort())

function changeMode(enabled) {
  const query = { ...route.query, page: 'statistics-report' }
  if (enabled) {
    query.ranking_only = '1'
  } else {
    delete query.ranking_only
    delete query.batch_id
  }
  return router.replace({ query })
}
</script>

<style scoped src="@/assets/styles/pages/teacher/rankings/TeacherRanking.css"></style>
