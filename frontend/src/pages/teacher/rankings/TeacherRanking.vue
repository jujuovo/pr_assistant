<template>
  <section class="page-content teacher-ranking">
    <div class="page-title"><span>专业排名（只读）</span></div>
    <form class="filters primary-section-frame" @submit.prevent="load">
      <label>批次编号 <input v-model.number="batchId" type="number" min="1" /></label>
      <button class="btn btn-outline">查看授权排名</button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <article v-if="ranking">
      <h2>{{ ranking.status }}</h2>
      <p>范围：{{ JSON.stringify(ranking.scope) }}；版本：{{ ranking.version }}；生成：{{ ranking.generated_at }}；发布：{{ ranking.published_at || '尚未发布' }}</p>
      <p v-if="ranking.status === 'stale'">失效原因：{{ ranking.reason_code }}</p>
      <table class="application-table"><thead><tr><th>学号</th><th>分数</th><th>名次</th><th>项目依据</th></tr></thead>
        <tbody><tr v-for="row in ranking.entries" :key="row.student_id">
          <td>{{ row.student_id }}</td><td>{{ row.comprehensive_score ?? row.reason_code }}</td>
          <td>{{ row.rank ?? '-' }}</td><td><pre>{{ JSON.stringify(row.score_basis, null, 2) }}</pre></td>
        </tr></tbody>
      </table>
      <p>教师权限：完整名单只读。批次状态操作仅由管理员执行。</p>
    </article>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import workflowApi from '@/services/workflowApi.js'
const batchId = ref(null)
const ranking = ref(null)
const error = ref('')
async function load() {
  try { error.value = ''; ranking.value = await workflowApi.getRanking(batchId.value) }
  catch (cause) { ranking.value = null; error.value = cause.message }
}
</script>
