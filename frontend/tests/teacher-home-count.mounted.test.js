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

test.each([[1, 6, 7], [0, 1, 1], [1, 0, 1], [0, 0, 0]])(
  '教师主页合并两类待审数量 %i 和 %i',
  async (competition, material, total) => {
    mocks.api.getCompetitionWorkbenchSummary.mockResolvedValue({ pending_count: competition })
    mocks.api.getTeacherMaterialSummary.mockResolvedValue({ pending_count: material })
    const wrapper = mount(RoleHome, { props: { role: 'teacher' }, global: { stubs } })
    await flushPromises()

    expect(wrapper.get('.action-count').text()).toBe(`${total} 份竞赛材料待审核。`)
    expect(wrapper.text()).not.toContain('非竞赛材料待审核')
    wrapper.unmount()
  }
)

test('教师主页不计入旧兼容申请', async () => {
  mocks.store.pendingApplications = [
    { id: 7, status: 'pending', rule: { sub_type: 'honor' } }
  ]
  mocks.api.getTeacherMaterialSummary.mockResolvedValue({ pending_count: 1 })
  const wrapper = mount(RoleHome, { props: { role: 'teacher' }, global: { stubs } })
  await flushPromises()

  expect(wrapper.text()).toContain('1 份竞赛材料待审核。')
})
