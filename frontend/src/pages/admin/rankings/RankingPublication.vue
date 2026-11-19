<template><section class="page-content"><h1>排名发布</h1>
  <form @submit.prevent="generate"><label>周期 <input v-model.number="form.year" type="number"></label>
    <label>专业 ID <input v-model.number="form.major_id" type="number"></label>
    <label>截止时间 <input v-model="form.cutoff_at" type="datetime-local"></label><button>生成 draft</button></form>
  <form @submit.prevent="load"><label>批次 ID <input v-model.number="batchId" type="number"></label><button>查看</button></form>
  <p v-if="error" role="alert">{{ error }}</p>
  <article v-if="batch"><h2>{{ batch.status }} · v{{ batch.version }}</h2><p>范围：{{ JSON.stringify(batch.scope) }}</p>
    <ul v-if="batch.blockers?.length"><li v-for="item in batch.blockers" :key="JSON.stringify(item)">{{ item.type }}：{{ item.reason }}</li></ul>
    <button v-for="action in commandActions" :key="action" @click="command(action)">{{ labels[action] }}</button>
    <table><thead><tr><th>学号</th><th>分数</th><th>名次</th><th>依据</th></tr></thead><tbody>
      <tr v-for="row in batch.entries" :key="row.student_id"><td>{{ row.student_id }}</td><td>{{ row.comprehensive_score }}</td><td>{{ row.rank }}</td><td>{{ row.reason_code || '-' }}</td></tr>
    </tbody></table></article>
</section></template>
<script setup>
import { computed, reactive, ref } from 'vue'
import workflowApi from '@/services/workflowApi.js'
import { workflowErrorMessage } from '@/services/workflowPresentation.js'
const form=reactive({year:2029,major_id:null,cutoff_at:''}),batchId=ref(null),batch=ref(null),error=ref('')
const labels={freeze:'冻结',request_correction:'解冻纠错',publish:'发布',withdraw:'撤回',create_successor:'创建后继版本'}
const commandActions=computed(()=>(batch.value?.allowed_actions||[]).filter(action=>labels[action]))
const key=action=>`${action}-${crypto.randomUUID()}`
async function load(){try{batch.value=await workflowApi.getRanking(batchId.value)}catch(e){error.value=workflowErrorMessage(e)}}
async function generate(){try{batch.value=await workflowApi.generateRanking({...form,precision:4,idempotency_key:key('generate')});batchId.value=batch.value.batch_id}catch(e){error.value=workflowErrorMessage(e)}}
async function command(action){try{const data={};if(['request_correction','withdraw'].includes(action))data.reason=prompt('请输入理由')||'';batch.value=await workflowApi.rankingCommand(batch.value.batch_id,action,batch.value.version,key(action),data)}catch(e){error.value=workflowErrorMessage(e)}}
</script>
