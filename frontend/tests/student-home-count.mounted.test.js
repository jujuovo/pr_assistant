// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, test, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  auth: { userName: '演示同学', user: { studentId: 'S1' } },
  api: {
    getStudentMaterialSummary: vi.fn()
  }
}))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/services/materialApi.js', () => ({ default: mocks.api }))

import Home from '../src/pages/student/home/Home.vue'

const stubs = {
  WelcomeHeader: true,
  ApplicationPeriodPanel: true,
  WorkbenchAction: {
    props: ['title'],
    template: '<div><h2>{{ title }}</h2><slot name="description"/><slot name="action"/></div>'
  }
}

beforeEach(() => {
  vi.resetAllMocks()
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
  expect(wrapper.text()).toContain('已提交 2 份材料')
  expect(wrapper.text()).toContain('材料审核进度')
  expect(wrapper.text()).not.toContain('非竞赛材料审核进度')
  expect(wrapper.text()).not.toContain('竞赛材料（新链路）')
})

test('主页只采用统一材料摘要，不再混入旧 Application', async () => {
  mocks.api.getStudentMaterialSummary.mockResolvedValue({
    approved_count: 1,
    pending_count: 0,
    needs_correction_count: 0,
    rejected_count: 0,
    submitted_count: 1
  })
  const wrapper = mount(Home, { global: { stubs } })
  await flushPromises()

  expect(approvedCount(wrapper)).toContain('1')
  expect(wrapper.text()).toContain('已提交 1 份材料')
})

test('主页保留待修改提示并跳转我的材料', async () => {
  mocks.api.getStudentMaterialSummary.mockResolvedValue({
    approved_count: 0,
    pending_count: 0,
    needs_correction_count: 1,
    rejected_count: 1,
    submitted_count: 2
  })
  const wrapper = mount(Home, { global: { stubs } })
  await flushPromises()

  expect(wrapper.text()).toContain('有材料需要你修改')
  expect(wrapper.text()).toContain('2 份待修改')
  await wrapper.get('.workbench-primary').trigger('click')
  expect(wrapper.emitted('navigate')).toEqual([['application-record']])
})
