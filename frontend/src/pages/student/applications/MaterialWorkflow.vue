<template><section class="page-content material-workflow"><h1>证明材料</h1><label>材料类别<select v-model="category" @change="load"><option v-for="x in categories" :key="x" :value="x">{{names[x]||x}}</option></select></label>
<CompetitionWorkflow v-if="category==='competition'" :ocr-job-id="route.query.ocrJobId" />
<template v-else><OcrMaterialDraft @saved="saved" @competition="competition"/><ManualMaterialDraft v-if="['competition_evidence','certification','social_practice','research','student_work'].includes(category)" :category="category" @saved="saved"/><p v-if="loading" role="status">正在加载材料…</p><p v-if="error" role="alert">{{error}} <button @click="load">重新加载</button></p><p v-if="!loading&&!records.length">此类别暂无材料。您可以先上传证书辅助填写。</p>
<article v-for="row in records" :key="row.id" class="material-record"><h2>材料 #{{row.id}} · {{statusName(row.status)}}</h2><MaterialFacts :data="row.data"/><p v-if="row.manual_only">此通道仅核验材料，不自动计分。正式目录内竞赛请使用竞赛申报。</p>
<template v-if="editing===row.id"><MaterialFieldsEditor v-model="editData"/><button class="btn btn-primary" :disabled="busy" @click="saveEdit(row)">保存修改</button><button class="btn btn-outline" @click="editing=null">取消</button></template>
<template v-else><button v-if="row.allowed_actions?.includes('edit')" class="btn btn-outline" @click="edit(row)">修改字段</button><button v-if="row.allowed_actions?.includes('submit')" class="btn btn-primary" :disabled="busy" @click="act(row,'submit')">提交人工核验</button><button v-if="row.allowed_actions?.includes('withdraw')" class="btn btn-outline" :disabled="busy" @click="act(row,'withdraw')">撤回</button></template>
<ul><li v-for="file in row.attachments" :key="file.id"><a :href="file.url" target="_blank" rel="noopener">{{file.filename}}</a></li></ul>
<details v-if="row.ocr_links?.length"><summary>原始识别与首次确认记录</summary><section v-for="link in row.ocr_links" :key="link.job_id"><MaterialFacts :data="link.suggestions.data"/><a :href="link.artifact_urls.original" target="_blank" rel="noopener">查看识别原图</a></section></details>
</article></template></section></template>
<script setup>
import { ref,onMounted } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import materialApi,{MATERIAL_CATEGORIES} from '@/services/materialApi.js'
import CompetitionWorkflow from './CompetitionWorkflow.vue'
import OcrMaterialDraft from '@/components/student/OcrMaterialDraft.vue'
import ManualMaterialDraft from '@/components/student/ManualMaterialDraft.vue'
import MaterialFacts from '@/components/common/MaterialFacts.vue'
import MaterialFieldsEditor from '@/components/common/MaterialFieldsEditor.vue'
const route=useRoute(),router=useRouter(),categories=MATERIAL_CATEGORIES,category=ref(route.query.category||categories[0]),records=ref([]),error=ref(''),loading=ref(false),busy=ref(false),editing=ref(null),editData=ref({})
const names={academic:'学业成绩',competition:'正式竞赛',language:'外语能力',student_work:'学生工作',honor:'荣誉称号',certification:'认证成绩',social_practice:'社会实践',research:'成果检索报告',competition_evidence:'目录外竞赛材料'}
const statusName=value=>({draft:'草稿',submitted:'待核验',verified:'已核验',rejected:'未通过',needs_correction:'待补充'})[value]||value
async function load(){error.value='';router.replace({query:{...route.query,page:'materials',category:category.value}});if(category.value==='competition'){records.value=[];return}loading.value=true;try{records.value=(await materialApi.listRecords(category.value)).records||[]}catch(e){error.value=e.message}finally{loading.value=false}}
async function act(row,action){busy.value=true;try{await materialApi[action](category.value,row.id,row.version);await load()}catch(e){error.value=e.message}finally{busy.value=false}}
function edit(row){editing.value=row.id;editData.value=JSON.parse(JSON.stringify(row.data))}
async function saveEdit(row){busy.value=true;try{await materialApi.updateRecord(category.value,row.id,row.version,editData.value);editing.value=null;await load()}catch(e){error.value=e.message}finally{busy.value=false}}
async function saved(row){category.value=row.category;await load()}
function competition(jobId){category.value='competition';router.replace({query:{...route.query,page:'materials',category:'competition',ocrJobId:jobId}})}
onMounted(load)
</script>
<style scoped>.material-workflow{display:grid;gap:18px}.material-workflow>label{display:flex;gap:12px;align-items:center}.material-workflow select{padding:10px;border:1px solid #b9c7d8;border-radius:7px}.material-record{padding:20px;border:1px solid #dce5ef;border-radius:12px;background:white}.material-record button{margin:6px}</style>
