<template>
  <section class="competition-flow" aria-labelledby="competition-title">
    <header class="card hero"
      ><div
        ><p class="eyebrow">证明材料 · 学业竞赛</p><h2 id="competition-title">学业竞赛申报</h2
        ><p
          >按证书手动填写申报信息。OCR在保存后后台运行，用于核对与预估分数，不会替您填写字段。</p
        ></div
      ><button
        class="btn btn-outline"
        type="button"
        data-test="refresh-records"
        :disabled="!context || savingDraft"
        @click="retry"
        >刷新申报目录</button
      ></header
    >
    <p
      v-if="pageState.kind === 'loading'"
      class="state-panel"
      role="status"
      aria-live="polite"
      data-state="loading"
      >正在加载竞赛周期与正式规则包…</p
    >
    <section
      v-else-if="pageState.kind !== 'ready'"
      class="state-panel"
      :class="`state-${pageState.kind}`"
      role="alert"
      :data-state="pageState.kind"
      ><div
        ><h3>{{ stateTitle }}</h3
        ><p>{{ pageState.message }}</p></div
      ><button
        v-if="pageState.kind !== 'validation'"
        class="btn btn-outline"
        type="button"
        @click="retry"
        >重新加载</button
      ></section
    >
    <section v-if="context" class="card context-card" aria-label="当前竞赛政策"
      ><div
        ><span>申报周期</span
        ><strong>{{ context.cycle.display_name || context.cycle.cycle_code }}</strong></div
      ><div
        ><span>规则包</span
        ><strong
          >{{ context.rule_package?.package_id || '正式规则包' }} · v{{
            context.rule_package?.version
          }}</strong
        ></div
      ><div
        ><span>证据有效期</span
        ><strong
          >{{ context.evidence_period?.start }} — {{ context.evidence_period?.end }}</strong
        ></div
      ><div
        ><span>正式目录</span
        ><strong>{{ context.catalog?.count ?? catalog.length }} 项</strong></div
      ></section
    >
    <div v-if="context" class="layout">
      <main class="main-column">
        <section class="card workflow-section"
          ><Heading step="1" title="选择正式竞赛" hint="搜索结果来自当前规则包，分类不可修改。" />
          <div class="catalog-controls"
            ><label for="competition-search">搜索正式竞赛 <small>按名称查找</small></label
            ><input
              id="competition-search"
              v-model.trim="query"
              class="form-control"
              type="search"
              placeholder="例如：中国大学生计算机设计大赛"
              @input="scheduleSearch"
            /><label for="competition-select">目录条目 *</label
            ><select
              id="competition-select"
              v-model="form.competition_id"
              class="form-control"
              required
              @change="selectCompetition"
              :aria-invalid="Boolean(fieldErrors.competition_id)"
              :aria-describedby="
                fieldErrors.competition_id ? 'competition-select-error' : undefined
              "
              ><option value="">请选择正式目录条目</option
              ><option
                v-for="item in catalog"
                :key="item.competition_id"
                :value="item.competition_id"
                >{{ item.name }}</option
              ></select
            ><span></span
            ><small
              v-if="fieldErrors.competition_id"
              id="competition-select-error"
              class="field-error"
              >{{ fieldErrors.competition_id }}</small
            ></div
          >
          <p
            v-if="pageState.kind === 'ready' && query && !searchLoading && !catalog.length"
            class="inline-empty"
            role="status"
            data-state="search-empty"
            >正式目录无匹配结果，请修改搜索词。</p
          ><div v-if="selected" class="authority"
            ><span>计分分类</span><strong>{{ selected.category }}</strong
            ><span>申报方式</span><strong>手动填写 · 后台识别</strong></div
          >
        </section>

        <form class="card workflow-section" novalidate @submit.prevent="validateAndSaveDraft"
          ><Heading step="2" title="填写材料事实" hint="带 * 的字段必填，请按证明原件填写。" />
          <p v-if="editingRecord" class="editing-notice" role="status" data-test="editing-notice"
            >正在编辑草稿“{{ editingRecord.data?.project_name }}”（版本
            {{ editingRecord.version }}）。保存将更新此草稿，不会新建重复材料。
            <button class="btn btn-outline" type="button" @click="cancelEditing"
              >取消编辑</button
            ></p
          >
          <section
            v-if="Object.keys(fieldErrors).length"
            class="error-summary"
            role="alert"
            tabindex="-1"
            ref="errorSummary"
            aria-labelledby="error-summary-title"
            ><h4 id="error-summary-title">请修正以下字段</h4
            ><ul
              ><li v-for="(message, key) in fieldErrors" :key="key"
                ><button type="button" @click="focusField(key)">{{ message }}</button></li
              ></ul
            ></section
          >
          <div class="form-grid">
            <label class="field wide" for="project-name"
              >项目名称 *<input
                id="project-name"
                v-model.trim="form.project_name"
                class="form-control"
                required
                :aria-invalid="Boolean(fieldErrors.project_name)"
                :aria-describedby="fieldErrors.project_name ? 'project-name-error' : undefined"
              /><small
                v-if="fieldErrors.project_name"
                id="project-name-error"
                class="field-error"
                >{{ fieldErrors.project_name }}</small
              ></label
            >
            <label class="field" for="award-date"
              >获奖日期 *<input
                id="award-date"
                v-model="form.award_date"
                class="form-control"
                type="date"
                required
                :aria-invalid="Boolean(fieldErrors.award_date)"
                :aria-describedby="fieldErrors.award_date ? 'award-date-error' : undefined"
              /><small v-if="fieldErrors.award_date" id="award-date-error" class="field-error">{{
                fieldErrors.award_date
              }}</small></label
            >
            <label class="field" for="event-year"
              >赛事年份 *<input
                id="event-year"
                v-model="form.event_year"
                class="form-control"
                type="number"
                min="2000"
                max="2100"
                required
                :aria-invalid="Boolean(fieldErrors.event_year)"
                :aria-describedby="fieldErrors.event_year ? 'event-year-error' : undefined"
              /><small v-if="fieldErrors.event_year" id="event-year-error" class="field-error">{{
                fieldErrors.event_year
              }}</small></label
            >
            <label class="field" for="level"
              >获奖级别 *<select
                id="level"
                v-model="form.level"
                class="form-control"
                required
                :aria-invalid="Boolean(fieldErrors.level)"
                :aria-describedby="fieldErrors.level ? 'level-error' : undefined"
                ><option value="">请选择</option
                ><option v-for="x in options.levels" :key="x" :value="x">{{
                  displayValue(x)
                }}</option></select
              ><small v-if="fieldErrors.level" id="level-error" class="field-error">{{
                fieldErrors.level
              }}</small></label
            >
            <label class="field" for="award"
              >奖项 *<select
                id="award"
                v-model="form.award"
                class="form-control"
                required
                :aria-invalid="Boolean(fieldErrors.award)"
                :aria-describedby="fieldErrors.award ? 'award-error' : undefined"
                ><option value="">请选择</option
                ><option v-for="x in options.awards" :key="x" :value="x">{{
                  displayValue(x)
                }}</option></select
              ><small v-if="fieldErrors.award" id="award-error" class="field-error">{{
                fieldErrors.award
              }}</small></label
            >
            <label class="field" for="mode"
              >参赛方式 *<select
                id="mode"
                v-model="form.participation_mode"
                class="form-control"
                :aria-invalid="Boolean(fieldErrors.participation_mode)"
                ><option v-for="x in options.participationModes" :key="x" :value="x">{{
                  displayValue(x)
                }}</option></select
              ></label
            >
            <template v-if="form.participation_mode === 'team'"
              ><label class="field" for="team-size"
                >团队总人数 *<input
                  id="team-size"
                  v-model="form.team_size"
                  class="form-control"
                  type="number"
                  min="1"
                  :aria-invalid="Boolean(fieldErrors.team_size)"
                /><small v-if="fieldErrors.team_size" class="field-error">{{
                  fieldErrors.team_size
                }}</small></label
              ><label class="field" for="personal-rank"
                >本人排序 *<input
                  id="personal-rank"
                  v-model="form.personal_rank"
                  class="form-control"
                  type="number"
                  min="1"
                  :max="form.team_size"
                  :aria-invalid="Boolean(fieldErrors.personal_rank)"
                /><small v-if="fieldErrors.personal_rank" class="field-error">{{
                  fieldErrors.personal_rank
                }}</small></label
              ></template
            >
            <label v-if="options.formats.length" class="field"
              >赛制<select v-model="form.event_format" class="form-control"
                ><option value="">请选择</option
                ><option v-for="x in options.formats" :key="x" :value="x">{{
                  displayValue(x)
                }}</option></select
              ></label
            ><label v-if="selected?.event_family === 'csp'" class="field"
              >CSP 排名前百分比<input
                v-model="form.csp_percentile"
                class="form-control"
                type="number"
                step=".01"
            /></label>
          </div>
          <label class="upload-area" for="attachment-upload"
            >证明原件{{ editingRecord?.attachments?.length ? '（已有原件，无须重复上传）' : ' *'
            }}<input
              id="attachment-upload"
              ref="fileInput"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              multiple
              @change="files = Array.from($event.target.files || [])"
            /><small>图片支持后台识别；PDF和未适配项目走人工核验。最多10个附件。</small></label
          >
          <MaterialImagePreview :files="files" :attachments="editingRecord?.attachments || []" />
          <p v-if="fieldErrors.attachments" class="field-error" role="alert">{{
            fieldErrors.attachments
          }}</p>
          <p v-if="actionNotice" role="status">{{ actionNotice }}</p>
          <OcrAssessment v-if="estimate" :advice="estimate" />
          <div class="form-actions"
            ><p>只上传一次，保存后可直接离开页面。</p
            ><button
              class="btn btn-outline"
              type="button"
              :disabled="savingDraft"
              @click="previewScore"
              >预估分数</button
            ><button
              class="btn btn-primary"
              type="submit"
              :disabled="!canSaveDraft || savingDraft"
              >{{
                savingDraft ? '正在保存原件…' : editingRecord ? '保存修改' : '保存材料并后台识别'
              }}</button
            ></div
          >
        </form>
        <section
          v-if="savedRecord"
          class="card workflow-section"
          role="status"
          data-test="saved-material"
        >
          <h3>材料已保存，可继续申报下一项</h3
          ><p
            >{{ savedRecord.data?.project_name }} ·
            {{
              savedRecord.ocr_assessment?.job
                ? 'OCR已在后台排队，离开页面不影响识别。'
                : '原件已保存，可通过人工通道核验。'
            }}</p
          >
          <MaterialImagePreview :attachments="savedRecord.attachments || []" />
          <OcrAssessment :advice="savedRecord.ocr_assessment" />
          <button class="btn btn-outline" type="button" @click="goHistory"
            >前往我的材料查看进度或正式提交</button
          >
        </section>
      </main>
      <aside
        ><section class="card side-card"
          ><h3>申报顺序</h3
          ><ol
            ><li>选择项目并手动填写信息</li
            ><li>上传一次证明原件</li
            ><li>保存后继续申报下一项</li
            ><li>我的材料查看后台OCR及分数预估</li
            ><li>正式提交，等待教师审核</li></ol
          ></section
        ></aside
      >
    </div>
  </section>
</template>
<script setup>
import {
  computed,
  defineComponent,
  h,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import materialApi from '@/services/materialApi.js'
import OcrAssessment from '@/components/common/OcrAssessment.vue'
import MaterialImagePreview from '@/components/common/MaterialImagePreview.vue'
import { displayValue } from '@/services/materialFields.js'
import {
  buildCompetitionFacts,
  competitionErrorState,
  legalCompetitionOptions,
  validateCompetitionForm
} from '@/services/competitionMaterial.js'
const route = useRoute(),
  router = useRouter()
const Heading = defineComponent({
  props: { step: String, title: String, hint: String },
  setup: (p) => () =>
    h('div', { class: 'section-heading' }, [
      h('div', [h('span', { class: 'step' }, p.step), h('h3', p.title)]),
      h('p', p.hint)
    ])
})
const context = ref(null),
  catalog = ref([]),
  query = ref(''),
  selected = ref(null),
  schema = ref(null),
  editingRecord = ref(null)
const savedRecord = ref(null),
  estimate = ref(null),
  files = ref([]),
  fileInput = ref(null),
  savingDraft = ref(false),
  actionNotice = ref(''),
  errorSummary = ref(null)
const pageState = ref({ kind: 'loading', message: '' }),
  searchLoading = ref(false),
  fieldErrors = reactive({})
const emptyForm = () => ({
  competition_id: '',
  project_name: '',
  award_date: '',
  event_year: '',
  level: '',
  award: '',
  participation_mode: 'individual',
  team_size: '',
  personal_rank: '',
  event_format: '',
  csp_percentile: ''
})
const form = reactive(emptyForm())
const options = computed(() => legalCompetitionOptions(schema.value, form.level))
const canSaveDraft = computed(
  () =>
    editingRecord.value?.allowed_actions?.includes('edit') ||
    context.value?.allowed_actions?.includes('create_draft')
)
const stateTitle = computed(
  () =>
    ({
      configuration: '竞赛申报暂未开放',
      permission: '没有访问权限',
      conflict: '材料或规则已更新',
      validation: '请检查申报信息'
    })[pageState.value.kind] || '服务暂不可用'
)
function fail(e) {
  pageState.value = competitionErrorState(e)
}
function replaceErrors(errors) {
  Object.keys(fieldErrors).forEach((k) => delete fieldErrors[k])
  Object.assign(fieldErrors, errors)
}
function focusField(key) {
  document
    .getElementById(
      {
        competition_id: 'competition-select',
        project_name: 'project-name',
        award_date: 'award-date',
        event_year: 'event-year',
        participation_mode: 'mode',
        attachments: 'attachment-upload'
      }[key] || key
    )
    ?.focus()
}
function resetForm() {
  for (const key of Object.keys(form)) delete form[key]
  Object.assign(form, emptyForm())
}
function cancelEditing() {
  editingRecord.value = null
  selected.value = null
  resetForm()
  files.value = []
  replaceErrors({})
  router.replace({ query: { ...route.query, editId: undefined } })
}
let scoreRequest = 0
watch(
  form,
  () => {
    scoreRequest += 1
    estimate.value = null
  },
  { deep: true, flush: 'sync' }
)
let timer = null,
  controller = null,
  alive = true
function scheduleSearch() {
  clearTimeout(timer)
  timer = setTimeout(search, 250)
}
async function search() {
  controller?.abort()
  controller = new AbortController()
  searchLoading.value = true
  try {
    catalog.value =
      (await materialApi.searchCompetitionCatalog(query.value, controller.signal)).items || []
  } catch (e) {
    if (e.name !== 'AbortError') fail(e)
  } finally {
    searchLoading.value = false
  }
}
async function selectCompetition() {
  estimate.value = null
  if (!form.competition_id) {
    selected.value = null
    return
  }
  try {
    const d = await materialApi.getCompetitionCatalogItem(form.competition_id)
    selected.value = d.competition
    schema.value = d.field_schema
    form.level = ''
    form.award = ''
  } catch (e) {
    fail(e)
  }
}
async function retry() {
  pageState.value = { kind: 'loading', message: '' }
  try {
    const d = await materialApi.getCompetitionContext()
    if (!alive) return
    context.value = d
    catalog.value = d.catalog?.items || []
    schema.value = d.field_schema
    if (route.query.editId) {
      const row = await materialApi.getRecord('competition', route.query.editId)
      if (!row.allowed_actions?.includes('edit'))
        throw { status: 409, message: '该材料已不可编辑，请返回我的材料查看最新状态。' }
      editingRecord.value = row
      const entry = await materialApi.getCompetitionCatalogItem(row.data.competition_id)
      selected.value = entry.competition
      schema.value = entry.field_schema
      Object.assign(form, row.data)
    }
    pageState.value = { kind: 'ready', message: '' }
  } catch (e) {
    fail(e)
  }
}
function validate() {
  const errors = validateCompetitionForm(form, schema.value, context.value?.evidence_period)
  replaceErrors(errors)
  if (Object.keys(errors).length) {
    pageState.value = { kind: 'validation', message: '请修正标记的字段。' }
    nextTick(() => errorSummary.value?.focus())
    return false
  }
  return true
}
async function previewScore() {
  if (!validate()) return
  const token = ++scoreRequest
  try {
    const result = await materialApi.estimateCompetition(buildCompetitionFacts(form, schema.value))
    if (token !== scoreRequest || !alive) return
    estimate.value = result
    pageState.value = { kind: 'ready', message: '' }
  } catch (e) {
    if (token === scoreRequest && alive) fail(e)
  }
}
async function validateAndSaveDraft() {
  if (savingDraft.value || !validate()) return
  if (!files.value.length && !editingRecord.value?.attachments?.length) {
    replaceErrors({ attachments: '请上传证明原件。' })
    nextTick(() => focusField('attachments'))
    return
  }
  savingDraft.value = true
  try {
    const facts = buildCompetitionFacts(form, schema.value)
    const row = editingRecord.value
      ? await materialApi.saveCompetitionDraft(
          editingRecord.value.id,
          editingRecord.value.version,
          facts,
          files.value
        )
      : await materialApi.createManualRecord(
          'competition',
          context.value.cycle.cycle_code,
          facts,
          files.value
        )
    if (!alive) return
    savedRecord.value = row
    estimate.value = null
    editingRecord.value = null
    selected.value = null
    resetForm()
    files.value = []
    if (fileInput.value) fileInput.value.value = ''
    replaceErrors({})
    pageState.value = { kind: 'ready', message: '' }
    actionNotice.value = '保存成功。可继续填写下一个项目，稍后到“我的材料”查看进度。'
  } catch (e) {
    fail(e)
  } finally {
    savingDraft.value = false
  }
}
function goHistory() {
  router.push({ query: { page: 'application-record' } })
}
onMounted(retry)
onBeforeUnmount(() => {
  alive = false
  clearTimeout(timer)
  controller?.abort()
})
</script>
<style scoped>
.competition-flow,
.main-column,
aside {
  display: grid;
  gap: 20px;
  color: #172033;
}
.card {
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(30, 61, 92, 0.05);
}
.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 28px;
  background: linear-gradient(135deg, #f8fbff, #edf6ff);
}
.hero h2 {
  margin: 4px 0 8px;
  font-size: 28px;
}
.hero p {
  margin: 0;
  color: #536179;
  line-height: 1.65;
}
.eyebrow {
  color: #0b5cab !important;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.state-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid #c7d6e7;
  border-radius: 10px;
  background: #f7faff;
}
.state-panel h3,
.state-panel p {
  margin: 0;
}
.state-configuration,
.state-conflict {
  border-color: #eac46c;
  background: #fff9e9;
}
.state-validation,
.state-permission,
.state-backend-unavailable {
  border-color: #e3aaaa;
  background: #fff6f6;
}
.context-card {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  overflow: hidden;
}
.context-card div {
  display: grid;
  gap: 6px;
  padding: 18px 20px;
  border-right: 1px solid #e4ebf3;
}
.context-card div:last-child {
  border: 0;
}
.context-card span,
.catalog-controls small {
  color: #6b788d;
  font-size: 12px;
}
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 20px;
  align-items: start;
}
aside {
  position: sticky;
  top: 18px;
}
.workflow-section,
.side-card {
  padding: 24px;
}
.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e6ecf3;
}
.section-heading > div {
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-heading h3,
.section-heading p {
  margin: 0;
}
.section-heading p {
  color: #68758a;
  font-size: 13px;
}
.step {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #0b5cab;
  color: #fff;
  font-weight: 700;
}
.catalog-controls,
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 18px;
}
.catalog-controls label {
  display: flex;
  justify-content: space-between;
  font-weight: 600;
}
.form-control {
  width: 100%;
  min-height: 42px;
  padding: 9px 11px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
  background: #fff;
}
.form-control:focus {
  outline: 0;
  border-color: #0b5cab;
  box-shadow: 0 0 0 3px rgba(11, 92, 171, 0.14);
}
.field {
  display: grid;
  gap: 7px;
  font-weight: 600;
}
.wide {
  grid-column: 1/-1;
}
.authority {
  display: grid;
  grid-template-columns: auto 1fr auto 1fr;
  gap: 8px 14px;
  margin-top: 16px;
  padding: 14px;
  background: #f3f7fb;
  border-radius: 8px;
}
.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid #e6ecf3;
}
.form-actions p {
  margin: 0;
  color: #68758a;
  font-size: 13px;
}
.inline-empty {
  padding: 18px;
  text-align: center;
  border: 1px dashed #afc0d4;
  border-radius: 8px;
  background: #f8fafc;
  color: #526177;
}
.record-card {
  margin-top: 16px;
  padding: 18px;
  border: 1px solid #dce5ef;
  border-radius: 10px;
}
.record-card header,
.record-card header > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.record-card h4 {
  margin: 0;
}
.status-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: #fff2d3;
  color: #805500;
  font-size: 12px;
}
.ocr-boundary {
  padding: 10px 12px;
  border-left: 3px solid #4a87c2;
  background: #f5f9fd;
  color: #526177;
  font-size: 13px;
}
.facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.facts > div {
  min-width: 0;
  padding: 12px;
  border-radius: 8px;
  background: #f7f9fc;
}
.facts span {
  font-size: 12px;
  color: #68758a;
}
.facts pre {
  max-height: 150px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 12px;
}
.upload-area {
  display: grid;
  gap: 6px;
  margin-top: 14px;
  padding: 16px;
  border: 1px dashed #91afd0;
  border-radius: 8px;
  background: #f7fbff;
  font-weight: 600;
}
.upload-area small {
  color: #68758a;
  font-weight: 400;
}
.record-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}
.ocr-warning {
  color: #8a5a00;
}
.score {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 16px;
  border-radius: 8px;
  background: #eef6ff;
}
.score strong {
  font-size: 30px;
  color: #0b5cab;
}
.side-card h3 {
  margin-top: 0;
}
.side-card ul {
  display: grid;
  gap: 10px;
  padding: 0;
  list-style: none;
}
.side-card li {
  display: grid;
  gap: 4px;
  padding-top: 10px;
  border-top: 1px solid #e7edf4;
}
.side-card li span {
  color: #68758a;
}
.side-card ol {
  display: grid;
  gap: 10px;
  padding-left: 22px;
  color: #526177;
}
.btn {
  min-height: 40px;
  padding: 9px 16px;
  border: 1px solid transparent;
  border-radius: 7px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary {
  background: #0b5cab;
  color: #fff;
}
.btn-outline {
  border-color: #9bb1ca;
  background: #fff;
  color: #174b7d;
}
.btn-danger {
  border-color: #cc8b8b;
  background: #fff;
  color: #9b2626;
}
.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.error-summary {
  margin-bottom: 18px;
  padding: 14px 16px;
  border: 1px solid #dc9c9c;
  border-radius: 8px;
  background: #fff5f5;
}
.error-summary h4 {
  margin: 0 0 8px;
  color: #8c2020;
}
.error-summary ul {
  margin: 0;
  padding-left: 20px;
}
.error-summary button {
  padding: 2px;
  border: 0;
  background: transparent;
  color: #8c2020;
  text-decoration: underline;
  cursor: pointer;
}
.field-error {
  color: #a12626;
  font-weight: 500;
}
.form-control[aria-invalid='true'] {
  border-color: #bb3434;
}
.form-control[aria-invalid='true']:focus {
  box-shadow: 0 0 0 3px rgba(187, 52, 52, 0.16);
}
@media (max-width: 980px) {
  .context-card {
    grid-template-columns: repeat(2, 1fr);
  }
  .layout {
    grid-template-columns: 1fr;
  }
  aside {
    position: static;
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 640px) {
  .competition-flow,
  .main-column,
  aside {
    gap: 14px;
  }
  .hero,
  .state-panel,
  .section-heading,
  .form-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .hero,
  .workflow-section,
  .side-card {
    padding: 18px;
  }
  .hero h2 {
    font-size: 24px;
  }
  .context-card,
  .catalog-controls,
  .form-grid,
  .facts,
  aside {
    grid-template-columns: 1fr;
  }
  .context-card div {
    border-right: 0;
    border-bottom: 1px solid #e4ebf3;
  }
  .wide {
    grid-column: auto;
  }
  .authority {
    grid-template-columns: auto 1fr;
  }
  .record-card header,
  .record-card header > div {
    align-items: flex-start;
    flex-direction: column;
  }
  .record-actions .btn,
  .form-actions .btn,
  .hero > .btn {
    width: 100%;
  }
}
</style>
