// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { expect, it } from 'vitest'
import RuleModal from '../src/components/admin/rules/RuleModal.vue'

it('saves cumulative and per-item limits independently, including zero', async () => {
  const wrapper = mount(RuleModal, {
    props: { visible: true },
    global: { plugins: [createPinia()], stubs: { FontAwesomeIcon: true } }
  })
  const cap = wrapper.get('input[step="0.0001"]')
  await cap.setValue('0')
  await wrapper.get('form').trigger('submit.prevent')
  const [payload] = wrapper.emitted('save')[0]
  expect(payload.total_score_cap).toBe(0)
  expect(payload.max_score).toBeNull()
})
