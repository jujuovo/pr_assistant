<template>
  <section class="page-content material-submission"
    ><h1>提交证明材料</h1>
    <label
      >材料类别<select v-model="category" @change="changeCategory"
        ><option v-for="x in categories" :key="x" :value="x">{{ names[x] }}</option></select
      ></label
    >
    <CompetitionWorkflow v-if="category === 'competition'" />
    <template v-else
      ><p>按原件手动填写，本通道由教师人工核验，不自动计分。</p>
      <p v-if="loading" role="status">正在加载草稿…</p
      ><p v-if="error" role="alert">{{ error }} <button @click="loadEdit">重试</button></p>
      <form v-if="editing" @submit.prevent="saveEdit"
        ><h2>修改材料 #{{ editing.id }}</h2
        ><MaterialFieldsEditor v-model="editData" /><p>原件已保留，无须重复上传。</p
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
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import materialApi from '@/services/materialApi.js'
import CompetitionWorkflow from './CompetitionWorkflow.vue'
import ManualMaterialDraft from '@/components/student/ManualMaterialDraft.vue'
import MaterialFieldsEditor from '@/components/common/MaterialFieldsEditor.vue'
const route = useRoute(),
  router = useRouter(),
  categories = [
    'competition',
    'competition_evidence',
    'certification',
    'social_practice',
    'research',
    'student_work'
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
function changeCategory() {
  router.replace({ query: { page: 'materials', category: category.value } })
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
    await materialApi.updateRecord(
      category.value,
      editing.value.id,
      editing.value.version,
      editData.value
    )
    history()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function saved() {
  notice.value = '草稿和原件已保存。可继续填写下一项，或前往我的材料正式提交。'
}
onMounted(loadEdit)
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
