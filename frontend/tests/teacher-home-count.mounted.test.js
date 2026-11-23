// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, test, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  auth: { userName: '演示教师' },
  store: { pendingApplications: [] },
  api: {
    getCompetitionWorkbenchSummary: vi.fn(),
    getTeacherMaterialSummary: vi.fn()
  }
}))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/stores/applications.js', () => ({ useApplicationsStore: () => mocks.store }))
vi.mock('@/services/materialApi.js', () => ({ default: mocks.api }))

import RoleHome from '../src/components/common/RoleHome.vue'

const stubs = {
  WelcomeHeader: true,
  ApplicationPeriodPanel: true,
  WorkbenchAction: { template: '<div><slot name="description"/><slot name="action"/></div>' }
}

beforeEach(() => {
  vi.resetAllMocks()
  mocks.store.pendingApplications = []
  mocks.api.getCompetitionWorkbenchSummary.mockResolvedValue({ pending_count: 0 })
  mocks.api.getTeacherMaterialSummary.mockResolvedValue({ pending_count: 0 })
})

test('教师主页显示本学院新材料待审份数', async () => {
  mocks.api.getTeacherMaterialSummary.mockResolvedValue({ pending_count: 1 })
  const wrapper = mount(RoleHome, { props: { role: 'teacher' }, global: { stubs } })
  await flushPromises()

  expect(wrapper.text()).toContain('0 份竞赛材料待审核')
  expect(wrapper.text()).toContain('1 份非竞赛材料待审核')
})

test('教师主页不计入旧兼容申请', async () => {
  mocks.store.pendingApplications = [
    { id: 7, status: 'pending', rule: { sub_type: 'honor' } }
  ]
  mocks.api.getTeacherMaterialSummary.mockResolvedValue({ pending_count: 1 })
  const wrapper = mount(RoleHome, { props: { role: 'teacher' }, global: { stubs } })
  await flushPromises()

  expect(wrapper.text()).toContain('1 份非竞赛材料待审核')
})
