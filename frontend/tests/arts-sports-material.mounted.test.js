// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, test, vi } from 'vitest'
import { submissionQuery } from '../src/services/materialWorkflowRoutes.js'

const mocks = vi.hoisted(() => ({
  api: {
    getTypes: vi.fn(),
    createManualRecord: vi.fn(),
    listRecords: vi.fn(),
    submit: vi.fn(),
    review: vi.fn(),
    getRecord: vi.fn(),
    updateRecord: vi.fn(),
    getEvents: vi.fn(),
    startVolunteerOcr: vi.fn(),
    startCompetitionOcr: vi.fn()
  },
  route: { query: { category: 'arts_sports', editId: '1' } },
  router: { replace: vi.fn(), push: vi.fn() }
}))
vi.mock('vue-router', () => ({ useRouter: () => mocks.router, useRoute: () => mocks.route }))
vi.mock('@/services/materialApi.js', () => ({
  default: mocks.api,
  MATERIAL_CATEGORIES: ['arts_sports']
}))

import ManualMaterialDraft from '../src/components/student/ManualMaterialDraft.vue'
import StudentMaterialsHub from '../src/pages/student/applications/StudentMaterialsHub.vue'
import ManualMaterialReview from '../src/components/common/ManualMaterialReview.vue'
import MaterialWorkflow from '../src/pages/student/applications/MaterialWorkflow.vue'

const DOCUMENT_TYPES = [
  { value: 'arts_competition', label: '文体竞赛' },
  { value: 'performance', label: '表演展示' },
  { value: 'arts_honor', label: '文体表彰' },
  { value: 'dorm_honor', label: '文明宿舍表彰' },
  { value: 'fitness_test', label: '体质健康测试' }
]
const TYPES = {
  cycle_code: 2028,
  types: [
    {
      key: 'arts_sports',
      name: '文体活动',
      required: ['document_type', 'project_name', 'award_date'],
      fields: ['document_type', 'project_name', 'award_date', 'reference_id'],
      document_types: DOCUMENT_TYPES
    }
  ]
}
const BASE_ROW = {
  id: 1,
  category: 'arts_sports',
  student_id: 'S1',
  year: 2028,
  version: 1,
  status: 'draft',
  workflow_state: 'draft',
  manual_only: true,
  data: {
    document_type: 'arts_competition',
    project_name: '校运会田径比赛',
    award_date: '2026-05-01',
    reference_id: ''
  },
  attachments: [{ id: 1, filename: 'proof.png', url: '/proof.png' }],
  allowed_actions: ['view', 'download_attachment', 'edit', 'add_attachment', 'submit']
}

beforeEach(() => {
  vi.resetAllMocks()
  mocks.route.query = { category: 'arts_sports', editId: '1' }
  mocks.api.getTypes.mockResolvedValue(TYPES)
  mocks.api.createManualRecord.mockResolvedValue({ id: 1, version: 1 })
  mocks.api.listRecords.mockResolvedValue({ records: [] })
  mocks.api.submit.mockResolvedValue({ id: 1 })
  mocks.api.review.mockResolvedValue({ id: 1 })
  mocks.api.getRecord.mockResolvedValue(structuredClone(BASE_ROW))
  mocks.api.updateRecord.mockResolvedValue({ id: 1, version: 2 })
  mocks.api.getEvents.mockResolvedValue({ events: [] })
})

function optionValues(wrapper) {
  return wrapper
    .get('select')
    .findAll('option')
    .map((option) => option.element.value)
}

test('文体活动分类路由到材料工作台而不是旧申请表单', () => {
  expect(submissionQuery('arts-sports')).toEqual({ page: 'materials', category: 'arts_sports' })
})

test('文体活动表单保留五个提交项并保存草稿', async () => {
  const wrapper = mount(ManualMaterialDraft, { props: { category: 'arts_sports' } })
  await wrapper.get('button').trigger('click')
  await flushPromises()

  expect(optionValues(wrapper)).toEqual(['', ...DOCUMENT_TYPES.map((item) => item.value)])
  await wrapper.get('select').setValue('arts_competition')
  await wrapper.get('input[type="text"]').setValue('校运会田径比赛')
  await wrapper.get('input[type="date"]').setValue('2026-05-01')
  const fileInput = wrapper.get('input[type="file"]')
  fileInput.element.files = [new File(['proof'], 'proof.png', { type: 'image/png' })]
  expect(fileInput.element.files).toHaveLength(1)
  await fileInput.trigger('change')
  expect(wrapper.text()).not.toContain('请提供证明原件')
  const save = wrapper.findAll('button').find((button) => button.text().includes('保存人工材料草稿'))
  expect(save).toBeTruthy()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(mocks.api.createManualRecord).toHaveBeenCalledTimes(1)
  const [category, year, data, files] = mocks.api.createManualRecord.mock.calls[0]
  expect(category).toBe('arts_sports')
  expect(typeof year).toBe('number')
  expect(data.document_type).toBe('arts_competition')
  expect(data.project_name).toBe('校运会田径比赛')
  expect(data.award_date).toBe('2026-05-01')
  expect(files).toHaveLength(1)
})

test('我的材料显示文体活动草稿并可正式提交', async () => {
  mocks.api.listRecords.mockImplementation(async (category) => ({
    records: category === 'arts_sports' ? [structuredClone(BASE_ROW)] : []
  }))
  const wrapper = mount(StudentMaterialsHub, {
    global: { stubs: { ApplicationHistory: true } }
  })
  await flushPromises()

  expect(wrapper.text()).toContain('校运会田径比赛')
  const submit = wrapper.findAll('button').find((button) => button.text().includes('正式提交审核'))
  expect(submit).toBeTruthy()
  await submit.trigger('click')
  await flushPromises()
  expect(mocks.api.submit).toHaveBeenCalledWith('arts_sports', 1, 1)
})

test('教师核验文体活动时退回必须填写意见', async () => {
  const submitted = { ...structuredClone(BASE_ROW), status: 'submitted', workflow_state: 'pending_review' }
  mocks.api.listRecords.mockImplementation(async (category) => ({
    records: category === 'arts_sports' ? [submitted] : []
  }))
  const wrapper = mount(ManualMaterialReview)
  await flushPromises()
  await wrapper.get('select').setValue('arts_sports')
  await flushPromises()

  const returnButton = wrapper.findAll('button').find((button) => button.text() === '退回补充')
  expect(returnButton).toBeTruthy()
  await returnButton.trigger('click')
  await flushPromises()
  expect(mocks.api.review).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('请先填写具体的核验意见')

  await wrapper.get('textarea').setValue('请补充秩序册')
  await returnButton.trigger('click')
  await flushPromises()
  expect(mocks.api.review).toHaveBeenCalledWith(
    'arts_sports',
    1,
    1,
    'needs_correction',
    '请补充秩序册'
  )
})

test('编辑文体活动草稿时仍显示五个提交项', async () => {
  const wrapper = mount(MaterialWorkflow)
  await flushPromises()
  expect(optionValues(wrapper)).toEqual(['', ...DOCUMENT_TYPES.map((item) => item.value)])
  expect(wrapper.get('input[type="text"]').element.value).toBe('校运会田径比赛')
})

test('教师人工核验默认汇总全部类别并可按类别筛选', async () => {
  const arts = { ...structuredClone(BASE_ROW), status: 'submitted', workflow_state: 'pending_review' }
  const social = {
    ...structuredClone(BASE_ROW),
    id: 2,
    category: 'social_practice',
    status: 'submitted',
    workflow_state: 'pending_review',
    data: { document_type: 'practice_proof', team: '测试实践队' }
  }
  mocks.api.listRecords.mockImplementation(async (category) => ({
    records:
      category === 'arts_sports' ? [arts] : category === 'social_practice' ? [social] : []
  }))
  const wrapper = mount(ManualMaterialReview)
  await flushPromises()
  expect(wrapper.text()).toContain('材料 #1')
  expect(wrapper.text()).toContain('材料 #2')

  const artsArticle = wrapper.findAll('article').find((article) => article.text().includes('材料 #1'))
  expect(artsArticle).toBeTruthy()
  await artsArticle
    .findAll('button')
    .find((button) => button.text() === '核验通过')
    .trigger('click')
  await flushPromises()
  expect(mocks.api.review).toHaveBeenCalledWith('arts_sports', 1, 1, 'verified', '')

  await wrapper.get('select').setValue('social_practice')
  await flushPromises()
  expect(wrapper.text()).toContain('材料 #2')
  expect(wrapper.text()).not.toContain('材料 #1')
})
