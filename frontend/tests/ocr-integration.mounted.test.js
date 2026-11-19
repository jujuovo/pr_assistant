// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, test, expect, vi } from 'vitest'
const mocks = vi.hoisted(() => ({
  ocr: { getCategories: vi.fn(), recognize: vi.fn(), getJob: vi.fn(), confirmMaterial: vi.fn() },
  material: {
    getTypes: vi.fn(),
    listRecords: vi.fn(),
    review: vi.fn(),
    createManualRecord: vi.fn()
  }
}))
vi.mock('@/services/ocrApi.js', () => ({ default: mocks.ocr }))
vi.mock('@/services/materialApi.js', () => ({ default: mocks.material }))
import Upload from '../src/components/student/OcrUploadPreview.vue'
import Draft from '../src/components/student/OcrMaterialDraft.vue'
import ManualDraft from '../src/components/student/ManualMaterialDraft.vue'
import ManualReview from '../src/components/common/ManualMaterialReview.vue'
const result = {
  id: '01234567-1234-1234-1234-1234567890ab',
  category: 'csp',
  status: 'extracted',
  report: { fields: { name: '张三', total_score: 260 } },
  mapping: {
    material_category: 'certification',
    data: {
      certification_name: 'CCF CSP',
      subject_name: '张三',
      score: 260,
      full_score: 500,
      test_date: '2026-05-01',
      certificate_no: 'CERT-001'
    },
    warnings: [],
    missing_fields: []
  },
  artifact_urls: { original: '/api/ocr/jobs/1/images/original' }
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.ocr.getCategories.mockResolvedValue({ categories: [{ key: 'csp', name: 'CSP认证' }] })
  mocks.ocr.recognize.mockResolvedValue(result)
  mocks.ocr.getJob.mockResolvedValue(result)
  mocks.material.getTypes.mockResolvedValue({
    types: [
      {
        key: 'certification',
        required: ['certification_name', 'score', 'full_score', 'test_date', 'certificate_no']
      }
    ]
  })
  mocks.ocr.confirmMaterial.mockResolvedValue({ material: { id: 7, category: 'certification' } })
  mocks.material.listRecords.mockResolvedValue({ records: [] })
})

test('upload displays recognition first and only explicit use emits suggestions', async () => {
  const wrapper = mount(Upload)
  await flushPromises()
  await wrapper.get('select').setValue('csp')
  const input = wrapper.get('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [new File(['image'], 'proof.png')] })
  await input.trigger('change')
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('张三')
  expect(wrapper.emitted('use')).toBeUndefined()
  expect(mocks.ocr.confirmMaterial).not.toHaveBeenCalled()
  await wrapper.get('[data-test=use-ocr]').trigger('click')
  expect(wrapper.emitted('use')[0][0].id).toBe(result.id)
  wrapper.unmount()
})

test('failed recognition keeps the manual path and never emits guessed data', async () => {
  mocks.ocr.getJob.mockResolvedValue({
    ...result,
    status: 'failed',
    mapping: null,
    error: '图片模糊，请重新上传'
  })
  const wrapper = mount(Upload)
  await flushPromises()
  await wrapper.get('select').setValue('csp')
  const input = wrapper.get('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'proof.png')] })
  await input.trigger('change')
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.get('[role=alert]').text()).toContain('重新上传')
  expect(wrapper.emitted('use')).toBeUndefined()
  wrapper.unmount()
})

test('student correction is sent only after confirm and retained on version conflict', async () => {
  mocks.ocr.confirmMaterial.mockRejectedValue(
    Object.assign(new Error('已关联材料，请查看原记录'), { status: 409 })
  )
  const wrapper = mount(Draft)
  await flushPromises()
  wrapper.findComponent(Upload).vm.$emit('use', structuredClone(result))
  await flushPromises()
  const name = wrapper.findAll('label').find((label) => label.text().startsWith('姓名'))
  await name.get('input').setValue('学生修正姓名')
  expect(mocks.ocr.confirmMaterial).not.toHaveBeenCalled()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(mocks.ocr.confirmMaterial.mock.calls[0][1].data.subject_name).toBe('学生修正姓名')
  expect(wrapper.text()).toContain('已关联材料')
  expect(wrapper.emitted('saved')).toBeUndefined()
  expect(name.get('input').element.value).toBe('学生修正姓名')
  wrapper.unmount()
})

test('manual-only opt out retains evidence and never submits a formal competition score request', async () => {
  const formal = {
    ...structuredClone(result),
    mapping: {
      ...result.mapping,
      material_category: 'competition',
      data: { competition_id: 'c28-ccf-csp', evidence: result.mapping.data }
    }
  }
  const wrapper = mount(Draft)
  await flushPromises()
  wrapper.findComponent(Upload).vm.$emit('use', formal)
  await flushPromises()
  const button = wrapper.findAll('button').find((b) => b.text().includes('不申请计分'))
  await button.trigger('click')
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(mocks.ocr.confirmMaterial.mock.calls[0][1].manual_only).toBe(true)
  expect(mocks.ocr.confirmMaterial.mock.calls[0][1].data.score).toBe(260)
  expect(wrapper.emitted('saved')).toHaveLength(1)
  wrapper.unmount()
})

test('manual teacher review requires an opinion and preserves failed-command context', async () => {
  mocks.material.listRecords.mockResolvedValue({
    records: [
      {
        id: 7,
        student_id: 'S1',
        status: 'submitted',
        version: 2,
        manual_only: true,
        data: { team: '测试实践队' },
        attachments: [],
        ocr_raw_terms: { fields: { team: 'OCR队名' } }
      }
    ]
  })
  mocks.material.review.mockRejectedValue(Object.assign(new Error('版本已变化'), { status: 409 }))
  const wrapper = mount(ManualReview)
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '核验通过')
    .trigger('click')
  expect(mocks.material.review).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('填写具体')
  await wrapper.get('textarea').setValue('已核对学校平台')
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '核验通过')
    .trigger('click')
  await flushPromises()
  expect(mocks.material.review).toHaveBeenCalledWith(
    'social_practice',
    7,
    2,
    'verified',
    '已核对学校平台'
  )
  expect(wrapper.text()).toContain('版本已变化')
  expect(wrapper.get('textarea').element.value).toBe('已核对学校平台')
  wrapper.unmount()
})

test('manual-only entry saves fields and originals with one request and never invokes OCR', async () => {
  mocks.material.getTypes.mockResolvedValue({
    types: [{ key: 'research', required: ['document_type', 'report_no', 'database'] }]
  })
  mocks.material.createManualRecord.mockResolvedValue({
    id: 8,
    category: 'research',
    manual_only: true,
    attachments: [{ id: 1 }]
  })
  const wrapper = mount(ManualDraft, { props: { category: 'research' } })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  const report = wrapper.findAll('label').find((l) => l.text().startsWith('报告编号'))
  await report.get('input').setValue('R-001')
  const database = wrapper.findAll('label').find((l) => l.text().startsWith('检索数据库'))
  await database.get('input').setValue('WoS')
  const input = wrapper.get('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [new File(['proof'], 'proof.pdf')] })
  await input.trigger('change')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(mocks.material.createManualRecord).toHaveBeenCalledTimes(1)
  expect(mocks.ocr.recognize).not.toHaveBeenCalled()
  expect(wrapper.emitted('saved')).toHaveLength(1)
  wrapper.unmount()
})
