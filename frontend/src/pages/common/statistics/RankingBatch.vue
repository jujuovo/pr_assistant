<template><section class="page-content"><h1>排名批次</h1>
  <form @submit.prevent="load"><label>批次编号 <input v-model.number="batchId" type="number" min="1"></label><button>查看</button></form>
  <p v-if="error" role="alert">{{ error.message || error }}</p>
  <article v-if="ranking"><h2>{{ statusText }}</h2>
    <p>范围：{{ JSON.stringify(ranking.scope) }}；生成：{{ ranking.generated_at }}；发布：{{ ranking.published_at || '尚未发布' }}</p>
    <p v-if="ranking.status === 'stale'">数据已变化：{{ ranking.stale_reason }}</p>
    <table><thead><tr><th>学号</th><th>综合成绩</th><th>名次</th></tr></thead><tbody>
      <tr v-for="row in ranking.entries" :key="row.student_id"><td>{{ row.student_id }}</td><td>{{ row.comprehensive_score ?? row.exclusion_reason }}</td><td>{{ row.rank ?? '-' }}</td></tr>
    </tbody></table></article></section></template>
<script setup>import { ref, computed, onMounted } from 'vue'; import { useRoute, useRouter } from 'vue-router'; import { useWorkflowStore } from '@/stores/workflow.js'
const route=useRoute(), router=useRouter(), store=useWorkflowStore(); const batchId=ref(Number(route.query.batch_id)||null)
const ranking=computed(()=>store.ranking), error=computed(()=>store.error)
const labels={draft:'试算',stale:'试算已过期',frozen:'已冻结',published:'正式发布',withdrawn:'已撤回'}
const statusText=computed(()=>labels[ranking.value?.status]||'')
async function load(){if(!batchId.value)return; await router.replace({query:{...route.query,page:'rankings',batch_id:String(batchId.value)}}); await store.loadRanking(batchId.value)}
onMounted(()=>{if(batchId.value)load()})</script>
