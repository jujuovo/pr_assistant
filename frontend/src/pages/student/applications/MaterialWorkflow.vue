<template><section class="page-content"><h1>证明材料</h1><label>类别 <select v-model="category" @change="load"><option v-for="x in categories" :key="x" :value="x">{{ x }}</option></select></label>
<CompetitionWorkflow v-if="category==='competition'" />
<template v-else>
<p v-if="error" role="alert">{{ error }}</p><article v-for="row in records" :key="row.id"><h2>#{{ row.id }} · {{ row.status }}</h2>
<p>版本 {{ row.version }}；可执行：{{ (row.allowed_actions||[]).join('、') || '无' }}</p>
<button v-if="row.allowed_actions?.includes('submit')" @click="act(row,'submit')">提交</button>
<button v-if="row.allowed_actions?.includes('withdraw')" @click="act(row,'withdraw')">撤回</button>
<button v-if="row.allowed_actions?.includes('resubmit')" @click="act(row,'submit')">补正后重交</button>
<button @click="recognize(row)">辅助识别</button></article></template></section></template>
<script setup>import {ref,onMounted} from 'vue'; import {useRoute,useRouter} from 'vue-router'; import materialApi,{MATERIAL_CATEGORIES} from '@/services/materialApi.js'; import CompetitionWorkflow from './CompetitionWorkflow.vue'
const route=useRoute(),router=useRouter(),categories=MATERIAL_CATEGORIES,category=ref(route.query.category||categories[0]),records=ref([]),error=ref('')
async function load(){
  error.value=''
  router.replace({query:{...route.query,page:'materials',category:category.value}})
  if(category.value==='competition'){
    records.value=[]
    return
  }
  const data=await materialApi.listRecords(category.value)
  records.value=data.records||data.items||[]
}
async function act(row,action){try{await materialApi[action](category.value,row.id,row.version);await load()}catch(e){error.value=e.status===409?'材料版本已变化，请刷新后重试':e.message}}
async function recognize(row){try{await materialApi.recognize(category.value,row.id)}catch(e){error.value=e.status===501?'辅助识别暂不可用，请直接查看原件并人工处理':e.message}}
onMounted(load)</script>
