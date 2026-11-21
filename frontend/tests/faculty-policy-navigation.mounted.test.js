// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import FacultyPolicyDrafts from '../src/pages/admin/rules/FacultyPolicyDrafts.vue'

vi.mock('@/services/requestJson.js', () => ({
  requestJson: vi.fn().mockResolvedValue({ items: [] })
}))

it('returns directly from a blank draft and prompts inline after an edit', async () => {
  const wrapper = mount(FacultyPolicyDrafts)
  await flushPromises()
  const click = label => wrapper.findAll('button').find(button => button.text() === label).trigger('click')
  await click('新建总规则')
  await click('返回版本列表')
  expect(wrapper.find('form').exists()).toBe(false)
  await click('新建总规则')
  await wrapper.get('input[maxlength]').setValue('2028 测试规则')
  await click('返回版本列表')
  expect(wrapper.get('[role="alertdialog"]').text()).toContain('尚未保存')
  await click('继续编辑')
  expect(wrapper.get('input[maxlength]').element.value).toBe('2028 测试规则')
  await click('返回版本列表')
  await click('放弃修改')
  expect(wrapper.find('form').exists()).toBe(false)
})
