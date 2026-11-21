<template>
  <section class="page-content material-submission"
    ><h1>提交{{ names[category] || '证明材料' }}</h1>
    <label v-if="!route.query.editId && ['research_paper','invention_patent'].includes(category)">材料类型<select :value="category" @change="router.replace({query:{page:'materials', category:$event.target.value}})"><option value="research_paper">论文</option><option value="invention_patent">授权发明专利</option></select></label>
    <CompetitionWorkflow v-if="category === 'competition'" />
    <template v-else
      ><p v-if="category === 'volunteer'">{{
        category === 'volunteer'
          ? '上传本次工时证明后，系统在后台比对工时、工时类别和服务记录日期。信用、荣誉截图均按普通志愿服务，分别采用签退日期、录入日期。一致后可正式提交教师审核；不一致或无法识别会打回，支持申诉转人工审核。'
          : '按原件手动填写，本通道由教师人工核验，不自动计分。'
      }}</p>
      <p v-if="loading" role="status">正在加载草稿…</p
      ><p v-if="error" role="alert">{{ error }} <button @click="loadEdit">重试</button></p>
      <form v-if="editing" @submit.prevent="saveEdit"
        ><h2>修改材料 #{{ editing.id }}</h2
        ><PolicyMaterialFields v-if="['research_paper', 'invention_patent', 'innovation_training'].includes(category)" v-model="editData" :category="category" />
        <MaterialFieldsEditor
          v-else
          v-model="editData"
          :labels="category === 'volunteer' ? { award_date: '服务记录日期' } : {}"
        /><MaterialImagePreview :attachments="editing.attachments || []" /><p v-if="editing.attachments?.length">原件已保留。</p><label v-else>请上传本版本的证明原件<input type="file" multiple required @change="files = Array.from($event.target.files)" /></label
        ><button class="btn btn-primary" :disabled="busy">{{
          busy ? '保存中…' : '保存修改'
        }}</button></form
      >
      <ManualMaterialDraft v-else-if="!route.query.editId" :category="category" @saved="saved" />
      <p v-if="notice" role="status">{{ notice }}</p
      ><button class="btn btn-outline" @click="history">前往我的材料查看进度</button></template
    ></section
  >
</template>
<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import materialApi from '@/services/materialApi.js'
import CompetitionWorkflow from './CompetitionWorkflow.vue'
import ManualMaterialDraft from '@/components/student/ManualMaterialDraft.vue'
import PolicyMaterialFields from '@/components/common/PolicyMaterialFields.vue'
import MaterialFieldsEditor from '@/components/common/MaterialFieldsEditor.vue'
import MaterialImagePreview from '@/components/common/MaterialImagePreview.vue'
const files=ref([])
const route = useRoute(),
  router = useRouter(),
  categories = [
    'competition',
    'research_paper', 'invention_patent', 'innovation_training',
    'competition_evidence',
    'certification',
    'social_practice',
    'research',
    'student_work',
    'volunteer'
  ]
if (route.query.editId) categories.push('academic', 'language', 'honor')
const category = ref(
    categories.includes(route.query.category) ? route.query.category : 'competition'
  ),
  error = ref(''),
  notice = ref(''),
  loading = ref(false),
  busy = ref(false),
  editing = ref(null),
  editData = ref({})
const names = {
  research_paper: '学术论文', invention_patent: '授权发明专利', innovation_training: '创业创新',
  volunteer: '志愿服务累计工时',
  academic: '学业成绩',
  language: '外语能力',
  honor: '荣誉称号',
  competition: '正式竞赛',
  student_work: '学生工作',
  certification: '能力认证',
  social_practice: '社会实践',
  research: '成果检索报告',
  competition_evidence: '目录外竞赛材料'
}
function history() {
  router.replace({ query: { page: 'application-record' } })
}
async function loadEdit() {
  if (category.value === 'competition' || !route.query.editId) return
  loading.value = true
  error.value = ''
  try {
    const row = await materialApi.getRecord(category.value, route.query.editId)
    if (!row.allowed_actions?.includes('edit'))
      throw new Error('此材料当前不可编辑，请返回我的材料查看最新状态。')
    editing.value = row
    editData.value = JSON.parse(JSON.stringify(row.data))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function saveEdit() {
  if (busy.value) return
  busy.value = true
  try {
    const updated = await materialApi.updateRecord(
      category.value,
      editing.value.id,
      editing.value.version,
      editData.value
    )
    editing.value = updated
    if(files.value.length) editing.value = await materialApi.uploadAttachments(category.value,updated.id,updated.version,files.value)
    if (category.value === 'volunteer')
      await materialApi.startVolunteerOcr(updated.id, updated.version)
    history()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function saved() {
  notice.value =
    '草稿和原件已保存。已适配材料会在后台识别，可继续填写下一项，或前往我的材料查看进度。'
}
watch(
  () => route.query.category,
  async (value) => {
    category.value = categories.includes(value) ? value : 'competition'
    editing.value = null
    editData.value = {}
    error.value = ''
    notice.value = ''
    await loadEdit()
  }
)
onMounted(() => {
  if(route.query.category==='research' && !route.query.editId) return router.replace({query:{page:'application-categories'}})
  return loadEdit()
})
</script>
<style scoped>
.material-submission {
  display: grid;
  gap: 20px;
}
.material-submission > label {
  display: flex;
  gap: 16px;
  align-items: center;
}
.material-submission select {
  padding: 10px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
.material-submission form {
  padding: 20px;
  background: white;
  border: 1px solid #dce5ef;
  border-radius: 12px;
}
.btn {
  justify-self: start;
}
</style>
