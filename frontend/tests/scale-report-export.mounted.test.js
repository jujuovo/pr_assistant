// @vitest-environment happy-dom
// Opt in after tools/exercise_thousand_students.py has produced actual route data.
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as XLSX from 'xlsx'
import StatisticsReport from '../src/pages/common/statistics/StatisticsReport.vue'

const state = vi.hoisted(() => ({ report: null, environment: null, writeFile: vi.fn() }))
vi.mock('xlsx', async (original) => ({ ...await original(), writeFile: state.writeFile }))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => ({ user: { facultyId: state.environment.faculty_id } }) }))
vi.mock('@/services/api.js', () => ({ default: {
  getFacultiesAdmin: async () => ({ faculties: [{ id: state.environment.faculty_id, name: '信息学院' }] }),
  getDepartmentsAdmin: async () => ({ departments: [{ id: state.environment.department_id, name: '规模测试系（合成数据）' }] }),
  getMajorsAdmin: async () => ({ majors: state.environment.majors })
} }))
vi.mock('@/stores/applications.js', () => ({ useApplicationsStore: () => ({ applications: [] }) }))
vi.mock('@/services/workflowApi.js', () => ({ default: {
  getCurrentCycle: async () => ({ cycle_code: 2028 }),
  getTeacherScoreReport: async () => state.report
} }))

const fixture = process.env.SCALE_REPORT_FIXTURE
const run = fixture ? test : test.skip
run.each(['teacher', 'admin'])('%s renders and exports every student and project from real scale report fixtures', async (role) => {
  const folder = resolve(fixture)
  state.environment = JSON.parse(readFileSync(resolve(folder, 'environment.json'), 'utf8'))
  const oracle = JSON.parse(readFileSync(resolve(folder, 'students.json'), 'utf8'))
  expect(oracle.length).toBeGreaterThanOrEqual(1000)
  let allStudents = new Set()
  for (const major of state.environment.majors) {
    state.report = JSON.parse(readFileSync(resolve(folder, `report-${role}-${major.id}.json`), 'utf8'))
    state.writeFile.mockClear()
    const wrapper = mount(StatisticsReport, { props: { embedded: role === 'teacher' } })
    try {
      await flushPromises()
      await wrapper.findAll('select')[1].setValue(String(state.environment.department_id))
      await flushPromises()
      await wrapper.findAll('select')[2].setValue(String(major.id))
      await flushPromises()
      const students = state.report.students
      if (!students.length) {
        expect(wrapper.text()).not.toContain('scale28_0001')
        expect(wrapper.findAll('button').find(button => button.text() === '导出统计报表').attributes('disabled')).toBeDefined()
        continue
      }
      const table = wrapper.get('.official-report-table')
      const headers = table.findAll('thead th').map(cell => cell.text())
      const domRows = table.findAll('tbody tr').map(row => row.findAll('td').map(cell => cell.text()))
      expect(domRows.length).toBe(students.reduce((total, row) => total + Math.max(row.projects.length, 1), 0))
      await wrapper.findAll('button').find(button => button.text() === '导出统计报表').trigger('click')
      expect(state.writeFile).toHaveBeenCalledTimes(1)
      const workbook = state.writeFile.mock.calls[0][0]
      const binary = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' })
      writeFileSync(resolve(folder, `export-${role}-major-${major.id}.xlsx`), binary)
      const reopened = XLSX.read(binary, { type: 'buffer' })
      const [excelHeaders, ...rows] = XLSX.utils.sheet_to_json(reopened.Sheets[reopened.SheetNames[0]], { header: 1, defval: null })
      expect(excelHeaders).toEqual(headers)
      expect(rows.map(row => row.map(value => value == null ? '' : String(value)))).toEqual(domRows)
      const sidColumn = headers.indexOf('学号')
      const scoreColumn = headers.indexOf('推免综合成绩')
      expect(sidColumn).toBeGreaterThanOrEqual(0)
      expect(scoreColumn).toBeGreaterThanOrEqual(0)
      const studentRows = rows.filter(row => row[sidColumn])
      expect(studentRows).toHaveLength(students.length)
      const byId = new Map(oracle.map(row => [row.student_id, row]))
      for (const row of studentRows) {
        const sid = row[sidColumn]
        expect(allStudents.has(sid)).toBe(false)
        allStudents.add(sid)
        expect(Number(row[scoreColumn])).toBe(Number(byId.get(sid).expected.score))
      }
    } finally {
      wrapper.unmount()
    }
  }
  expect(allStudents.size).toBe(1000)
}, 120000)
