<template>
  <section class="competition-flow" aria-labelledby="competition-title">
    <header class="card hero"
      ><div
        ><p class="eyebrow">证明材料 · 学业竞赛</p><h2 id="competition-title">学业竞赛申报</h2
        ><p>依据后端正式目录填写获奖事实；规则分类、候选分与审核结论均为只读权威信息。</p></div
      ><button
        class="btn btn-outline"
        type="button"
        data-test="refresh-records"
        :disabled="!context || recordsLoading"
        @click="load"
        >{{ recordsLoading ? '刷新中…' : '刷新竞赛记录' }}</button
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
            ><span>后端分类</span><strong>{{ selected.category }}</strong
            ><span>赛事族</span><strong>{{ selected.event_family }}</strong></div
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
              >级别 *<select
                id="level"
                v-model="form.level"
                class="form-control"
                required
                :aria-invalid="Boolean(fieldErrors.level)"
                :aria-describedby="fieldErrors.level ? 'level-error' : undefined"
                ><option value="">请选择</option
                ><option v-for="x in options.levels" :key="x">{{ x }}</option></select
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
                ><option v-for="x in options.awards" :key="x">{{ x }}</option></select
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
                ><option v-for="x in options.participationModes" :key="x">{{ x }}</option></select
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
                ><option v-for="x in options.formats" :key="x">{{ x }}</option></select
              ></label
            ><label v-if="selected?.event_family === 'csp'" class="field"
              >CSP 排名前百分比<input
                v-model="form.csp_percentile"
                class="form-control"
                type="number"
                step=".01"
            /></label>
          </div>
          <div class="form-actions"
            ><p>保存后可上传证明原件并选择 OCR 辅助核对。</p
            ><button class="btn btn-primary" type="submit" :disabled="!canSaveDraft">{{
              editingRecord ? '更新草稿' : '保存草稿'
            }}</button></div
          >
        </form>
        <section class="card workflow-section"
          ><Heading
            step="3"
            title="附件、OCR 与提交"
            hint="OCR 仅辅助预览，不会覆盖学生确认事实。"
          /><p v-if="actionNotice" class="action-notice" role="status" aria-live="polite">{{
            actionNotice
          }}</p
          ><p
            v-if="pageState.kind === 'ready' && !recordsLoading && !records.length"
            class="inline-empty"
            role="status"
            data-state="empty"
            >当前周期还没有竞赛材料，可从正式目录开始申报。</p
          >
          <article v-for="row in records" :key="row.id" class="record-card"
            ><header
              ><div
                ><span class="status-badge">{{ row.status }}</span
                ><h4>{{ row.data?.competition_name || row.data?.project_name }}</h4></div
              ><span>版本 {{ row.version }}</span></header
            ><p v-if="row.superseded_by_record_id" class="action-notice" role="status"
              >此记录已由补正版本 #{{ row.superseded_by_record_id }} 取代，仅保留用于审计。</p
            ><p class="ocr-boundary"
              >OCR
              仅用于辅助预览，不会认定真实性、审核结论或最终加分；失败时请按学生确认值人工处理。</p
            ><div class="facts"
              ><div
                ><span>OCR 原文</span
                ><pre>{{ JSON.stringify(row.ocr_raw_terms || {}, null, 2) }}</pre></div
              ><div
                ><span>学生确认值</span><pre>{{ JSON.stringify(row.data, null, 2) }}</pre>
              </div></div
            ><label v-if="row.allowed_actions?.includes('add_attachment')" class="upload-area"
              >上传证明附件<input type="file" multiple @change="upload(row, $event)" /><small
                >支持 PDF、图片、CSV、XLSX；最多 10 个文件。</small
              ></label
            ><p v-if="jobs[row.id]"
              >OCR 状态：{{ jobs[row.id].status
              }}<span v-if="jobs[row.id].late_result_ignored">；迟到结果已隔离</span
              ><span v-if="jobs[row.id].error">；{{ jobs[row.id].error }}</span></p
            ><p
              v-if="ocrNotice(jobs[row.id])"
              class="ocr-warning"
              role="status"
              :data-test="`ocr-notice-${row.id}`"
              >{{ ocrNotice(jobs[row.id]) }}</p
            ><footer class="record-actions"
              ><button
                v-if="row.allowed_actions?.includes('edit')"
                class="btn btn-outline"
                type="button"
                :data-test="`edit-${row.id}`"
                @click="editDraft(row)"
                >编辑草稿</button
              ><button
                v-if="row.status === 'draft'"
                class="btn btn-outline"
                type="button"
                @click="startOcr(row)"
                >等待 OCR 并核对</button
              ><button
                v-if="jobs[row.id]"
                class="btn btn-outline"
                type="button"
                @click="stopOcr(row)"
                >停止 OCR 后手填</button
              ><button
                v-if="row.allowed_actions?.includes('submit')"
                class="btn btn-primary"
                type="button"
                @click="submit(row)"
                >提交审核</button
              ><button
                v-if="row.allowed_actions?.includes('withdraw')"
                class="btn btn-outline"
                type="button"
                :data-test="`withdraw-${row.id}`"
                @click="withdraw(row)"
                >撤回为草稿</button
              ><button
                v-if="row.allowed_actions?.includes('create_correction')"
                class="btn btn-primary"
                type="button"
                @click="createCorrection(row)"
                >修改并重提</button
              ><button
                v-if="row.allowed_actions?.includes('abandon')"
                class="btn btn-danger"
                type="button"
                :data-test="`abandon-${row.id}`"
                @click="abandon(row)"
                >{{ row.status === 'draft' ? '删除草稿' : '放弃材料' }}</button
              ><button
                v-if="row.status === 'rule_reconfirmation_required'"
                class="btn btn-primary"
                type="button"
                @click="reconfirm(row)"
                >确认新规则并重提</button
              ></footer
            ></article
          >
        </section>
      </main>
      <aside
        ><section class="card side-card"
          ><h3>本人竞赛计分反馈</h3
          ><template v-if="feedback"
            ><div class="score"
              ><strong>{{ feedback.competition_total }}</strong
              ><span>竞赛计入合计</span></div
            ><p>周期总分：{{ feedback.cycle_snapshot.comprehensive_score ?? '暂无权威快照' }}</p
            ><ul
              ><li v-for="item in feedback.items" :key="item.material_id"
                ><strong>{{ item.project_name }}</strong
                ><span>候选 {{ item.candidate_score }} · 计入 {{ item.effective_score }}</span></li
              ></ul
            ></template
          ><p v-else>正在读取权威反馈…</p></section
        ><section class="card side-card"
          ><h3>申报顺序</h3
          ><ol
            ><li>选择正式目录条目</li
            ><li>按原件填写事实</li
            ><li>保存并上传附件</li
            ><li>可选 OCR 辅助核对</li
            ><li>确认后提交审核</li></ol
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
  ref
} from 'vue'
import materialApi from '@/services/materialApi.js'
import {
  buildCompetitionFacts,
  competitionErrorState,
  legalCompetitionOptions,
  validateCompetitionForm
} from '@/services/competitionMaterial.js'
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
  records = ref([]),
  feedback = ref(null),
  query = ref(''),
  selected = ref(null),
  schema = ref(null),
  editingRecord = ref(null),
  jobs = reactive({}),
  fieldErrors = reactive({})
const pageState = ref({ kind: 'loading', message: '' }),
  recordsLoading = ref(false),
  searchLoading = ref(false),
  actionNotice = ref(''),
  errorSummary = ref(null)
const form = reactive({
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
      validation: '请修正材料信息',
      permission: '没有访问权限',
      conflict: '内容已发生变化',
      'backend-unavailable': '服务暂不可用'
    })[pageState.value.kind] || '需要处理'
)
const fail = (e) => {
  pageState.value = competitionErrorState(e)
  if (e?.code === 'competition_attachment_required')
    replaceErrors({ attachments: '请先上传证明原件，再提交审核' })
  else if (e?.code === 'duplicate_submission')
    replaceErrors({ competition_id: '该竞赛材料已提交，请处理已有记录' })
  if (['competition_attachment_required', 'duplicate_submission'].includes(e?.code))
    nextTick(() => errorSummary.value?.focus())
}
const ocrNotice = (j) =>
  !j
    ? ''
    : j.status === 'failed'
      ? 'OCR 失败，请继续使用人工填写的学生确认值'
      : j.status === 'completed' &&
          Number.isFinite(Number(j.raw_result?.confidence)) &&
          Number(j.raw_result.confidence) < 0.8
        ? 'OCR 置信度较低，请人工核对并以学生确认值为准'
        : ''
let searchTimer = null,
  searchController = null
async function loadContext() {
  pageState.value = { kind: 'loading', message: '' }
  try {
    context.value = await materialApi.getCompetitionContext()
    catalog.value = context.value.catalog?.items || []
    schema.value = context.value.field_schema
    pageState.value = { kind: 'ready', message: '' }
  } catch (e) {
    context.value = null
    fail(e)
    throw e
  }
}
async function load() {
  if (!context.value) return
  recordsLoading.value = true
  try {
    const year = context.value.cycle.cycle_code
    const [list, scores] = await Promise.all([
      materialApi.listRecords('competition', { year }),
      materialApi.getCompetitionFeedback(year)
    ])
    records.value = list.records || []
    feedback.value = scores
    pageState.value = { kind: 'ready', message: '' }
  } catch (e) {
    fail(e)
  } finally {
    recordsLoading.value = false
  }
}
function scheduleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(search, 250)
}
async function search() {
  searchController?.abort()
  searchController = new AbortController()
  searchLoading.value = true
  try {
    catalog.value =
      (await materialApi.searchCompetitionCatalog(query.value, searchController.signal)).items || []
  } catch (e) {
    if (e?.name !== 'AbortError') fail(e)
  } finally {
    searchLoading.value = false
  }
}
async function retry() {
  try {
    await loadContext()
    await load()
  } catch {}
}
async function selectCompetition() {
  if (!form.competition_id) {
    selected.value = null
    schema.value = context.value?.field_schema || null
    return
  }
  try {
    const data = await materialApi.getCompetitionCatalogItem(form.competition_id)
    selected.value = data.competition
    schema.value = data.field_schema
    form.level = data.field_schema.levels[0] || ''
    form.award = legalCompetitionOptions(schema.value, form.level).awards[0] || ''
  } catch (e) {
    fail(e)
  }
}
async function upload(row, e) {
  try {
    await materialApi.uploadAttachments('competition', row.id, row.version, e.target.files)
    await load()
  } catch (x) {
    fail(x)
  }
}
async function pollOcr(row) {
  try {
    const job = await materialApi.getCompetitionOcr(row.id, jobs[row.id].job_id)
    jobs[row.id] = job
    if (['queued', 'running'].includes(job.status)) setTimeout(() => pollOcr(row), 1200)
    else if (job.status === 'completed') await load()
    else if (job.status === 'failed')
      jobs[row.id] = { ...job, error: job.error || 'OCR 失败，请手工填写' }
  } catch (e) {
    fail(e)
  }
}
async function startOcr(row) {
  try {
    jobs[row.id] = await materialApi.startCompetitionOcr(row.id, row.version)
    pollOcr(row)
  } catch (e) {
    fail(e)
  }
}
async function stopOcr(row) {
  try {
    await materialApi.cancelCompetitionOcr(row.id, row.version, jobs[row.id].job_id)
    delete jobs[row.id]
    await load()
  } catch (e) {
    fail(e)
  }
}
async function submit(row) {
  try {
    await materialApi.submit('competition', row.id, row.version)
    await load()
  } catch (e) {
    fail(e)
  }
}
async function confirmedPayload(row) {
  const d = await materialApi.getCompetitionCatalogItem(row.data.competition_id)
  return buildCompetitionFacts(row.data, d.field_schema)
}
async function createCorrection(row) {
  try {
    const correction = await materialApi.createCorrection(
      'competition',
      row.id,
      row.version,
      await confirmedPayload(row)
    )
    await load()
    await editDraft(correction)
  } catch (e) {
    fail(e)
  }
}
async function abandon(row) {
  try {
    await materialApi.abandon('competition', row.id, row.version)
    await load()
  } catch (e) {
    fail(e)
  }
}
async function reconfirm(row) {
  try {
    await materialApi.reconfirmCompetition(row.id, row.version, await confirmedPayload(row))
    await load()
  } catch (e) {
    fail(e)
  }
}
onMounted(async () => {
  try {
    await loadContext()
    await load()
  } catch {}
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  searchController?.abort()
})
const fieldIds = {
  competition_id: 'competition-select',
  project_name: 'project-name',
  award_date: 'award-date',
  event_year: 'event-year',
  level: 'level',
  award: 'award',
  participation_mode: 'mode',
  team_size: 'team-size',
  personal_rank: 'personal-rank',
  attachments: 'attachment-upload'
}
function focusField(key) {
  ;(
    document.getElementById(fieldIds[key]) ||
    document.querySelector('.upload-area input[type="file"]')
  )?.focus()
}
function replaceErrors(errors) {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
  Object.assign(fieldErrors, errors)
}
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
function cancelEditing() {
  editingRecord.value = null
  selected.value = null
  schema.value = context.value?.field_schema || null
  Object.assign(form, emptyForm())
  replaceErrors({})
  actionNotice.value = '已取消编辑，表单已恢复为新建草稿。'
}
async function editDraft(row) {
  if (!row?.allowed_actions?.includes('edit')) return
  try {
    const data = await materialApi.getCompetitionCatalogItem(row.data.competition_id)
    editingRecord.value = row
    selected.value = data.competition
    schema.value = data.field_schema
    Object.assign(form, emptyForm(), row.data)
    replaceErrors({})
    pageState.value = { kind: 'ready', message: '' }
    actionNotice.value = '已载入草稿，请修改后点击“更新草稿”。'
    await nextTick()
    document.getElementById('project-name')?.focus()
    document.getElementById('project-name')?.scrollIntoView?.({ block: 'center' })
  } catch (e) {
    fail(e)
  }
}
async function validateAndSaveDraft() {
  const errors = validateCompetitionForm(form, schema.value, context.value?.evidence_period)
  replaceErrors(errors)
  if (Object.keys(errors).length) {
    pageState.value = { kind: 'validation', message: '请修正标记字段后再保存。' }
    await nextTick()
    errorSummary.value?.focus()
    return
  }
  try {
    const facts = buildCompetitionFacts(form, schema.value)
    if (editingRecord.value)
      await materialApi.updateRecord(
        'competition',
        editingRecord.value.id,
        editingRecord.value.version,
        facts
      )
    else
      await materialApi.createRecord('competition', {
        year: context.value.cycle.cycle_code,
        data: facts
      })
    replaceErrors({})
    editingRecord.value = null
    selected.value = null
    schema.value = context.value?.field_schema || null
    Object.assign(form, emptyForm())
    actionNotice.value = '草稿已保存，可继续上传附件或提交审核。'
    await load()
  } catch (e) {
    if (e.code === 'duplicate_submission')
      replaceErrors({ competition_id: '该竞赛材料已提交，请处理已有记录' })
    fail(e)
    await nextTick()
    errorSummary.value?.focus()
  }
}
async function withdraw(row) {
  try {
    await materialApi.withdraw('competition', row.id, row.version)
    await load()
  } catch (e) {
    fail(e)
  }
}
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
