// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('@/services/api.js', () => ({
  default: {
    getFacultiesAdmin: async () => ({ faculties: [] }),
    getDepartmentsAdmin: async () => ({ departments: [] }),
    getMajorsAdmin: async () => ({ majors: [] })
  }
}))
vi.mock('@/stores/auth.js', () => ({
  useAuthStore: () => ({ isAuthenticated: true, user: { id: 1, role: 'admin' } })
}))
vi.mock('@/stores/toast.js', () => ({
  useToastStore: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() })
}))

import UserManagement from '../src/pages/admin/users/UserManagement.vue'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

test('shows import progress and replaces result actions with one working confirm button', async () => {
  vi.useFakeTimers()
  let finishImport
  const importResponse = new Promise((resolve) => {
    finishImport = resolve
  })
  vi.stubGlobal(
    'fetch',
    vi.fn((url) => {
      if (String(url).includes('/api/admin/import-users')) return importResponse
      return Promise.resolve({
        ok: true,
        json: async () => ({ users: [], total: 0, pages: 0 })
      })
    })
  )

  const wrapper = mount(UserManagement, {
    global: { stubs: { FontAwesomeIcon: true } }
  })
  await flushPromises()

  const open = wrapper.findAll('button').find((button) => button.text().includes('导入用户'))
  await open.trigger('click')
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', {
    configurable: true,
    value: [new File(['users'], 'users.xlsx')]
  })
  await input.trigger('change')

  const submit = wrapper.findAll('button').find((button) => button.text() === '确认导入')
  await submit.trigger('click')
  await wrapper.vm.$nextTick()
  expect(wrapper.get('.import-progress').text()).toContain('正在导入用户')
  expect(wrapper.find('.form-actions').exists()).toBe(false)

  vi.advanceTimersByTime(65_000)
  await wrapper.vm.$nextTick()
  expect(wrapper.get('.import-progress-time').text()).toContain('1分05秒')

  finishImport({
    ok: true,
    json: async () => ({ success_count: 1000, error_count: 0, errors: [] })
  })
  await flushPromises()

  expect(wrapper.text()).toContain('成功导入')
  expect(wrapper.text()).toContain('1000人')
  const actions = wrapper.get('.import-result-actions')
  expect(actions.findAll('button')).toHaveLength(1)
  expect(actions.get('button').text()).toBe('确定')
  await actions.get('button').trigger('click')
  expect(wrapper.find('.modal-overlay').exists()).toBe(false)
  wrapper.unmount()
})
