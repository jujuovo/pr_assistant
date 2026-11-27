// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import Sidebar from '../src/components/common/Sidebar.vue'
import ReviewTimeline from '../src/components/common/ReviewTimeline.vue'
import { useAuthStore } from '../src/stores/auth.js'

describe('reviewer navigation and evidence', () => {
  for (const role of ['reviewer_level1', 'reviewer_level2']) {
    it(`${role} only exposes review navigation and emits a working review action`, async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      useAuthStore().user = { name: '审核测试员', username: 'reviewer', role }
      const wrapper = mount(Sidebar, { global: { plugins: [pinia], stubs: { FontAwesomeIcon: true } } })
      expect(wrapper.text()).toContain('审核测试员')
      expect(wrapper.text()).toContain('审核记录')
      expect(wrapper.text()).not.toMatch(/统计报表|学生汇总|个人信息|用户管理/)
      const button = wrapper.findAll('button').find(b => b.text() === '待审核申请')
      await button.trigger('click')
      expect(wrapper.emitted('page-change').at(-1)).toEqual(['pending-review'])
    })
  }
  it('shows the named reviewers, all stages and return opinion to students and staff', async () => {
    const wrapper = mount(ReviewTimeline, { props: { events: [1, 2, 3].map(stage => ({
      review_stage: stage, actor: { name: `审核人${stage}`, role: stage === 3 ? 'teacher' : `reviewer_level${stage}` },
      decision: stage === 3 ? 'return' : 'approve', comment: stage === 3 ? '请补充证明' : '', created_at: '2026-11-27T01:00:00Z'
    })) } })
    await wrapper.find('summary').trigger('click')
    expect(wrapper.findAll('li')).toHaveLength(3)
    expect(wrapper.text()).toContain('教师终审')
    expect(wrapper.text()).toContain('审核人2')
    expect(wrapper.text()).toContain('请补充证明')
  })
})
