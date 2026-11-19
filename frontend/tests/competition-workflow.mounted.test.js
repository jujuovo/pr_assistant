// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  route: { query: { page: 'materials', category: 'competition' } },
  router: { replace: vi.fn() },
  api: {
    getCompetitionContext: vi.fn(),
    listRecords: vi.fn(),
    getCompetitionFeedback: vi.fn(),
    searchCompetitionCatalog: vi.fn(),
    getCompetitionCatalogItem: vi.fn(),
    createRecord: vi.fn(),
    updateRecord: vi.fn(),
    createCorrection: vi.fn(),
    startCompetitionOcr: vi.fn(),
    getCompetitionOcr: vi.fn(),
    cancelCompetitionOcr: vi.fn(),
    abandon: vi.fn(),
    withdraw: vi.fn(),
    submit: vi.fn(),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => state.route,
  useRouter: () => state.router,
}))
vi.mock('@/services/materialApi.js', () => ({
  default: state.api,
  MATERIAL_CATEGORIES: ['academic', 'competition', 'language', 'student_work', 'honor'],
}))

import CompetitionWorkflow from '../src/pages/student/applications/CompetitionWorkflow.vue'
import MaterialWorkflow from '../src/pages/student/applications/MaterialWorkflow.vue'

const context = {
  available: true,
  cycle: { cycle_code: 2028 },
  catalog: {
    count: 1,
    items: [{ competition_id: 'c09', name: '计算机设计大赛', category: 'A-', levels: ['national'], event_family: 'computer-design' }],
  },
  field_schema: {
    required: ['competition_id', 'project_name', 'award_date', 'level', 'award', 'event_year', 'participation_mode'],
    awards: { national: ['first_or_above'] },
    participation_modes: ['individual', 'team'],
    team_required: ['team_size', 'personal_rank'],
  },
  allowed_actions: ['view_catalog', 'list_records', 'create_draft'],
}

beforeEach(() => {
  vi.clearAllMocks()
  state.route.query = { page: 'materials', category: 'competition' }
  state.api.getCompetitionContext.mockResolvedValue(structuredClone(context))
  state.api.listRecords.mockResolvedValue({ records: [] })
  state.api.getCompetitionFeedback.mockResolvedValue({
    competition_total: 0,
    cycle_snapshot: { comprehensive_score: null },
    items: [],
  })
  state.api.searchCompetitionCatalog.mockResolvedValue({ items: context.catalog.items })
  state.api.getCompetitionCatalogItem.mockResolvedValue({
    competition: context.catalog.items[0],
    field_schema: { ...context.field_schema, levels: ['national'], awards_by_level: { national: ['first_or_above'] }, formats: [] },
  })
  state.api.startCompetitionOcr.mockResolvedValue({ job_id: 'job-1', status: 'queued', material_version: 1 })
  state.api.getCompetitionOcr.mockResolvedValue({ job_id: 'job-1', status: 'failed', error: '识别服务失败' })
  state.api.cancelCompetitionOcr.mockResolvedValue({ job_id: 'job-1', status: 'cancelled', version: 2 })
  state.api.abandon.mockResolvedValue({ id: 7, status: 'abandoned', version: 2 })
  state.api.withdraw.mockResolvedValue({ id: 7, status: 'draft', version: 4 })
  state.api.submit.mockResolvedValue({ id: 7, status: 'submitted', version: 2 })
  state.api.updateRecord.mockResolvedValue({ id: 7, status: 'draft', version: 2 })
})

describe('competition request ownership', () => {
  it('mounts the product sections, labelled controls, attachment area and action region', async () => {
    state.api.listRecords.mockResolvedValueOnce({ records: [{
      id: 7, version: 1, status: 'draft', data: { project_name: '布局测试作品' },
      allowed_actions: ['add_attachment', 'submit'],
    }] })
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()

    for (const heading of ['学业竞赛申报', '选择正式竞赛', '填写材料事实', '附件、OCR 与提交', '本人竞赛计分反馈']) {
      expect(wrapper.text()).toContain(heading)
    }
    for (const id of ['competition-search', 'competition-select', 'project-name', 'award-date', 'event-year', 'level', 'award', 'mode']) {
      expect(wrapper.get(`#${id}`).attributes('id')).toBe(id)
      expect(wrapper.get(`label[for="${id}"]`).exists()).toBe(true)
    }
    expect(wrapper.get('.upload-area input[type="file"]').exists()).toBe(true)
    expect(wrapper.get('.record-actions').text()).toContain('提交审核')
  })

  it('mounts through MaterialWorkflow without a duplicate parent records request', async () => {
    mount(MaterialWorkflow)
    await flushPromises()

    expect(state.api.getCompetitionContext).toHaveBeenCalledTimes(1)
    expect(state.api.listRecords).toHaveBeenCalledTimes(1)
    expect(state.api.listRecords).toHaveBeenCalledWith('competition', { year: 2028 })
    expect(state.api.getCompetitionFeedback).toHaveBeenCalledTimes(1)
  })

  it('refreshes records exactly once and keeps catalog selection independent', async () => {
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()
    expect(state.api.listRecords).toHaveBeenCalledTimes(1)

    await wrapper.get('[data-test="refresh-records"]').trigger('click')
    await flushPromises()
    expect(state.api.listRecords).toHaveBeenCalledTimes(2)
    expect(state.api.getCompetitionFeedback).toHaveBeenCalledTimes(2)
    expect(state.api.getCompetitionContext).toHaveBeenCalledTimes(1)

    await wrapper.get('select').setValue('c09')
    await flushPromises()
    expect(state.api.getCompetitionCatalogItem).toHaveBeenCalledTimes(1)
    expect(state.api.listRecords).toHaveBeenCalledTimes(2)
  })

  it('removes a draft through the backend-authorized abandon action', async () => {
    state.api.listRecords
      .mockResolvedValueOnce({ records: [{
        id: 7, version: 1, status: 'draft', data: { project_name: '多余草稿' },
        allowed_actions: ['submit', 'abandon'],
      }] })
      .mockResolvedValueOnce({ records: [] })
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()

    expect(wrapper.get('[data-test="abandon-7"]').text()).toBe('删除草稿')
    await wrapper.get('[data-test="abandon-7"]').trigger('click')
    await flushPromises()
    expect(state.api.abandon).toHaveBeenCalledWith('competition', 7, 1)
    expect(wrapper.text()).not.toContain('多余草稿')
  })

  it('hides upload for submitted material and allows an authority-driven withdrawal', async () => {
    state.api.listRecords
      .mockResolvedValueOnce({ records: [{
        id: 8, version: 3, status: 'submitted', data: { project_name: '已提交作品' },
        allowed_actions: ['withdraw'],
      }] })
      .mockResolvedValueOnce({ records: [{
        id: 8, version: 4, status: 'draft', data: { project_name: '已提交作品' },
        allowed_actions: ['add_attachment', 'submit', 'abandon'],
      }] })
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()

    expect(wrapper.find('.upload-area').exists()).toBe(false)
    await wrapper.get('[data-test="withdraw-8"]').trigger('click')
    await flushPromises()
    expect(state.api.withdraw).toHaveBeenCalledWith('competition', 8, 3)
    expect(wrapper.find('.upload-area').exists()).toBe(true)
    expect(wrapper.get('[data-test="abandon-8"]').text()).toBe('删除草稿')
  })
})

describe('competition page states', () => {
  it('renders loading and successful empty states from mounted async behavior', async () => {
    state.api.getCompetitionContext.mockReturnValue(new Promise(() => {}))
    const loading = mount(CompetitionWorkflow)
    expect(loading.get('[data-state="loading"]').text()).toContain('正在加载')
    loading.unmount()

    state.api.getCompetitionContext.mockResolvedValue(structuredClone(context))
    const empty = mount(CompetitionWorkflow)
    await flushPromises()
    expect(empty.get('[data-state="empty"]').text()).toContain('还没有竞赛材料')
  })

  it.each([
    [{ code: 'competition_package_missing', status: 409 }, 'configuration', '管理员'],
    [{ code: 'forbidden', status: 403 }, 'permission', '权限'],
    [{ status: 503 }, 'backend-unavailable', '问题不一定来自材料内容'],
  ])('maps context failure %j to actionable %s state', async (failure, kind, message) => {
    state.api.getCompetitionContext.mockRejectedValue(Object.assign(new Error('backend'), failure))
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()

    expect(wrapper.get(`[data-state="${kind}"]`).text()).toContain(message)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('操作失败，请核对材料后重试')
  })

  it('keeps the form mounted for validation and conflict recovery', async () => {
    const wrapper = mount(CompetitionWorkflow, { attachTo: document.body })
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[data-state="validation"]').text()).toContain('修正标记字段')
    expect(wrapper.get('.error-summary').text()).toContain('正式目录条目为必填项')
    expect(wrapper.get('.error-summary').element).toBe(document.activeElement)
    await wrapper.get('.error-summary button').trigger('click')
    expect(wrapper.get('#competition-select').element).toBe(document.activeElement)
    expect(state.api.createRecord).not.toHaveBeenCalled()
    expect(wrapper.find('form').exists()).toBe(true)

    state.api.listRecords.mockRejectedValueOnce(Object.assign(new Error('stale'), {
      code: 'version_conflict', status: 409,
    }))
    await wrapper.get('[data-test="refresh-records"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-state="conflict"]').text()).toContain('刷新权威状态')
    expect(wrapper.find('form').exists()).toBe(true)
    wrapper.unmount()
  })

  it('distinguishes a successful catalog search with no matches', async () => {
    vi.useFakeTimers()
    state.api.searchCompetitionCatalog.mockResolvedValueOnce({ items: [] })
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()
    await wrapper.get('input').setValue('不存在的竞赛')
    await vi.advanceTimersByTimeAsync(250)
    await flushPromises()
    expect(wrapper.get('[data-state="search-empty"]').text()).toContain('正式目录无匹配结果')
    vi.useRealTimers()
  })

  it('debounces catalog input and never requests an empty catalog item id', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()

    await wrapper.get('#competition-search').setValue('计')
    await wrapper.get('#competition-search').setValue('计算机')
    await wrapper.get('#competition-search').setValue('计算机设计')
    await vi.advanceTimersByTimeAsync(250)
    await flushPromises()
    expect(state.api.searchCompetitionCatalog).toHaveBeenCalledTimes(1)
    expect(state.api.searchCompetitionCatalog.mock.calls[0][0]).toBe('计算机设计')

    await wrapper.get('#competition-select').setValue('')
    await flushPromises()
    expect(state.api.getCompetitionCatalogItem).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('focuses actionable attachment and duplicate errors without partial creation', async () => {
    state.api.listRecords.mockResolvedValue({ records: [{
      id: 9, version: 1, status: 'draft', data: { project_name: '缺附件作品' },
      allowed_actions: ['add_attachment', 'submit', 'abandon'],
    }] })
    state.api.submit.mockRejectedValueOnce(Object.assign(new Error('attachment'), {
      code: 'competition_attachment_required', status: 409,
    }))
    const wrapper = mount(CompetitionWorkflow, { attachTo: document.body })
    await flushPromises()
    await wrapper.findAll('.record-actions button').find(button => button.text().includes('提交审核')).trigger('click')
    await flushPromises()
    expect(wrapper.get('.error-summary').text()).toContain('请先上传证明原件')
    await wrapper.get('.error-summary button').trigger('click')
    expect(wrapper.get('.upload-area input').element).toBe(document.activeElement)

    state.api.createRecord.mockRejectedValueOnce(Object.assign(new Error('duplicate'), {
      code: 'duplicate_submission', status: 409,
    }))
    await wrapper.get('#competition-select').setValue('c09')
    await flushPromises()
    await wrapper.get('#project-name').setValue('重复作品')
    await wrapper.get('#award-date').setValue('2027-05-20')
    await wrapper.get('#event-year').setValue('2027')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(state.api.createRecord).toHaveBeenCalledTimes(1)
    expect(wrapper.get('.error-summary').text()).toContain('该竞赛材料已提交')
    wrapper.unmount()
  })
})

describe('manual OCR fallback', () => {
  const draft = {
    id: 7,
    version: 1,
    status: 'draft',
    data: { competition_id: 'c09', project_name: '人工填写作品' },
    allowed_actions: ['edit', 'add_attachment', 'submit'],
  }

  beforeEach(() => {
    state.api.listRecords.mockResolvedValue({ records: [structuredClone(draft)] })
  })

  it('keeps confirmed facts visible while OCR is pending', async () => {
    state.api.getCompetitionOcr.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()
    const start = wrapper.findAll('button').find(button => button.text().includes('等待 OCR'))
    await start.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('OCR 状态：queued')
    expect(wrapper.text()).toContain('人工填写作品')
    expect(state.api.createRecord).not.toHaveBeenCalled()
  })

  it('shows failed and low-confidence results without replacing manual facts', async () => {
    const failed = mount(CompetitionWorkflow)
    await flushPromises()
    await failed.findAll('button').find(button => button.text().includes('等待 OCR')).trigger('click')
    await flushPromises()
    expect(failed.get('[data-test="ocr-notice-7"]').text()).toContain('人工填写')
    expect(failed.text()).toContain('人工填写作品')
    failed.unmount()

    state.api.getCompetitionOcr.mockResolvedValueOnce({
      job_id: 'job-1', status: 'completed', raw_result: { confidence: 0.42, project_name: '机器猜测' },
    })
    const low = mount(CompetitionWorkflow)
    await flushPromises()
    await low.findAll('button').find(button => button.text().includes('等待 OCR')).trigger('click')
    await flushPromises()
    expect(low.get('[data-test="ocr-notice-7"]').text()).toContain('置信度较低')
    expect(low.text()).toContain('人工填写作品')
    expect(low.text()).not.toContain('机器猜测')
  })

  it('keeps the manual form when the OCR service is unavailable', async () => {
    state.api.startCompetitionOcr.mockRejectedValueOnce(Object.assign(new Error('offline'), { status: 503 }))
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text().includes('等待 OCR')).trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-state="backend-unavailable"]').text()).toContain('问题不一定来自材料内容')
    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.text()).toContain('人工填写作品')
  })
})

describe('draft and correction editing', () => {
  const facts = {
    competition_id: 'c09', competition_name: '计算机设计大赛', project_name: '退回前作品',
    award_date: '2027-05-20', event_year: 2027, level: 'national', award: 'first_or_above',
    participation_mode: 'individual',
  }

  it('creates a correction, opens its draft, patches the current version and never posts a duplicate draft', async () => {
    const returned = { id: 21, version: 4, status: 'needs_correction', data: facts, allowed_actions: ['view', 'create_correction', 'abandon'] }
    const correction = { id: 22, version: 1, status: 'draft', data: facts, allowed_actions: ['edit', 'add_attachment', 'submit'] }
    state.api.listRecords
      .mockResolvedValueOnce({ records: [returned] })
      .mockResolvedValueOnce({ records: [returned, correction] })
      .mockResolvedValueOnce({ records: [returned, { ...correction, version: 2, data: { ...facts, project_name: '修正后作品' } }] })
    state.api.createCorrection.mockResolvedValueOnce(correction)

    const wrapper = mount(CompetitionWorkflow, { attachTo: document.body })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text().includes('修改并重提')).trigger('click')
    await flushPromises()

    expect(state.api.createCorrection).toHaveBeenCalledWith('competition', 21, 4, expect.objectContaining({ project_name: '退回前作品' }))
    expect(wrapper.get('[data-test="editing-notice"]').text()).toContain('版本 1')
    expect(wrapper.get('#project-name').element.value).toBe('退回前作品')
    expect(wrapper.get('#project-name').element).toBe(document.activeElement)

    await wrapper.get('#project-name').setValue('修正后作品')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(state.api.updateRecord).toHaveBeenCalledWith('competition', 22, 1, expect.objectContaining({ project_name: '修正后作品' }))
    expect(state.api.createRecord).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('uses the refreshed draft version for resubmission after an edit', async () => {
    const draft = { id: 31, version: 5, status: 'draft', data: facts, allowed_actions: ['edit', 'submit'] }
    const updated = { ...draft, version: 6, data: { ...facts, project_name: '版本六作品' } }
    state.api.listRecords
      .mockResolvedValueOnce({ records: [draft] })
      .mockResolvedValueOnce({ records: [updated] })
      .mockResolvedValueOnce({ records: [{ ...updated, version: 7, status: 'submitted', allowed_actions: ['withdraw'] }] })
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()
    await wrapper.get('[data-test="edit-31"]').trigger('click')
    await flushPromises()
    await wrapper.get('#project-name').setValue('版本六作品')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await wrapper.findAll('.record-actions button').find(button => button.text().includes('提交审核')).trigger('click')
    await flushPromises()

    expect(state.api.updateRecord).toHaveBeenCalledWith('competition', 31, 5, expect.any(Object))
    expect(state.api.submit).toHaveBeenCalledWith('competition', 31, 6)
  })

  it('preserves edited input when a stale PATCH is rejected', async () => {
    const draft = { id: 41, version: 2, status: 'draft', data: facts, allowed_actions: ['edit', 'submit'] }
    state.api.listRecords.mockResolvedValue({ records: [draft] })
    state.api.updateRecord.mockRejectedValueOnce(Object.assign(new Error('stale'), { code: 'version_conflict', status: 409 }))
    const wrapper = mount(CompetitionWorkflow)
    await flushPromises()
    await wrapper.get('[data-test="edit-41"]').trigger('click')
    await flushPromises()
    await wrapper.get('#project-name').setValue('尚未覆盖的输入')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-state="conflict"]').text()).toContain('刷新权威状态')
    expect(wrapper.get('#project-name').element.value).toBe('尚未覆盖的输入')
    expect(wrapper.get('[data-test="editing-notice"]').exists()).toBe(true)
    expect(state.api.createRecord).not.toHaveBeenCalled()
  })
})
