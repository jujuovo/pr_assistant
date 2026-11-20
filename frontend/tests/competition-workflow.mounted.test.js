// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
const state = vi.hoisted(() => ({
  route: { query: { page: 'materials', category: 'competition' } },
  router: { replace: vi.fn(), push: vi.fn() },
  api: {
    getCompetitionContext: vi.fn(),
    getCompetitionCatalogItem: vi.fn(),
    searchCompetitionCatalog: vi.fn(),
    createManualRecord: vi.fn(),
    saveCompetitionDraft: vi.fn(),
    getRecord: vi.fn(),
    estimateCompetition: vi.fn(),
    listRecords: vi.fn(),
    submit: vi.fn(),
    withdraw: vi.fn(),
    abandon: vi.fn(),
    createCorrection: vi.fn(),
    startCompetitionOcr: vi.fn()
  }
}))
vi.mock('vue-router', () => ({ useRoute: () => state.route, useRouter: () => state.router }))
vi.mock('@/services/materialApi.js', () => ({
  default: state.api,
  MATERIAL_CATEGORIES: ['competition', 'social_practice']
}))
import Form from '../src/pages/student/applications/CompetitionWorkflow.vue'
import History from '../src/pages/student/applications/StudentMaterialsHub.vue'
import MaterialWorkflow from '../src/pages/student/applications/MaterialWorkflow.vue'
const schema = {
  required: [
    'competition_id',
    'project_name',
    'award_date',
    'event_year',
    'level',
    'award',
    'participation_mode'
  ],
  levels: ['national', 'provincial'],
  awards_by_level: {
    national: ['first_or_above', 'second', 'third'],
    provincial: ['first_or_above', 'second']
  },
  participation_modes: ['individual', 'team'],
  formats: []
}
const item = {
  competition_id: 'c09',
  name: '计算机设计大赛',
  category: 'A-',
  event_family: 'computer-design'
}
const facts = {
  competition_id: 'c09',
  project_name: '手动填写的作品',
  award_date: '2027-05-20',
  event_year: 2027,
  level: 'national',
  award: 'first_or_above',
  participation_mode: 'individual'
}
const row = {
  id: 7,
  category: 'competition',
  year: 2028,
  version: 2,
  status: 'draft',
  workflow_state: 'ocr_queued',
  data: facts,
  updated_at: '2026-11-19',
  attachments: [{ id: 1, filename: 'proof.png', url: '/original' }],
  allowed_actions: ['edit', 'submit', 'abandon'],
  ocr_assessment: {
    declared_estimate: '3.3333',
    job: { job_id: 'job7', status: 'queued' },
    requires_teacher_review: true
  }
}
let wrappers = []
const render = (component = Form) => {
  const w = mount(component, {
    attachTo: document.body,
    global: { stubs: { ApplicationHistory: true } }
  })
  wrappers.push(w)
  return w
}
beforeEach(() => {
  vi.clearAllMocks()
  state.route.query = { page: 'materials', category: 'competition' }
  state.api.getCompetitionContext.mockResolvedValue({
    cycle: { cycle_code: 2028 },
    catalog: { count: 1, items: [item] },
    field_schema: schema,
    evidence_period: { start: '2025-09-01', end: '2028-08-31' },
    allowed_actions: ['create_draft']
  })
  state.api.getCompetitionCatalogItem.mockResolvedValue({ competition: item, field_schema: schema })
  state.api.searchCompetitionCatalog.mockResolvedValue({ items: [item] })
  state.api.createManualRecord.mockResolvedValue(structuredClone(row))
  state.api.saveCompetitionDraft.mockResolvedValue(structuredClone(row))
  state.api.getRecord.mockResolvedValue({
    ...structuredClone(row),
    workflow_state: 'ready_to_submit'
  })
  state.api.estimateCompetition.mockResolvedValue({ declared_estimate: '3.3333' })
  state.api.listRecords.mockResolvedValue({ records: [] })
  state.api.submit.mockResolvedValue({})
  state.api.withdraw.mockResolvedValue({})
  state.api.abandon.mockResolvedValue({})
})
afterEach(() => {
  wrappers.forEach((w) => w.unmount())
  wrappers = []
  vi.useRealTimers()
  document.body.innerHTML = ''
})
async function fill(w) {
  await w.get('#competition-select').setValue('c09')
  await flushPromises()
  await w.get('#project-name').setValue(facts.project_name)
  await w.get('#award-date').setValue(facts.award_date)
  await w.get('#event-year').setValue('2027')
  await w.get('#level').setValue('national')
  await w.get('#award').setValue('first_or_above')
}
async function file(w) {
  const el = w.get('#attachment-upload')
  Object.defineProperty(el.element, 'files', {
    value: [new File(['image'], 'proof.png', { type: 'image/png' })],
    configurable: true
  })
  await el.trigger('change')
}
function button(w, text) {
  return w.findAll('button').find((b) => b.text().includes(text))
}

describe('single upload submission', () => {
  it('renders one manual form and one original upload without OCR autofill or history', async () => {
    const w = render()
    await flushPromises()
    expect(w.findAll('input[type=file]')).toHaveLength(1)
    expect(w.text()).not.toContain('使用建议')
    expect(w.find('.record-card').exists()).toBe(false)
    expect(state.api.listRecords).not.toHaveBeenCalled()
    expect(state.api.getCompetitionContext).toHaveBeenCalledTimes(1)
  })
  it('shows Chinese labels while preserving backend enum values', async () => {
    const w = render()
    await flushPromises()
    await fill(w)
    expect(w.get('#award option[value=first_or_above]').text()).toBe('一等奖及以上')
    expect(w.get('#level option[value=national]').text()).toBe('国家级')
    expect(w.get('#mode option[value=individual]').text()).toBe('个人')
    expect(w.get('#award').element.value).toBe('first_or_above')
  })
  it('submits the original once, returns immediately after queueing and accepts a second project', async () => {
    const w = render()
    await flushPromises()
    await fill(w)
    await file(w)
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(state.api.createManualRecord).toHaveBeenCalledTimes(1)
    expect(state.api.createManualRecord.mock.calls[0][2]).toEqual(facts)
    expect(w.text()).toContain('OCR已在后台排队')
    expect(w.get('#project-name').element.value).toBe('')
    await fill(w)
    await w.get('#project-name').setValue('另一个项目')
    await file(w)
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(state.api.createManualRecord).toHaveBeenCalledTimes(2)
    expect(state.api.startCompetitionOcr).not.toHaveBeenCalled()
  })
  it('prevents duplicate save while the single upload is in flight', async () => {
    state.api.createManualRecord.mockReturnValue(new Promise(() => {}))
    const w = render()
    await flushPromises()
    await fill(w)
    await file(w)
    await w.get('form').trigger('submit')
    await w.get('form').trigger('submit')
    expect(state.api.createManualRecord).toHaveBeenCalledTimes(1)
    expect(w.get('button[type=submit]').attributes('disabled')).toBeDefined()
  })
  it('requires the original before creating any material', async () => {
    const w = render()
    await flushPromises()
    await fill(w)
    await w.get('form').trigger('submit')
    expect(w.text()).toContain('请上传证明原件')
    expect(state.api.createManualRecord).not.toHaveBeenCalled()
  })
  it('focuses validation without replacing manual input', async () => {
    const w = render()
    await flushPromises()
    await w.get('#project-name').setValue('保留输入')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.get('.error-summary').element).toBe(document.activeElement)
    expect(w.get('#project-name').element.value).toBe('保留输入')
    await w.get('.error-summary button').trigger('click')
    expect(document.activeElement.id).toBe('competition-select')
  })
  it('previews authoritative score without saving, OCR or submitting', async () => {
    const w = render()
    await flushPromises()
    await fill(w)
    await button(w, '预估分数').trigger('click')
    await flushPromises()
    expect(state.api.estimateCompetition).toHaveBeenCalledWith(facts)
    expect(w.text()).toContain('3.3333')
    expect(state.api.createManualRecord).not.toHaveBeenCalled()
    expect(state.api.submit).not.toHaveBeenCalled()
  })
  it.each([
    [{ code: 'competition_package_missing', status: 409 }, 'configuration'],
    [{ code: 'forbidden', status: 403 }, 'permission'],
    [{ status: 503 }, 'backend-unavailable']
  ])('renders actionable context error %s', async (failure, kind) => {
    state.api.getCompetitionContext.mockRejectedValue(failure)
    const w = render()
    await flushPromises()
    expect(w.find(`[data-state="${kind}"]`).exists()).toBe(true)
    expect(w.find('form').exists()).toBe(false)
    expect(button(w, '重新加载')).toBeDefined()
  })
  it('retains input after version conflict or upload failure', async () => {
    state.api.createManualRecord.mockRejectedValue({ code: 'version_conflict', status: 409 })
    const w = render()
    await flushPromises()
    await fill(w)
    await file(w)
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.find('[data-state=conflict]').exists()).toBe(true)
    expect(w.get('#project-name').element.value).toBe(facts.project_name)
    expect(w.get('form').exists()).toBe(true)
  })
  it('edits a persisted draft without requiring a second original upload', async () => {
    state.route.query.editId = 7
    const w = render()
    await flushPromises()
    expect(w.get('#project-name').element.value).toBe(facts.project_name)
    await w.get('#project-name').setValue('修改作品')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(state.api.saveCompetitionDraft).toHaveBeenCalledWith(
      7,
      2,
      expect.objectContaining({ project_name: '修改作品' }),
      []
    )
    expect(state.api.createManualRecord).not.toHaveBeenCalled()
  })
  it('debounces search and renders an empty result', async () => {
    vi.useFakeTimers()
    state.api.searchCompetitionCatalog.mockResolvedValue({ items: [] })
    const w = render()
    await flushPromises()
    await w.get('#competition-search').setValue('计')
    await w.get('#competition-search').setValue('计算机')
    await vi.advanceTimersByTimeAsync(250)
    await flushPromises()
    expect(state.api.searchCompetitionCatalog).toHaveBeenCalledTimes(1)
    expect(w.find('[data-state=search-empty]').exists()).toBe(true)
  })
  it('stays a single form when mounted through the category page', async () => {
    const w = render(MaterialWorkflow)
    await flushPromises()
    expect(w.findAll('input[type=file]')).toHaveLength(1)
    expect(state.api.getCompetitionContext).toHaveBeenCalledTimes(1)
    expect(state.api.listRecords).not.toHaveBeenCalled()
  })
})

describe('persistent material history', () => {
  it('shows queued history, no creation form, and resumes completed status after reopening', async () => {
    state.api.listRecords.mockImplementation(async (c) => ({
      records: c === 'competition' ? [structuredClone(row)] : []
    }))
    const first = render(History)
    await flushPromises()
    expect(first.text()).toContain('OCR队列中')
    expect(first.find('input[type=file]').exists()).toBe(false)
    expect(button(first, '正式提交审核')).toBeUndefined()
    first.unmount()
    wrappers = []
    state.api.listRecords.mockImplementation(async (c) => ({
      records:
        c === 'competition'
          ? [
              {
                ...structuredClone(row),
                workflow_state: 'ready_to_submit',
                ocr_assessment: {
                  ...row.ocr_assessment,
                  job: { status: 'completed' },
                  missing_fields: ['level'],
                  differences: [
                    { field: 'award', declared: 'first_or_above', recognized: 'second' }
                  ]
                }
              }
            ]
          : []
    }))
    const second = render(History)
    await flushPromises()
    expect(second.text()).toContain('待提交')
    expect(second.text()).toContain('奖项不一致')
    expect(second.text()).toContain('一等奖及以上')
    expect(button(second, '正式提交审核')).toBeDefined()
  })
  it('formally submits only via the authorized history action', async () => {
    state.api.listRecords.mockImplementation(async (c) => ({
      records:
        c === 'competition' ? [{ ...structuredClone(row), workflow_state: 'ready_to_submit' }] : []
    }))
    const w = render(History)
    await flushPromises()
    await button(w, '正式提交审核').trigger('click')
    await flushPromises()
    expect(state.api.submit).toHaveBeenCalledWith('competition', 7, 2)
    expect(w.text()).toContain('等待教师审核')
  })
  it('retains withdrawal and delete with backend versions', async () => {
    state.api.listRecords
      .mockResolvedValueOnce({
        records: [
          {
            ...structuredClone(row),
            status: 'submitted',
            workflow_state: 'pending_review',
            allowed_actions: ['withdraw']
          }
        ]
      })
      .mockResolvedValueOnce({ records: [] })
    const w = render(History)
    await flushPromises()
    await button(w, '撤回为草稿').trigger('click')
    await flushPromises()
    expect(state.api.withdraw).toHaveBeenCalledWith('competition', 7, 2)
  })
  it('routes correction to an editable successor rather than overwriting history', async () => {
    state.api.listRecords
      .mockResolvedValueOnce({
        records: [
          {
            ...structuredClone(row),
            status: 'needs_correction',
            workflow_state: 'needs_correction',
            allowed_actions: ['create_correction']
          }
        ]
      })
      .mockResolvedValueOnce({ records: [] })
    state.api.createCorrection.mockResolvedValue({ id: 8, category: 'competition' })
    const w = render(History)
    await flushPromises()
    await button(w, '补正材料').trigger('click')
    await flushPromises()
    expect(state.api.createCorrection).toHaveBeenCalledWith('competition', 7, 2, facts)
    expect(state.router.push).toHaveBeenCalledWith({
      query: { page: 'materials', category: 'competition', editId: 8 }
    })
  })
  it('renders partial failure and empty history with retry', async () => {
    state.api.listRecords.mockRejectedValue(new Error('offline'))
    const w = render(History)
    await flushPromises()
    expect(w.get('[role=alert]').text()).toContain('未能加载')
    expect(w.text()).toContain('暂无符合条件')
  })
  it('filters states and never offers a command without allowed_actions', async () => {
    state.api.listRecords
      .mockResolvedValueOnce({
        records: [
          {
            ...structuredClone(row),
            status: 'scored',
            workflow_state: 'approved',
            allowed_actions: []
          }
        ]
      })
      .mockResolvedValueOnce({ records: [] })
    const w = render(History)
    await flushPromises()
    expect(w.text()).toContain('已通过')
    expect(button(w, '正式提交审核')).toBeUndefined()
    await w.get('select').setValue('draft')
    expect(w.text()).toContain('暂无符合条件')
  })
  it('loads additional pages without losing earlier materials', async () => {
    state.api.listRecords.mockImplementation(async (c, f) => ({
      records: c === 'competition' ? [{ ...structuredClone(row), id: f.after_id ? 8 : 7 }] : [],
      next_after_id: c === 'competition' && !f.after_id ? 7 : null
    }))
    const w = render(History)
    await flushPromises()
    await button(w, '加载更多').trigger('click')
    await flushPromises()
    expect(w.findAll('.history-card')).toHaveLength(2)
    expect(state.api.listRecords).toHaveBeenCalledWith('competition', { after_id: 7 })
  })
})

it('isolates an old score response after the student changes declared facts', async () => {
  let resolve
  state.api.estimateCompetition.mockReturnValue(new Promise((r) => (resolve = r)))
  const w = render()
  await flushPromises()
  await fill(w)
  await button(w, '预估分数').trigger('click')
  await w.get('#project-name').setValue('已改变的信息')
  resolve({ declared_estimate: '99.9999' })
  await flushPromises()
  expect(w.text()).not.toContain('99.9999')
  expect(w.get('#project-name').element.value).toBe('已改变的信息')
})
it('refreshes only persisted pending jobs and stops watching when history unmounts', async () => {
  vi.useFakeTimers()
  state.api.listRecords.mockImplementation(async (c) => ({
    records: c === 'competition' ? [structuredClone(row)] : []
  }))
  state.api.getRecord.mockResolvedValue({
    ...structuredClone(row),
    workflow_state: 'ready_to_submit',
    ocr_assessment: { ...row.ocr_assessment, job: { status: 'completed' } }
  })
  const w = render(History)
  await flushPromises()
  await vi.advanceTimersByTimeAsync(5000)
  await flushPromises()
  expect(state.api.getRecord).toHaveBeenCalledWith('competition', 7)
  expect(w.text()).toContain('待提交')
  expect(state.api.createManualRecord).not.toHaveBeenCalled()
  const count = state.api.getRecord.mock.calls.length
  w.unmount()
  wrappers = []
  await vi.advanceTimersByTimeAsync(10000)
  expect(state.api.getRecord).toHaveBeenCalledTimes(count)
})
