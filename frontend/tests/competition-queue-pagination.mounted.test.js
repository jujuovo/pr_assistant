// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, test, vi } from 'vitest'
const state = vi.hoisted(() => ({ api: { getCompetitionWorkbenchSummary: vi.fn() } }))
vi.mock('@/services/materialApi.js', () => ({ default: state.api }))
import Review from '../src/pages/teacher/reviews/TeacherCompetitionReview.vue'
beforeEach(() => vi.resetAllMocks())

test.each(['pending', 'history'])('%s can load past 50 records without losing earlier pages', async mode => {
  const key = mode === 'history' ? 'reviewed_items' : 'items'
  const cursor = mode === 'history' ? 'reviewed_next_before_id' : 'next_before_id'
  const first = Array.from({ length: 50 }, (_, i) => ({ id: 100-i, student_id: 'S'+i, status: mode === 'history' ? 'scored' : 'submitted', project_name: '项目'+i }))
  state.api.getCompetitionWorkbenchSummary
    .mockResolvedValueOnce({ pending_count: 70, [key]: first, [cursor]: 51 })
    .mockResolvedValueOnce({ [key]: [first[49], { id: 50, student_id: 'S50', project_name: '下一页项目' }], [cursor]: null })
  const wrapper = mount(Review, { props: { mode, detailsActive: false } })
  await flushPromises()
  expect(wrapper.findAll('.pending-card')).toHaveLength(50)
  await wrapper.get('[data-test=load-more-competition]').trigger('click')
  await flushPromises()
  expect(wrapper.findAll('.pending-card')).toHaveLength(51)
  expect(wrapper.text()).toContain(mode === 'history' ? '下一页项目' : '学生 S50 · 材料 #50')
  expect(wrapper.find('[data-test=load-more-competition]').exists()).toBe(false)
  expect(state.api.getCompetitionWorkbenchSummary).toHaveBeenLastCalledWith(undefined, undefined,
    mode === 'history' ? { reviewedBeforeId: 51 } : { beforeId: 51 })
  wrapper.unmount()
})

test('failed next page keeps current records and permits retry', async () => {
  state.api.getCompetitionWorkbenchSummary
    .mockResolvedValueOnce({ items: [{ id: 2, project_name: '保留材料' }], next_before_id: 2 })
    .mockRejectedValueOnce(new Error('网络暂不可用'))
    .mockResolvedValueOnce({ items: [{ id: 1, project_name: '重试成功' }], next_before_id: null })
  const wrapper = mount(Review, { props: { detailsActive: false } })
  await flushPromises()
  await wrapper.get('[data-test=load-more-competition]').trigger('click')
  await flushPromises()
  expect(wrapper.get('[role=alert]').text()).toContain('网络暂不可用')
  expect(wrapper.findAll('.pending-card')).toHaveLength(1)
  await wrapper.get('[data-test=load-more-competition]').trigger('click')
  await flushPromises()
  expect(wrapper.findAll('.pending-card')).toHaveLength(2)
  expect(wrapper.find('[role=alert]').exists()).toBe(false)
  wrapper.unmount()
})
