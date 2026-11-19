<template><section class="page-content"><h1>竞赛规则包</h1>
  <p>正式包不可编辑；下一届规则必须复制为草稿，经差异预览和完整校验后整体发布。</p>
  <p v-if="error" role="alert">{{ error }}</p>
  <button @click="load">刷新</button>
  <table><thead><tr><th>周期</th><th>状态</th><th>版本</th><th>来源</th><th>操作</th></tr></thead><tbody>
    <tr v-for="row in items" :key="row.id"><td>{{ row.cycle_code }}</td><td>{{ row.status }}</td>
      <td>v{{ row.version }} / draft r{{ row.draft_revision }}</td><td>{{ row.source_summary?.package_id || '-' }}</td>
      <td><button v-if="row.allowed_actions.includes('copy')" @click="copyToNext(row)">复制上一届</button>
        <button v-if="row.allowed_actions.includes('edit')" @click="selectDraft(row)">编辑草稿</button>
        <button v-if="row.allowed_actions.includes('diff')" @click="showDiff(row)">查看差异</button>
        <button v-if="row.allowed_actions.includes('validate')" @click="validateDraft(row)">校验</button>
        <button v-if="row.allowed_actions.includes('publish')" @click="publishDraft(row)">确认发布</button></td></tr>
  </tbody></table>
  <section v-if="draft"><h2>编辑 {{ draft.package_id }}</h2><textarea v-model="snapshotText" rows="16"></textarea>
    <button @click="saveDraft">保存 revision</button></section>
  <pre v-if="preview">{{ JSON.stringify(preview, null, 2) }}</pre>
</section></template>
<script setup>
import { onMounted, ref } from 'vue'
import api from '@/services/competitionRulePackageApi.js'
import { workflowErrorMessage } from '@/services/workflowPresentation.js'
const items=ref([]),draft=ref(null),snapshotText=ref(''),preview=ref(null),error=ref('')
const key=prefix=>`${prefix}-${crypto.randomUUID()}`
async function run(fn){try{error.value='';return await fn()}catch(e){error.value=workflowErrorMessage(e);throw e}}
async function load(){const result=await run(()=>api.list());items.value=result.items||[]}
async function copyToNext(row){await run(()=>api.copy(row.id,row.cycle_code+1,key('copy')));await load()}
function selectDraft(row){draft.value=row;snapshotText.value=JSON.stringify(row.snapshot,null,2)}
async function saveDraft(){const snapshot=JSON.parse(snapshotText.value);draft.value=await run(()=>api.edit(draft.value.id,draft.value.draft_revision,snapshot));await load()}
async function showDiff(row){preview.value=await run(()=>api.diff(row.id))}
async function validateDraft(row){preview.value=await run(()=>api.validate(row.id))}
async function publishDraft(row){preview.value=await run(()=>api.publish(row.id,row.draft_revision,key('publish')));await load()}
onMounted(load)
</script>
