<template>
  <section class="ranking-batches" :class="{ 'page-content': !embedded }">
    <div v-if="!embedded" class="page-title"><span>{{ title }}</span></div>
    <slot name="before" />
    <div class="card batch-controls">
      <p v-if="loadingOptions" role="status">正在加载排名批次…</p>
      <RankingBatchSelect v-else-if="batches.length" v-model="batchId" :batches="batches" :disabled="disabled" />
      <p v-else-if="!optionsError" role="status">暂无可查看的排名批次。</p>
      <p v-if="optionsError" role="alert">{{ optionsError }}
        <button type="button" class="btn btn-outline" @click="loadOptions()">重新加载批次</button>
      </p>
    </div>
    <p v-if="loadingDetail" role="status">正在加载排名详情…</p>
    <p v-if="detailError" role="alert">{{ detailError }}
      <button v-if="batchId" type="button" class="btn btn-outline" @click="loadDetail(batchId)">重试</button>
    </p>
    <article v-if="ranking" class="card batch-details">
      <h2>{{ selectedLabel }}</h2>
      <slot name="actions" :ranking="ranking" :label="selectedLabel" />
      <p>生成时间 {{ formatScoreTime(ranking.generated_at) }} · 发布时间 {{ ranking.published_at ? formatScoreTime(ranking.published_at) : '尚未发布' }}</p>
      <p v-if="ranking.reason_code" role="status">{{ ranking.reason_code }}</p>
      <slot :ranking="ranking" :label="selectedLabel">
      <div class="table-container" :tabindex="embedded ? 0 : undefined" :role="embedded ? 'region' : undefined" :aria-label="embedded ? '排名批次明细' : undefined">
        <table class="application-table">
          <thead><tr><th>学号</th><th>推免综合成绩</th><th>名次</th><th>未纳入原因</th><th v-if="showBasis">计分依据</th></tr></thead>
          <tbody>
            <tr v-for="row in ranking.entries" :key="row.student_id">
              <td>{{ row.student_id }}</td><td>{{ row.comprehensive_score ?? '—' }}</td>
              <td>{{ row.rank ?? '—' }}</td><td>{{ row.reason_code || '—' }}</td>
              <td v-if="showBasis">
                <details v-if="row.score_basis?.length">
                  <summary>展开依据</summary>
                  <ul><li v-for="(fact, index) in row.score_basis" :key="index">
                    {{ fact.faculty_scoring_policy_id ? `学院推免总规则编号 ${fact.faculty_scoring_policy_id}` :
                      `${fact.score_group === 'academic' ? '学术专长' : '综合表现'} · 计入 ${fact.effective_score} 分` }}
                  </li></ul>
                </details>
                <span v-else>—</span>
              </td>
            </tr>
            <tr v-if="!ranking.entries.length"><td :colspan="showBasis ? 5 : 4">本批次暂无排名明细。</td></tr>
          </tbody>
        </table>
      </div>
      </slot>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RankingBatchSelect, { rankingBatchLabel } from '@/components/common/RankingBatchSelect.vue'
import { formatScoreTime } from '@/services/scorePresentation.js'
import workflowApi from '@/services/workflowApi.js'
import { workflowErrorMessage } from '@/services/workflowPresentation.js'

const props = defineProps({
  embedded: Boolean,
  preferLatest: Boolean,
  scope: Object,
  title: { type: String, default: '排名批次' },
  showBasis: Boolean,
  disabled: Boolean
})

const route = useRoute()
const router = useRouter()
const batches = ref([])
const batchId = ref('')
const ranking = ref(null)
const loadingOptions = ref(true)
const loadingDetail = ref(false)
const optionsError = ref('')
const detailError = ref('')
let optionsRequest
let detailRequest

const selectedLabel = computed(() => {
  const batch = batches.value.find(item => item.batch_id === batchId.value)
  return batch ? rankingBatchLabel(batch) : '批次详情'
})

async function loadOptions(preferredId = null) {
  optionsRequest?.abort()
  const request = new AbortController()
  optionsRequest = request
  optionsError.value = ''
  loadingOptions.value = true
  try {
    batches.value = (await (props.scope ? workflowApi.listRankings(request.signal, props.scope) : workflowApi.listRankings(request.signal))).items
    if (preferredId && batches.value.some(batch => batch.batch_id === preferredId)) {
      if (batchId.value === preferredId) await loadDetail(preferredId)
      else batchId.value = preferredId
    } else {
      selectFromRoute()
    }
  } catch (error) {
    if (!request.signal.aborted) optionsError.value = workflowErrorMessage(error)
  } finally {
    if (!request.signal.aborted) loadingOptions.value = false
  }
}

function selectFromRoute() {
  const requested = Number(route.query.batch_id)
  if (batches.value.some(item => item.batch_id === requested)) {
    batchId.value = requested
  } else if (route.query.batch_id && !props.scope) {
    batchId.value = ''
    detailError.value = '该排名批次不存在或你没有查看权限。'
  } else {
    batchId.value = (!props.preferLatest ? batches.value.find(item => item.status === 'published')?.batch_id : undefined)
      ?? batches.value[0]?.batch_id ?? ''
  }
}

async function loadDetail(id) {
  detailRequest?.abort()
  const request = new AbortController()
  detailRequest = request
  ranking.value = null
  detailError.value = ''
  loadingDetail.value = true
  try {
    const result = await workflowApi.getRanking(id, request.signal)
    if (!request.signal.aborted) ranking.value = result
  } catch (error) {
    if (!request.signal.aborted) detailError.value = workflowErrorMessage(error)
  } finally {
    if (!request.signal.aborted) loadingDetail.value = false
  }
}

watch(batchId, id => {
  if (!id) {
    detailRequest?.abort()
    ranking.value = null
    loadingDetail.value = false
    return
  }
  if (String(route.query.batch_id) !== String(id)) {
    void router.replace({ query: { ...route.query, batch_id: String(id) } })
  }
  void loadDetail(id)
})
watch(() => route.query.batch_id, () => {
  if (!loadingOptions.value) selectFromRoute()
})

const exportableRanking = computed(() => (
  !loadingOptions.value && !loadingDetail.value &&
  ranking.value?.batch_id === batchId.value && ranking.value?.allowed_actions.includes('export')
    ? ranking.value
    : null
))
defineExpose({ refresh: loadOptions, exportableRanking })
onMounted(() => loadOptions())
onUnmounted(() => {
  optionsRequest?.abort()
  detailRequest?.abort()
})
</script>

<style scoped>
.batch-controls, .batch-details { padding: 1.25rem; margin-bottom: 1rem; }
.batch-details h2 { margin-bottom: .75rem; }
.table-container { overflow-x: auto; margin-top: 1rem; }
</style>
