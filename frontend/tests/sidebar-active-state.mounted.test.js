// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  role: 'teacher',
  userName: '演示同学',
  userAvatar: ''
}))

vi.mock('@/stores/auth.js', () => ({
  useAuthStore: () => ({
    user: { role: state.role },
    userName: state.userName,
    userAvatar: state.userAvatar
  })
}))

import Sidebar from '../src/components/common/Sidebar.vue'
import StudentNavigation from '../src/components/student/StudentNavigation.vue'

const stubs = { 'font-awesome-icon': true }

// 只找真正的导航项；「展开导航 · 主页」这种移动端开关不算
function findHomeNavButton(wrapper) {
  return wrapper
    .findAll('button.student-direct-item')
    .find((button) => button.text().trim() === '主页')
}

beforeEach(() => {
  state.role = 'teacher'
  state.userAvatar = ''
})

describe('侧栏高亮：主页时只有导航项变蓝，头像块不跟着高亮', () => {
  it.each([
    ['教师/管理员侧栏', Sidebar],
    ['学生侧栏', StudentNavigation]
  ])('%s 在 activePage=home 时只高亮主页项', (_name, Component) => {
    const wrapper = mount(Component, {
      props: { activePage: 'home' },
      global: { stubs }
    })

    const identity = wrapper.get('.student-identity')
    expect(identity.classes()).not.toContain('selected')
    expect(identity.attributes('aria-current')).toBeUndefined()

    const homeButton = findHomeNavButton(wrapper)
    expect(homeButton).toBeTruthy()
    expect(homeButton.classes()).toContain('selected')
    expect(homeButton.attributes('aria-current')).toBe('page')
  })

  it.each([
    ['教师/管理员侧栏', Sidebar],
    ['学生侧栏', StudentNavigation]
  ])('%s 点头像仍然回到主页', async (_name, Component) => {
    const wrapper = mount(Component, {
      props: { activePage: 'profile' },
      global: { stubs }
    })

    await wrapper.get('.student-identity').trigger('click')
    expect(wrapper.emitted('page-change')?.at(-1)).toEqual(['home'])
  })

  it.each([
    ['教师/管理员侧栏', Sidebar],
    ['学生侧栏', StudentNavigation]
  ])('%s 在非主页页面时头像和主页都不高亮', (_name, Component) => {
    const wrapper = mount(Component, {
      props: { activePage: 'profile' },
      global: { stubs }
    })

    expect(wrapper.get('.student-identity').classes()).not.toContain('selected')
    expect(findHomeNavButton(wrapper).classes()).not.toContain('selected')
  })
})
