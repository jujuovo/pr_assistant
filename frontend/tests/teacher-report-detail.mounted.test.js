// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import StatisticsReport from '../src/pages/common/statistics/StatisticsReport.vue'

const { writeFile } = vi.hoisted(() => ({ writeFile: vi.fn() }))
vi.mock('xlsx', async (importOriginal) => ({ ...await importOriginal(), writeFile }))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => ({ user: { facultyId: 1 } }) }))
vi.mock('@/stores/toast.js', () => ({ useToastStore: () => ({ error: vi.fn() }) }))
vi.mock('@/services/api.js', () => ({ default: {
  getSystemSettings: async () => ({ settings: { academicYear: '2028' } }),
  getFacultiesAdmin: async () => ({ faculties: [{ id: 1, name: '信息学院' }] }),
  getDepartmentsAdmin: async () => ({ departments: [{ id: 2, name: '计算机系' }] }),
  getMajorsAdmin: async () => ({ majors: [{ id: 3, name: '软件工程' }] })
} }))
vi.mock('@/stores/applications.js', () => ({ useApplicationsStore: () => ({
  applications: [],
  fetchStudentsRanking: () => { throw Error('Teacher report must not call the legacy endpoint') }
}) }))
vi.mock('@/services/workflowApi.js', () => ({ default: {
  getCurrentCycle: async () => ({ cycle_code: 2028 }),
  getTeacherScoreReport: async () => ({ year: 2028, students: [{
    student_id: 'S1', name: '测试学生', major: '软件工程', report_rank: 1, ranked_count: 12,
    score: '87.0000', academic_total: '8.0000', comprehensive_total: '2.0000',
    items: [
      { title: '竞赛项目', score_group: 'academic', included_score: '8.0000', included: true },
      { title: '志愿项目', score_group: 'comprehensive', included_score: '2.0000', included: true }
    ]
  }] })
} }))

test('teacher sees and exports the same official report columns and rows', async () => {
  const view = mount(StatisticsReport, { props: { embedded: true } })
  await flushPromises()
  await view.findAll('select')[1].setValue('2')
  await flushPromises()
  await view.findAll('select')[2].setValue('3')
  await flushPromises()
  expect(view.text()).not.toContain('查看完整明细')
  const table = view.get('.official-report-table')
  expect(table.findAll('tbody tr')).toHaveLength(2)
  for (const text of ['竞赛项目', '志愿项目', '8.0000', '2.0000', '排名人数', '12']) {
    expect(table.text()).toContain(text)
  }
  await view.findAll('button').find(button => button.text() === '导出统计报表').trigger('click')
  const [workbook, filename] = writeFile.mock.calls[0]
  expect(filename).toMatch(/\.xlsx$/)
  const cells = Object.values(workbook.Sheets[workbook.SheetNames[0]]).map(cell => cell?.v)
  const headers = table.findAll('thead th').map(cell => cell.text())
  expect(cells.slice(0, headers.length)).toEqual(headers)
  expect(cells).toEqual(expect.arrayContaining(['竞赛项目', '志愿项目', '8.0000', '2.0000', 12]))
  view.unmount()
})
