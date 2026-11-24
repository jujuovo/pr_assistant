// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'

const importAcademicScores = vi.hoisted(() => vi.fn())
vi.mock('@/services/api.js', () => ({
  default: {
    importAcademicScores,
    getFacultiesAdmin: async () => ({ faculties: [] }),
    getDepartmentsAdmin: async () => ({ departments: [] }),
    getMajorsAdmin: async () => ({ majors: [] }),
    getFacultyScoreSettings: async () => ({ settings: [] })
  }
}))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => ({ user: {} }) }))
vi.mock('@/stores/toast.js', () => ({ useToastStore: () => ({ error: vi.fn() }) }))
vi.mock('@/stores/applications.js', () => ({
  useApplicationsStore: () => ({ fetchStudentsRanking: async () => ({ students: [] }) })
}))

import ScoreManagement from '../src/pages/admin/scores/ScoreManagement.vue'
import AcademicScoreImport from '../src/pages/admin/scores/AcademicScoreImport.vue'

test('previews missing values and confirms only after an explicit action', async () => {
  importAcademicScores.mockResolvedValueOnce({
    token: 'preview-token', ready_count: 1,
    rows: [
      { line: 2, student_id: 'sample2602', name: '测试学生02', previous: null, score: 0, issues: [] },
      { line: 3, student_id: '', name: '测试学生04', previous: null, score: null, issues: ['缺少学号', '未提供学业成绩'] }
    ]
  }).mockResolvedValueOnce({ imported_count: 1, skipped_count: 1 })
  const wrapper = mount(AcademicScoreImport)
  const file = new File(['example'], 'scores.xlsx')
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file] })
  await input.trigger('change')
  expect(importAcademicScores).not.toHaveBeenCalled()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(wrapper.get('tbody').text()).toContain('未提供学业成绩')
  expect(wrapper.findAll('tbody tr')[0].findAll('td')[4].text()).toBe('0')
  expect(wrapper.emitted('imported')).toBeUndefined()
  const confirm = wrapper.findAll('button').find(button => button.text() === '确认导入')
  await confirm.trigger('click')
  await flushPromises()

  expect(importAcademicScores).toHaveBeenLastCalledWith(file, 'preview-token')
  expect(wrapper.emitted('imported')).toHaveLength(1)
  expect(wrapper.text()).toContain('已导入 1 条，跳过 1 条')
  wrapper.unmount()
})

test('opens and reopens the upload panel from the grade management page', async () => {
  const wrapper = mount(ScoreManagement, { global: { stubs: { FontAwesomeIcon: true } } })
  await flushPromises()
  expect(wrapper.find('.page-title button').exists()).toBe(false)
  const entry = wrapper.get('.academic-import-module .card-body > button')
  expect(entry.attributes('aria-expanded')).toBe('false')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)

  await entry.trigger('click')
  expect(entry.attributes('aria-expanded')).toBe('true')
  expect(wrapper.get('#academic-import-panel input[type="file"]').isVisible()).toBe(true)

  const close = wrapper.findAll('#academic-import-panel button').find(button => button.text() === '关闭')
  await close.trigger('click')
  expect(entry.attributes('aria-expanded')).toBe('false')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)

  await entry.trigger('click')
  expect(wrapper.get('#academic-import-panel input[type="file"]').isVisible()).toBe(true)
  wrapper.unmount()
})
