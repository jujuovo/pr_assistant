// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { expect, test, vi } from 'vitest'
import TeacherRanking from '../src/pages/teacher/rankings/TeacherRanking.vue'

const { listRankings, getRanking, openExport, exportReport } = vi.hoisted(() => ({
  listRankings: vi.fn(),
  getRanking: vi.fn(),
  openExport: vi.fn(),
  exportReport: vi.fn()
}))
vi.mock('@/services/workflowApi.js', () => ({ default: { listRankings, getRanking } }))
vi.mock('@/pages/common/statistics/StatisticsReport.vue', () => ({
  default: {
    props: ['hidden', 'canExportRanking'],
    emits: ['export-ranking'],
    methods: { exportReport },
    template: `<div><input aria-label="专业筛选">
      <button :disabled="hidden && !canExportRanking" @click="hidden ? $emit('export-ranking') : exportReport()">导出统计报表</button>
      <slot name="filter-actions" />
      <slot v-if="hidden" name="ranking" :scope="{ majorId: 3, year: 2028 }" />
    </div>`
  }
}))
vi.mock('@/components/common/RankingExport.vue', () => ({
  default: { template: '<div></div>', methods: { open: openExport } }
}))

test('switches export modes, prefers the newest batch and preserves report filters', async () => {
  listRankings.mockResolvedValue({
    items: [{ batch_id: 2, status: 'draft' }, { batch_id: 1, status: 'published' }]
  })
  getRanking.mockImplementation(async (id) => ({
    batch_id: id,
    entries: [{ student_id: 'S1', rank: 1, comprehensive_score: 90 }],
    allowed_actions: id === 2 ? ['export'] : []
  }))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: TeacherRanking }]
  })
  await router.push('/?page=statistics-report')
  const view = mount(TeacherRanking, { global: { plugins: [router] } })
  await view.get('[aria-label="专业筛选"]').setValue('软件工程')
  const exportButton = view.get('button')
  await exportButton.trigger('click')
  expect(exportReport).toHaveBeenCalledTimes(1)
  expect(getRanking).not.toHaveBeenCalled()

  const toggle = view.get('input[type="checkbox"]')
  await toggle.setValue(true)
  await flushPromises()
  expect(getRanking).toHaveBeenLastCalledWith(2, expect.any(AbortSignal))
  expect(view.get('table').text()).toContain('S1')
  expect(view.get('button').element).toBe(exportButton.element)
  await exportButton.trigger('click')
  expect(openExport).toHaveBeenCalledWith(expect.objectContaining({ batch_id: 2 }))
  await view.get('select').setValue('1')
  await flushPromises()
  expect(getRanking).toHaveBeenLastCalledWith(1, expect.any(AbortSignal))
  expect(exportButton.element.disabled).toBe(true)
  expect(openExport).toHaveBeenCalledTimes(1)

  await toggle.setValue(false)
  await flushPromises()
  expect(view.find('table').exists()).toBe(false)
  await exportButton.trigger('click')
  expect(exportReport).toHaveBeenCalledTimes(2)
  expect(view.get('[aria-label="专业筛选"]').element.value).toBe('软件工程')
  expect(router.currentRoute.value.query.batch_id).toBeUndefined()

  await router.push('/?page=rankings&batch_id=1')
  await flushPromises()
  expect(toggle.element.checked).toBe(true)
  expect(getRanking).toHaveBeenLastCalledWith(1, expect.any(AbortSignal))
  view.unmount()
})
