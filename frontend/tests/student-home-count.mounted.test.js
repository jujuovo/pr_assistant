// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, test, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  auth: { userName: '演示同学', user: { studentId: 'S1' } },
  store: { loading: false, error: '', applications: [], fetchApplications: vi.fn() },
  api: {
    getCompetitionWorkbenchSummary: vi.fn(),
    getStudentMaterialSummary: vi.fn()
  }
}))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/stores/applications.js', () => ({ useApplicationsStore: () => mocks.store }))
vi.mock('@/services/materialApi.js', () => ({ default: mocks.api }))

import Home from '../src/pages/student/home/Home.vue'

const stubs = {
  WelcomeHeader: true,
  ApplicationPeriodPanel: true,
  WorkbenchAction: { template: '<div><slot name="description"/><slot name="action"/></div>' }
}

beforeEach(() => {
  vi.resetAllMocks()
  mocks.store.loading = false
  mocks.store.error = ''
  mocks.store.applications = []
  mocks.api.getCompetitionWorkbenchSummary.mockResolvedValue({
    pending_count: 0,
    needs_correction_count: 0,
    completed_count: 0
  })
  mocks.api.getStudentMaterialSummary.mockResolvedValue({
    approved_count: 0,
    pending_count: 0,
    needs_correction_count: 0,
    rejected_count: 0,
    submitted_count: 0
  })
})

function approvedCount(wrapper) {
  return wrapper.get('.home-material-panel .status-approved .workbench-number').text()
}

test('主页已通过份数包含新材料记录', async () => {
  mocks.api.getStudentMaterialSummary.mockResolvedValue({
    approved_count: 2,
    pending_count: 0,
    needs_correction_count: 0,
    rejected_count: 0,
    submitted_count: 2
  })
  const wrapper = mount(Home, { global: { stubs } })
  await flushPromises()

  expect(approvedCount(wrapper)).toContain('2')
  expect(wrapper.text()).toContain('已提交 2 份加分材料')
})

test('主页统计同时保留旧兼容申请并通过材料数相加', async () => {
  mocks.store.applications = [
    { id: 7, studentId: 'S1', status: 'approved', rule: { sub_type: 'honor' } }
  ]
  mocks.api.getStudentMaterialSummary.mockResolvedValue({
    approved_count: 1,
    pending_count: 0,
    needs_correction_count: 0,
    rejected_count: 0,
    submitted_count: 1
  })
  const wrapper = mount(Home, { global: { stubs } })
  await flushPromises()

  expect(approvedCount(wrapper)).toContain('2')
  expect(wrapper.text()).toContain('已提交 2 份加分材料')
})
