// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import PolicySectionEditor from '../src/components/admin/rules/PolicySectionEditor.vue'

it('synchronizes numeric fields and rejects invalid JSON without losing the edit', async () => {
  const wrapper = mount(PolicySectionEditor, {
    props: {
      title: '学科竞赛',
      fields: [{ key: 'competition_max_count', label: '最多计入项目数', integer: true }],
      modelValue: { competition_max_count: 3, catalog: [] },
      'onUpdate:modelValue': value => wrapper.setProps({ modelValue: value }),
      'onUpdate:dirty': value => wrapper.setProps({ dirty: value })
    }
  })
  await wrapper.get('input').setValue('2')
  expect(JSON.parse(wrapper.get('textarea').element.value)).toEqual({
    competition_max_count: 2, catalog: []
  })
  await wrapper.get('textarea').setValue('{"competition_max_count": 1.5}')
  await wrapper.get('button').trigger('click')
  expect(wrapper.get('[role="alert"]').text()).toContain('最多计入项目数')
  expect(wrapper.get('input').element.disabled).toBe(true)
  await wrapper.get('textarea').setValue('{"competition_max_count": 4}')
  await wrapper.get('button').trigger('click')
  expect(wrapper.get('input').element.value).toBe('4')
  expect(wrapper.get('input').element.disabled).toBe(false)
})
