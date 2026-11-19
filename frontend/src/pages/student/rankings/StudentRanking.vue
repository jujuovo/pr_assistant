<template>
  <section class="page-content student-personal-ranking">
    <header><h1>我的排名</h1><p>仅显示本人信息，不提供专业其他学生名单。</p></header>
    <form class="filters primary-section-frame" @submit.prevent="load">
      <label>排名批次 <input v-model.number="batchId" type="number" min="1" /></label>
      <button class="btn btn-outline">查看本人排名</button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <article v-if="ranking" class="personal-ranking-card">
      <h2>{{ statusLabel }}</h2>
      <p v-if="ranking.status === 'draft'">这是试算结果，尚未冻结或正式发布。</p>
      <p v-else-if="ranking.status === 'stale'">试算已经失效：{{ ranking.reason_code || '输入已变化' }}</p>
      <p v-else-if="ranking.status === 'frozen'">结果已冻结，尚未正式发布。</p>
      <dl>
        <dt>本人名次</dt><dd>{{ own?.rank ?? '-' }}</dd>
        <dt>排名总人数</dt><dd>{{ ranking.total_count }}</dd>
        <dt>本人分数</dt><dd>{{ own?.comprehensive_score ?? own?.reason_code ?? '-' }}</dd>
        <dt>排名范围</dt><dd>{{ JSON.stringify(ranking.scope) }}</dd>
        <dt>状态</dt><dd>{{ ranking.status }}</dd>
        <dt>生成时间</dt><dd>{{ ranking.generated_at || '-' }}</dd>
        <dt>发布时间</dt><dd>{{ ranking.published_at || '尚未发布' }}</dd>
      </dl>
    </article>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import workflowApi from '@/services/workflowApi.js'
const batchId = ref(null)
const ranking = ref(null)
const error = ref('')
const own = computed(() => ranking.value?.entries?.[0] || null)
const labels = { draft: '试算', stale: '试算已失效', frozen: '已冻结', published: '已正式发布', withdrawn: '已撤回', correction_required: '纠错中' }
const statusLabel = computed(() => labels[ranking.value?.status] || ranking.value?.status)
async function load() {
  try { error.value = ''; ranking.value = await workflowApi.getRanking(batchId.value) }
  catch (cause) { ranking.value = null; error.value = cause.message }
}
</script>
