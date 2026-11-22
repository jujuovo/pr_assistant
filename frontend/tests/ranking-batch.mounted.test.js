// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { expect, it, vi } from 'vitest'
import RankingBatch from '../src/pages/common/statistics/RankingBatch.vue'
import workflowApi from '../src/services/workflowApi.js'

vi.mock('../src/services/workflowApi.js', () => ({
  default: { listRankings: vi.fn(), getRanking: vi.fn() }
}))

it('loads a linked authorized batch and lets users select another batch without typing IDs', async () => {
  workflowApi.listRankings.mockResolvedValue({ items: [
    { batch_id: 2, year: 2028, major_name: '计算机科学', version: 2, status: 'published' },
    { batch_id: 1, year: 2028, major_name: '计算机科学', version: 1, status: 'withdrawn' }
  ] })
  workflowApi.getRanking.mockImplementation(async id => ({
    status: 'published', entries: [{ student_id: 'S1', comprehensive_score: id === 2 ? '74.1333' : '75.8000', rank: 1 }]
  }))
  const router = createRouter({
    history: createMemoryHistory(), routes: [{ path: '/', component: RankingBatch }]
  })
  await router.push('/?batch_id=1')
  const wrapper = mount(RankingBatch, { global: { plugins: [router] } })
  await flushPromises()
  expect(wrapper.get('select').element.value).toBe('1')
  expect(wrapper.text()).toContain('75.8000')
  await wrapper.get('select').setValue('2')
  await flushPromises()
  expect(router.currentRoute.value.query.batch_id).toBe('2')
  expect(wrapper.text()).toContain('74.1333')
})

it('shows a clear message for a link outside the authorized batch options', async () => {
  workflowApi.getRanking.mockClear()
  workflowApi.listRankings.mockResolvedValue({ items: [] })
  const router = createRouter({
    history: createMemoryHistory(), routes: [{ path: '/', component: RankingBatch }]
  })
  await router.push('/?batch_id=999')
  const wrapper = mount(RankingBatch, { global: { plugins: [router] } })
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('没有查看权限')
  expect(workflowApi.getRanking).not.toHaveBeenCalled()
})
