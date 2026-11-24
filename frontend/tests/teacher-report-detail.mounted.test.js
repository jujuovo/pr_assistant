// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import { read, utils, write } from 'xlsx'
import StatisticsReport from '../src/pages/common/statistics/StatisticsReport.vue'

const { writeFile } = vi.hoisted(() => ({ writeFile: vi.fn() }))
vi.mock('xlsx', async (importOriginal) => ({ ...await importOriginal(), writeFile }))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => ({ user: { facultyId: 1 } }) }))
vi.mock('@/services/api.js', () => ({ default: {
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
    score: '87.0000', cet4: 550, cet6: 510,
    projects: [
      { category: 'competition', name: '竞赛项目', score: '8.0000' },
      { category: 'innovation_training', name: '创新项目', score: '0', exclusion_reason: 'max_count_exceeded' },
      { category: 'research_paper', name: '论文项目', score: '1.0000' },
      { category: 'volunteer', name: '志愿项目', score: '0.5000' },
      { category: 'arts_sports', name: '文体项目', score: '0.5000' }
    ], academic_raw_total: '10.0000', academic_total: '8.0000',
    comprehensive_raw_total: '3.0000', comprehensive_total: '2.0000'
  }, {
    student_id: 'S2', name: '单项目学生',
    projects: [{ category: 'competition', name: '独立项目', score: '2.0000' }]
  }, {
    student_id: 'S3', name: '无快照学生', snapshot_status: 'no_authoritative_snapshot'
  }] })
} }))

test.each([
  ['管理员独立报表', false],
  ['教师嵌入报表', true]
])('%s 展示并导出相同的正式报表列和项目明细', async (_mode, embedded) => {
  writeFile.mockClear()
  const view = mount(StatisticsReport, { props: { embedded } })
  await flushPromises()
  await view.findAll('select')[1].setValue('2')
  await flushPromises()
  await view.findAll('select')[2].setValue('3')
  await flushPromises()
  expect(view.text()).not.toContain('查看完整明细')
  const table = view.get('.official-report-table')
  expect(table.findAll('tbody tr')).toHaveLength(7)
  expect(table.text()).toContain('项目名称')
  await view.findAll('button').find(button => button.text() === '导出统计报表').trigger('click')
  const [workbook, filename] = writeFile.mock.calls[0]
  expect(filename).toMatch(/\.xlsx$/)
  const exported = read(write(workbook, { bookType: 'xlsx', type: 'array' }), { type: 'array' })
  const sheet = exported.Sheets[exported.SheetNames[0]]
  const [headers, firstExcel, projectExcel, ...remaining] = utils.sheet_to_json(sheet, {
    header: 1, defval: null
  })
  const columnCount = headers.indexOf('项目类型')
  expect(sheet['!merges']).toEqual(Array.from({ length: columnCount }, (_, column) => ({
    s: { r: 1, c: column }, e: { r: 5, c: column }
  })))
  expect(utils.encode_range(sheet['!merges'][headers.indexOf('姓名')])).toBe('F2:F6')
  expect(remaining.map(row => row[headers.indexOf('实际加分')])).toEqual([
    '1.0000', '0.5000', '0.5000', '2.0000', null
  ])
  expect(remaining.at(-2)[headers.indexOf('姓名')]).toBe('单项目学生')
  expect(remaining.at(-1)[headers.indexOf('姓名')]).toBe('无快照学生')
  const nextExcel = remaining.at(-1)
  expect(table.findAll('thead th').map(cell => cell.text())).toEqual(headers)
  const rows = table.findAll('tbody tr').map(row => row.findAll('td').map(cell => cell.text()))
  const [firstRow, projectRow] = rows
  const nextRow = rows.at(-1)
  for (const [label, expected] of [
    ['学号', 'S1'], ['四级成绩', 550], ['六级成绩', 510], ['推免综合成绩', '87.0000'], ['报表名次', 1],
    ['学术专长原始总分', '10.0000'], ['学术专长实际计入分', '8.0000'],
    ['综合表现原始总分', '3.0000'], ['综合表现实际计入分', '2.0000']
  ]) {
    const index = headers.indexOf(label)
    expect(firstRow[index]).toBe(String(expected))
    expect(firstExcel[index]).toBe(expected)
  }
  expect(projectRow.slice(0, -4).every(value => value === '')).toBe(true)
  expect(projectRow.slice(-4)).toEqual(['创新创业', '创新项目', '0', '超出计入项目数上限'])
  expect(projectExcel.slice(-4)).toEqual(projectRow.slice(-4))
  expect(nextRow).toContain('暂无正式成绩快照')
  const scoreIndex = headers.indexOf('推免综合成绩')
  expect(nextRow[scoreIndex]).toBe('')
  expect(nextExcel[scoreIndex]).toBeNull()
  view.unmount()
})
