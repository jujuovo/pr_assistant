// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
const api = vi.hoisted(() => ({ getTypes: vi.fn(), createManualRecord: vi.fn(), listRecords: vi.fn(), review: vi.fn() }))
vi.mock('@/services/materialApi.js', () => ({ default: api }))
import Draft from '../src/components/student/ManualMaterialDraft.vue'
import Review from '../src/components/common/ManualMaterialReview.vue'

beforeEach(() => vi.resetAllMocks())

it('saves one ordinary volunteer event without requiring reduced hours', async () => {
  api.getTypes.mockResolvedValue({ cycle_code: 2028, types: [{ key: 'volunteer', fields: ['regular_hours','reduced_hours','award_date'], required: ['award_date'] }] })
  api.createManualRecord.mockResolvedValue({ id: 1 })
  const wrapper = mount(Draft, { props: { category: 'volunteer' } })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  await wrapper.get('input[type=number][step]').setValue('8')
  await wrapper.get('input[type=date]').setValue('2028-08-01')
  const file = new File(['report'], 'report.pdf', { type: 'application/pdf' })
  Object.defineProperty(wrapper.get('input[type=file]').element, 'files', { value: [file] })
  await wrapper.get('input[type=file]').trigger('change')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(api.createManualRecord).toHaveBeenCalledExactlyOnceWith('volunteer', 2028,
    { regular_hours:'8', reduced_hours:'0', award_date:'2028-08-01' }, [file])
  expect(wrapper.emitted('saved')).toHaveLength(1)
  wrapper.unmount()
})

it('saves one large-event record without requiring ordinary hours', async () => {
  api.getTypes.mockResolvedValue({ cycle_code: 2028, types: [{ key: 'volunteer', fields: ['regular_hours','reduced_hours','award_date'], required: ['award_date'] }] })
  api.createManualRecord.mockResolvedValue({ id: 2 })
  const wrapper = mount(Draft, { props: { category: 'volunteer' } })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  await wrapper.get('select').setValue('reduced')
  await wrapper.get('input[type=number][step]').setValue('6')
  await wrapper.get('input[type=date]').setValue('2028-08-01')
  const file = new File(['proof'], 'proof.pdf', { type: 'application/pdf' })
  Object.defineProperty(wrapper.get('input[type=file]').element, 'files', { value: [file] })
  await wrapper.get('input[type=file]').trigger('change')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(api.createManualRecord).toHaveBeenCalledExactlyOnceWith('volunteer', 2028,
    { regular_hours:'0', reduced_hours:'6', award_date:'2028-08-01' }, [file])
  wrapper.unmount()
})

it('teacher approves an individual event without selecting a rule or writing a score', async () => {
  api.listRecords.mockResolvedValue({ records: [] })
  const wrapper=mount(Review)
  await flushPromises()
  api.listRecords.mockResolvedValueOnce({ records: [{ id:4, category:'volunteer', student_id:'S1', status:'submitted', version:2, data:{regular_hours:'8'}, attachments:[], analysis:{submitted_hours:{effective_hours:'8'}}, allowed_actions:['view','download_attachment','review'] }] })
  await wrapper.get('select').setValue('volunteer')
  await flushPromises()
  expect(wrapper.text()).toContain('本次有效工时：8')
  await wrapper.findAll('button').find(x => x.text()==='核验通过').trigger('click')
  await flushPromises()
  expect(api.review).toHaveBeenCalledExactlyOnceWith('volunteer',4,2,'verified','')
  wrapper.unmount()
})
