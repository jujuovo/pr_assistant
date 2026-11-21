// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import Categories from '../src/pages/student/applications/ApplicationCategories.vue'
import Fields from '../src/components/common/PolicyMaterialFields.vue'
import { submissionQuery } from '../src/services/materialWorkflowRoutes.js'
test('提交材料提供两个独立入口并保留竞赛和志愿', async () => {
  const page = mount(Categories, { global: { stubs: { FontAwesomeIcon: true } } })
  for (const [label, key] of [
    ['创业创新', 'innovation_training'],
    ['学术论文', 'research_paper'],
    ['学业竞赛', 'competition'],
    ['志愿服务', 'volunteer']
  ]) {
    await page
      .findAll('button')
      .find((b) => b.text().includes(label))
      .trigger('click')
    expect(submissionQuery(page.emitted('select').at(-1)[0].key)).toEqual({
      page: 'materials',
      category: key
    })
  }
  expect(page.text()).not.toContain('学术创新')
})
test('授权事实提交为布尔值', async () => {
  const w = mount(Fields, { props: { category: 'invention_patent', modelValue: {} } })
  await w.get('select').setValue('true')
  expect(w.emitted('update:modelValue').at(-1)[0].authorized_national_invention).toBe(true)
})
