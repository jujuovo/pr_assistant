// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
const mocks = vi.hoisted(() => ({
  api: {
    listRecords: vi.fn(),
    getRecord: vi.fn(),
    getTypes: vi.fn(),
    createManualRecord: vi.fn(),
    appealVolunteer: vi.fn(),
    startVolunteerOcr: vi.fn(),
    submit: vi.fn(),
    review: vi.fn(),
    getEvents: vi.fn()
  },
  router: { replace: vi.fn(), push: vi.fn() },
  route: { query: { page: 'materials', category: 'volunteer' } }
}))
vi.mock('vue-router', () => ({ useRouter: () => mocks.router, useRoute: () => mocks.route }))
vi.mock('@/services/materialApi.js', () => ({
  default: mocks.api,
  MATERIAL_CATEGORIES: ['volunteer']
}))
import Hub from '../src/pages/student/applications/StudentMaterialsHub.vue'
import Review from '../src/components/common/ManualMaterialReview.vue'
import Draft from '../src/components/student/ManualMaterialDraft.vue'
import Workflow from '../src/pages/student/applications/MaterialWorkflow.vue'
const base = {
  id: 31,
  category: 'volunteer',
  student_id: 'S1',
  year: 2028,
  version: 4,
  status: 'needs_correction',
  workflow_state: 'needs_correction',
  updated_at: '2026-11-20T10:00:00Z',
  data: { regular_hours: '202', reduced_hours: '0', award_date: '2026-05-08' },
  attachments: [{ id: 1, filename: 'proof.png', url: '/original.png' }],
  allowed_actions: ['view', 'edit', 'appeal', 'recognize'],
  volunteer_ocr: {
    status: 'returned',
    auto_returned: true,
    reasons: ['普通志愿服务工时与申报信息不一致'],
    comparisons: [
      {
        field: 'regular_hours',
        label: '普通志愿服务工时',
        declared: '202',
        recognized: '200',
        matches: false
      }
    ]
  },
  ocr_raw_terms: {
    reports: [
      {
        job_id: 'j1',
        filename: 'proof.png',
        report: { fields: { hours: '200', service_type: 'regular', award_date: '2026-05-08' } }
      }
    ]
  }
}
let wrappers = []
const render = (component, props = {}) => {
  const w = mount(component, {
    props,
    attachTo: document.body,
    global: { stubs: { ApplicationHistory: true } }
  })
  wrappers.push(w)
  return w
}
const button = (w, text) => w.findAll('button').find((b) => b.text() === text)
beforeEach(() => {
  vi.resetAllMocks()
  mocks.api.listRecords.mockImplementation(async (c) => ({
    records: c === 'volunteer' ? [structuredClone(base)] : []
  }))
  mocks.api.getTypes.mockResolvedValue({
    cycle_code: 2028,
    types: [
      {
        key: 'volunteer',
        required: ['award_date'],
        fields: ['regular_hours', 'reduced_hours', 'award_date']
      }
    ]
  })
  mocks.api.appealVolunteer.mockResolvedValue({})
  mocks.api.createManualRecord.mockResolvedValue({ ...base, workflow_state: 'ocr_queued' })
  mocks.api.review.mockResolvedValue({})
})
afterEach(() => {
  wrappers.forEach((w) => w.unmount())
  wrappers = []
  vi.useRealTimers()
  document.body.innerHTML = ''
})

test('returned material shows exact differences and appeal, never offers regular submit', async () => {
  const w = render(Hub)
  await flushPromises()
  expect(w.text()).toContain('工时与申报信息不一致')
  expect(w.text()).toContain('200')
  expect(button(w, '正式提交审核')).toBeUndefined()
  await button(w, '提出申诉').trigger('click')
  expect(w.get('textarea').attributes('required')).toBeDefined()
  await w.get('.appeal-form').trigger('submit')
  await flushPromises()
  expect(mocks.api.appealVolunteer).not.toHaveBeenCalled()
  expect(w.text()).toContain('请填写申诉理由')
  await w.get('textarea').setValue('  识别有误，请核对原件  ')
  await w.get('.appeal-form').trigger('submit')
  await flushPromises()
  expect(mocks.api.appealVolunteer).toHaveBeenCalledWith(31, 4, '识别有误，请核对原件')
  expect(w.text()).toContain('已转人工审核并标记为重点核验')
  expect(w.find('textarea').exists()).toBe(false)
})

test('appeal conflict and API failure retain student reason with an actionable error', async () => {
  mocks.api.appealVolunteer.mockRejectedValue(Object.assign(new Error('conflict'), { status: 409 }))
  const w = render(Hub)
  await flushPromises()
  await button(w, '提出申诉').trigger('click')
  await w.get('textarea').setValue('保留这段申诉理由')
  await w.get('.appeal-form').trigger('submit')
  await flushPromises()
  expect(w.get('textarea').element.value).toBe('保留这段申诉理由')
  expect(w.get('[role=alert]').text()).toContain('刷新后重试')
})

test('queued OCR survives history refresh and becomes ready after background polling', async () => {
  vi.useFakeTimers()
  mocks.api.listRecords.mockResolvedValue({
    records: [
      {
        ...base,
        status: 'draft',
        workflow_state: 'ocr_queued',
        allowed_actions: ['view'],
        volunteer_ocr: { status: 'queued' }
      }
    ]
  })
  mocks.api.getRecord.mockResolvedValue({
    ...base,
    status: 'draft',
    workflow_state: 'ready_to_submit',
    allowed_actions: ['submit'],
    volunteer_ocr: { status: 'matched' }
  })
  const w = render(Hub)
  await flushPromises()
  expect(w.text()).toContain('OCR队列中')
  expect(button(w, '正式提交审核')).toBeUndefined()
  await vi.advanceTimersByTimeAsync(5000)
  await flushPromises()
  expect(mocks.api.getRecord).toHaveBeenCalledWith('volunteer', 31)
  expect(w.text()).toContain('字段一致')
  await button(w, '正式提交审核').trigger('click')
  await flushPromises()
  expect(mocks.api.submit).toHaveBeenCalledWith('volunteer', 31, 4)
})

test('retry invokes volunteer OCR instead of a competition endpoint', async () => {
  const w = render(Hub)
  await flushPromises()
  await button(w, '重新识别').trigger('click')
  await flushPromises()
  expect(mocks.api.startVolunteerOcr).toHaveBeenCalledWith(31, 4)
})

test('teacher sees priority appeal before ordinary material and may approve without comment', async () => {
  const appeal = {
    ...base,
    status: 'submitted',
    allowed_actions: ['review'],
    workflow_state: 'pending_review',
    priority_review: true,
    appeal: { reason: '请重点核对图片中的202小时' }
  }
  mocks.api.listRecords.mockResolvedValue({
    records: [{ ...appeal, id: 32, priority_review: false, appeal: null }, appeal]
  })
  const w = render(Review)
  await flushPromises()
  await w.get('select').setValue('volunteer')
  await flushPromises()
  expect(w.findAll('article')[0].text()).toContain('材料 #31')
  expect(w.text()).toContain('申诉材料 · 重点核验')
  expect(w.text()).toContain('请重点核对图片中的202小时')
  expect(w.text()).toContain('普通志愿服务工时与申报信息不一致')
  await button(w.findAll('article')[0], '核验通过').trigger('click')
  await flushPromises()
  expect(mocks.api.review).toHaveBeenCalledWith('volunteer', 31, 4, 'verified', '')
})

test('volunteer upload stays manual input with one upload and an explicit background OCR action', async () => {
  const w = render(Draft, { category: 'volunteer' })
  expect(w.text()).not.toContain('不使用识别')
  await button(w, '填写志愿服务材料').trigger('click')
  await flushPromises()
  expect(w.findAll('input[type=date]')).toHaveLength(1)
  expect(w.findAll('.volunteer-fields')).toHaveLength(1)
  expect(w.find('.fields-editor').exists()).toBe(false)
  const labels = w.findAll('label')
  await labels
    .find((l) => l.text().startsWith('本次工时（小时）'))
    .get('input')
    .setValue('202')
  await labels
    .find((l) => l.text().startsWith('服务记录日期'))
    .get('input')
    .setValue('2026-05-08')
  const upload = w.get('input[type=file]')
  Object.defineProperty(upload.element, 'files', { value: [new File(['image'], 'proof.png')] })
  await upload.trigger('change')
  expect(button(w, '保存并后台识别')).toBeDefined()
  await w.get('form').trigger('submit')
  await flushPromises()
  expect(mocks.api.createManualRecord.mock.calls[0].slice(0, 3)).toEqual([
    'volunteer',
    2028,
    { award_date: '2026-05-08', regular_hours: '202', reduced_hours: '0' }
  ])
  expect(w.emitted('saved')).toHaveLength(1)
})

test.each([
  'volunteer',
  'social_practice',
  'research',
  'student_work',
  'certification',
  'competition_evidence'
])(
  'proof upload for %s displays a clickable thumbnail without triggering a submission',
  async (category) => {
    mocks.api.getTypes.mockResolvedValue({
      cycle_code: 2028,
      types: [{ key: category, required: ['award_date'], fields: ['award_date'] }]
    })
    const w = render(Draft, { category })
    await w.get('button').trigger('click')
    await flushPromises()
    const input = w.get('input[type=file]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['image'], 'proof.jpg', { type: 'image/jpeg' })]
    })
    await input.trigger('change')
    await flushPromises()
    expect(w.get('.thumbnail img').attributes('alt')).toContain('proof.jpg')
    await w.get('[aria-label="放大预览：proof.jpg"]').trigger('click')
    await flushPromises()
    expect(document.querySelector('[role=dialog] img')).not.toBeNull()
    expect(mocks.api.createManualRecord).not.toHaveBeenCalled()
    document.querySelector('.close-preview').click()
    await flushPromises()
    expect(document.querySelector('[role=dialog]')).toBeNull()
  }
)

test('a selected volunteer module has its own title and no unrelated category selector', async () => {
  const w = render(Workflow)
  await flushPromises()
  expect(w.get('h1').text()).toBe('提交志愿服务累计工时')
  expect(w.find('select').exists()).toBe(false)
  expect(w.text()).not.toContain('目录外竞赛材料')
})

test('partial OCR shows the real hours while missing policy fields remain unknown', async () => {
  mocks.api.listRecords.mockResolvedValue({
    records: [
      {
        ...base,
        volunteer_ocr: {
          status: 'returned',
          reasons: ['工时类别未可靠识别，无法核对'],
          comparisons: [
            {
              field: 'hours',
              label: '本次工时（小时）',
              declared: '5.05',
              recognized: '5.05',
              matches: true
            },
            {
              field: 'service_type',
              label: '工时类别',
              declared: '普通志愿服务',
              recognized: null,
              matches: false,
              reason: 'missing'
            }
          ]
        },
        ocr_raw_terms: {
          reports: [
            {
              job_id: 'j1',
              filename: 'example2.jpg',
              report: {
                fields: {
                  hours: '5.05',
                  check_in: '2025-12-21T12:33:03',
                  check_out: '2025-12-21T17:36:34'
                }
              }
            }
          ]
        }
      }
    ]
  })
  const w = render(Hub)
  await flushPromises()
  expect(w.text()).toContain('5.05')
  expect(w.text()).toContain('未识别，无法核对')
  expect(w.text()).toContain('签到时间')
  expect(w.text()).toContain('签退时间')
  expect(button(w, '提出申诉')).toBeDefined()
})

test.each([
  ['credit', '信用时数', '5.05', '2025-12-21'],
  ['honor', '荣誉时数', '12', '2026-09-14']
])(
  '%s platform shows all three matching fields and permits formal submission',
  async (kind, title, hours, day) => {
    const comparisons = [
      {
        field: 'hours',
        label: '本次工时（小时）',
        declared: hours,
        recognized: hours,
        matches: true
      },
      {
        field: 'service_type',
        label: '工时类别',
        declared: '普通志愿服务',
        recognized: '普通志愿服务',
        matches: true
      },
      { field: 'award_date', label: '服务记录日期', declared: day, recognized: day, matches: true }
    ]
    mocks.api.listRecords.mockResolvedValue({
      records: [
        {
          ...base,
          status: 'draft',
          workflow_state: 'ready_to_submit',
          allowed_actions: ['view', 'edit', 'submit'],
          data: { regular_hours: hours, reduced_hours: '0', award_date: day },
          volunteer_ocr: { status: 'matched', reasons: [], comparisons },
          ocr_raw_terms: {
            reports: [
              {
                job_id: 'policy-job',
                filename: 'proof.jpg',
                report: {
                  fields: { hours, service_type: 'regular', award_date: day },
                  platform_policy: { page_type: kind, description: title + '按普通志愿服务核对' }
                }
              }
            ]
          }
        }
      ]
    })
    const w = render(Hub)
    await flushPromises()
    const rows = w.findAll('.volunteer-assessment tbody tr')
    expect(rows).toHaveLength(3)
    rows.forEach((row) => expect(row.findAll('td').at(-1).text()).toBe('一致'))
    expect(w.text()).toContain('服务记录日期')
    expect(w.text()).not.toContain('系统录入并审核通过日期')
    expect(button(w, '提出申诉')).toBeUndefined()
    await button(w, '正式提交审核').trigger('click')
    await flushPromises()
    expect(mocks.api.submit).toHaveBeenCalledWith('volunteer', 31, 4)
  }
)
