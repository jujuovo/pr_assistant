<template>
  <section class="card policy-workspace">
    <div class="policy-heading">
      <h2>学院推免总规则</h2>
      <button v-if="!form" class="btn btn-primary" :disabled="busy" @click="open()">新建总规则</button>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="!form && loading">正在加载本学院规则…</p>
    <div v-else-if="!form && (!error || rows.length)" class="table-container">
      <table class="application-table policy-table">
        <thead><tr><th>推免周期</th><th>规则名称</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.cycle_code }} 届</td>
            <td>{{ row.title }}</td>
            <td><span class="policy-status">{{ statusLabel(row.status) }}</span></td>
            <td>
              <div class="row-actions">
                <button class="btn btn-outline" :disabled="busy" @click="open(row)">编辑</button>
                <button class="btn btn-outline" :disabled="busy" @click="open(row, true)">复制到下一届</button>
                <button class="btn btn-outline" :disabled="busy || row.status !== 'draft'"
                  @click="showPublishStatus(row)">{{ row.status === 'published' ? '已发布' : '发布' }}</button>
                <button class="btn btn-outline remove-action" :disabled="busy" @click="confirmDelete(row)">删除</button>
              </div>
            </td>
          </tr>
          <tr v-if="!rows.length"><td colspan="4">暂无学院推免总规则</td></tr>
        </tbody>
      </table>
    </div>
    <dialog ref="publishDialog" class="policy-dialog" aria-labelledby="publish-policy-title">
      <h3 id="publish-policy-title">发布推免规则</h3>
      <p>本次应用学业权重、两个分组上限及竞赛总项数。其他专项继续使用现有计分规则。</p>
      <p v-if="publishError" role="alert">{{ publishError }}</p>
      <template v-if="publication">
        <p>计分预览覆盖 {{ publication.material_count }} 份材料。</p>
        <table v-if="publication.score_changes.length" class="application-table">
          <thead><tr><th>学号</th><th>当前综合分</th><th>预计综合分</th></tr></thead>
          <tbody><tr v-for="item in publication.score_changes" :key="item.student_id">
            <td>{{ item.student_id }}</td><td>{{ item.before ?? '—' }}</td><td>{{ item.after }}</td>
          </tr></tbody>
        </table>
        <p v-else>本次预览没有需要更新的成绩快照。</p>
      </template>
      <div class="row-actions">
        <button class="btn btn-outline" :disabled="busy" @click="publishDialog.close()">取消</button>
        <button class="btn btn-primary" :disabled="busy || !publication" @click="publish">确认发布</button>
      </div>
    </dialog>
    <dialog ref="deleteDialog" class="policy-dialog" aria-labelledby="delete-policy-title" @close="deleting = null">
      <template v-if="deleting">
        <h3 id="delete-policy-title">删除推免规则</h3>
        <p>{{ deleting.cycle_code }} 届 · {{ deleting.title }}</p>
        <p v-if="deleting.status === 'published'">请先发布本学院、本届的替代版本，再删除当前正式版。</p>
        <p v-else>确认后，这份规则将从列表移除。</p>
        <p v-if="deleteError" role="alert">{{ deleteError }}</p>
        <div class="row-actions">
          <button class="btn btn-outline" :disabled="busy" @click="deleteDialog.close()">取消</button>
          <button class="btn btn-outline remove-action" :disabled="busy || deleting.status === 'published'"
            @click="removePolicy">确认删除</button>
        </div>
      </template>
    </dialog>
    <form v-if="form" novalidate @submit.prevent="save">
      <fieldset :disabled="busy || discardPrompt">
        <legend>{{ form.title || '新建总规则' }}</legend>
        <nav class="policy-tabs" aria-label="计分规则模块">
          <button v-for="group in groups" :key="group.title" type="button"
            class="btn" :class="activeGroup === group.title ? 'btn-primary' : 'btn-outline'"
            :aria-pressed="activeGroup === group.title" @click="activeGroup = group.title">
            {{ group.title }}
          </button>
        </nav>
        <section v-for="group in groups" v-show="activeGroup === group.title" :key="group.title" :data-policy-group="group.title" class="policy-panel">
          <h2>{{ group.title }}</h2>
          <div v-if="group.title === '整套规则'" class="policy-metadata">
            <label class="form-label">规则名称
              <input class="form-control" v-model.trim="form.title" required maxlength="120" />
            </label>
            <label class="form-label">推免周期
              <input class="form-control" v-model.number="form.cycle_code" type="number" required min="2000" max="2100" />
            </label>
          </div>
          <p v-if="group.title === '整套规则'">推免综合成绩 = 学业综合成绩 × 学业成绩权重 + 学术专长成绩 + 综合表现成绩</p>
          <PolicySectionEditor v-for="section in group.modules" :key="section.title"
            :title="section.title" :fields="section.fields" v-model="sections[section.title]"
            v-model:dirty="pendingJson[section.title]" />
        </section>
        <p v-if="hasPendingJson" role="status">请先应用或撤销各模块尚未应用的 JSON 编辑。</p>
        <p v-if="saveError" role="alert">{{ saveError }}</p>
        <div class="policy-actions">
          <button class="btn btn-primary" type="submit" :disabled="hasPendingJson || discardPrompt">
            {{ saving ? '正在保存…' : '保存草稿' }}
          </button>
          <button class="btn btn-outline" type="button" @click="close">返回版本列表</button>
        </div>
      </fieldset>
    </form>
    <section v-if="discardPrompt" class="discard-prompt" role="alertdialog" aria-label="放弃未保存修改">
      <p>本次修改尚未保存。返回版本列表会放弃这些修改。</p>
      <button type="button" @click="discardPrompt = false">继续编辑</button>
      <button type="button" @click="returnToList">放弃修改</button>
    </section>
    <slot v-if="form && activeGroup === '学术专长'" name="competition" />
    <slot v-if="form && activeGroup === '综合表现'" name="ordinary" />
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { requestJson } from '@/services/requestJson.js'

import PolicySectionEditor from '@/components/admin/rules/PolicySectionEditor.vue'

const numberField = (key, label, limits = {}) => ({ key, label, ...limits })
const groups = [
  { title: '整套规则', modules: [] },
  { title: '学业综合成绩', modules: [
    { title: '学业成绩计算', fields: [
      numberField('academic_score_weight', '学业成绩权重 (%)', { max: 100 }),
      numberField('retake_pass_score', '重修通过计分', { max: 100 })
    ] }
  ] },
  { title: '学术专长', modules: [
    { title: '学术专长封顶', fields: [
      numberField('specialty_max_score', '学术专长上限')
    ] },
    { title: '科研成果', fields: [
      numberField('paper_category_c_max_count', 'C 类论文最多篇数', { integer: true }),
      numberField('invention_patent_score', '授权发明专利基础分')
    ] },
    { title: '学科竞赛', fields: [
      numberField('competition_max_count', '全部竞赛最多计入项目数（项）', { integer: true }),
      numberField('external_competition_max_count', '非信息学院项目最多计入数', { integer: true })
    ] },
    { title: '创新创业训练', fields: [numberField('max_score', '累计分数上限（分）')] }
  ] },
  { title: '综合表现', modules: [
    { title: '综合表现封顶', fields: [numberField('performance_max_score', '综合表现上限')] },
    ...['国际组织实习', '参军服役', '志愿工时', '志愿表彰', '荣誉称号', '社会工作'].map(title => ({
      title, fields: [numberField('max_score', '累计分数上限（分）')]
    })),
    { title: '体育比赛', fields: [numberField('national_champion_team_score', '国家级团体冠军基础分')] }
  ] }
]
const modules = groups.flatMap(group => group.modules)
const activeGroup = ref('整套规则')
const discardPrompt = ref(false)
let initialState = ''

const endpoint = '/api/faculty-scoring-policies'
const emit = defineEmits(['editing'])
const rows = ref([])
const deleteDialog = ref(null)
const deleting = ref(null)
const deleteError = ref('')

function statusLabel(status) {
  return { draft: '草稿', published: '正式版', retired: '已退役' }[status] || status
}

const publishDialog = ref(null)
const publication = ref(null)
const publishError = ref('')

async function showPublishStatus(row) {
  publication.value = null
  publishError.value = ''
  publishDialog.value.showModal()
  busy.value = true
  try {
    publication.value = await requestJson(endpoint + '/' + row.id + '/publication-preview')
  } catch (e) {
    publishError.value = e.message
  } finally {
    busy.value = false
  }
}

async function publish() {
  if (busy.value || !publication.value) return
  busy.value = true
  try {
    await requestJson(endpoint + '/' + publication.value.policy_id + '/publish', {
      method: 'POST', data: { digest: publication.value.digest }
    })
    publishDialog.value.close()
    await load()
    notice.value = '规则已发布'
  } catch (e) {
    publishError.value = e.message
    publication.value = null
  } finally {
    busy.value = false
  }
}

function confirmDelete(row) {
  deleting.value = row
  deleteError.value = ''
  deleteDialog.value.showModal()
}

async function removePolicy() {
  if (busy.value || !deleting.value || deleting.value.status === 'published') return
  const id = deleting.value.id
  busy.value = true
  try {
    await requestJson(endpoint + '/' + id, { method: 'DELETE' })
    rows.value = rows.value.filter(row => row.id !== id)
    deleteDialog.value.close()
    notice.value = '规则已删除'
  } catch (e) {
    deleteError.value = e.status === 405
      ? '当前后端未加载删除接口。重启后端后，请重新打开页面再试。'
      : e.message
  } finally {
    busy.value = false
  }
}
const form = ref(null)
watch(() => Boolean(form.value), editing => emit('editing', editing))
const sections = ref({})
const pendingJson = ref({})
const hasPendingJson = computed(() => Object.values(pendingJson.value).some(Boolean))
const error = ref('')
const notice = ref('')
const busy = ref(false)
const saving = ref(false)
const saveError = ref('')
const loading = ref(true)

async function load() {
  try {
    rows.value = (await requestJson(endpoint)).items
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function open(row, nextCycle = false) {
  notice.value = error.value = saveError.value = ''
  const editing = row?.status === 'draft' && !nextCycle
  form.value = {
    id: editing ? row.id : null,
    revision: editing ? row.revision : null,
    source_id: editing ? row.source_id : row?.id,
    title: row?.title || '',
    cycle_code: row ? row.cycle_code + Number(nextCycle) : null
  }
  const existing = row?.sections ?? {
    总分计算: {}, 学科竞赛: {}, 志愿服务: {}, 科研成果: {}, 创新创业训练: {}, 学生干部: {}, 普通规则: {}
  }
  sections.value = JSON.parse(JSON.stringify(existing))
  for (const { title } of modules) sections.value[title] ??= {}
  const totals = sections.value['总分计算'] ?? {}
  for (const [title, key] of [
    ['学业成绩计算', 'academic_score_weight'],
    ['学术专长封顶', 'specialty_max_score'],
    ['综合表现封顶', 'performance_max_score']
  ]) {
    if (!Object.hasOwn(sections.value[title], key) && Object.hasOwn(totals, key)) {
      sections.value[title][key] = totals[key]
    }
  }
  pendingJson.value = {}
  activeGroup.value = '整套规则'
  discardPrompt.value = false
  initialState = editingState()
}

function editingState() {
  return JSON.stringify([form.value, sections.value])
}

function close() {
  if (hasPendingJson.value || editingState() !== initialState) {
    discardPrompt.value = true
    return
  }
  returnToList()
}

function returnToList() {
  discardPrompt.value = false
  form.value = null
  error.value = ''
}

async function save(event) {
  if (busy.value || hasPendingJson.value) return
  saveError.value = ''
  const invalid = Array.from(event.currentTarget.elements).find(
    element => element.willValidate && !element.validity.valid
  )
  if (invalid) {
    const panel = invalid.closest('[data-policy-group]')
    if (panel) activeGroup.value = panel.dataset.policyGroup
    const field = invalid.labels?.[0]?.textContent.trim()
    saveError.value = [panel?.dataset.policyGroup, field, invalid.validationMessage]
      .filter(Boolean).join(' · ')
    await nextTick()
    invalid.focus()
    return
  }
  busy.value = saving.value = true
  error.value = notice.value = ''
  try {
    const { id, ...data } = form.value
    const saved = await requestJson(id ? endpoint + '/' + id : endpoint, {
      method: id ? 'PUT' : 'POST', data: { ...data, sections: sections.value }
    })
    rows.value = [saved, ...rows.value.filter(row => row.id !== saved.id)]
    form.value = null
    notice.value = '草稿已保存'
  } catch (e) {
    saveError.value = `草稿保存失败：${e.message}`
  } finally {
    busy.value = saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.policy-workspace { padding: clamp(1rem, 3vw, 2.25rem); margin-bottom: 1.5rem; }
fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }
legend { margin-bottom: 1.25rem; font-size: 1.2rem; font-weight: 600; }
.policy-tabs, .policy-actions { display: flex; flex-wrap: wrap; gap: .75rem; }
.policy-panel { margin: 1.5rem 0; }
.policy-metadata {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));
  gap: 1.25rem;
  margin: 1.25rem 0;
}
.policy-actions { border-top: 1px solid #dce5ef; padding-top: 1.25rem; }
.policy-heading, .row-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; }
.policy-heading { justify-content: space-between; margin-bottom: 1.25rem; }
.policy-heading h2 { margin: 0; }
.table-container { overflow-x: auto; }
.policy-table { width: 100%; }
.policy-table th, .policy-table td { padding: .9rem 1rem; text-align: left; }
.policy-status { display: inline-block; padding: .3rem .65rem; border-radius: .45rem; background: #edf4fb; }
.remove-action { color: #b42318; }
.policy-dialog { position: fixed; inset: 0; margin: auto; max-height: calc(100dvh - 2rem); overflow: auto; background: #fff; width: min(32rem, calc(100% - 2rem)); border: 1px solid #dce5ef; border-radius: .85rem; padding: 1.5rem; }
.policy-dialog::backdrop { background: rgb(10 28 48 / 45%); }
</style>
