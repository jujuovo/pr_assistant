// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import MaterialReviewComparison from '../src/components/teacher/MaterialReviewComparison.vue'

test('highlights authoritative differences and distinguishes missing evidence', () => {
  const view = mount(MaterialReviewComparison, {
    props: {
      declared: { award: '一等奖', award_date: '2027-05-01' },
      differences: [{ field: 'award', declared: '一等奖', recognized: '二等奖' }]
    }
  })
  expect(view.findAll('.comparison-difference')).toHaveLength(1)
  expect(view.get('.comparison-difference').text()).toContain('二等奖')
  expect(view.text()).toContain('需人工核对')
  view.unmount()
})

test('compares only supported fields when no server comparison is supplied', () => {
  const view = mount(MaterialReviewComparison, {
    props: {
      declared: { project_name: '项目一', award: 'first', award_date: '2027-05-01' },
      recognized: { project_name: '项目二', award: '一等奖', award_date: '2027-05-01' }
    }
  })
  expect(view.findAll('.comparison-difference')).toHaveLength(1)
  expect(view.get('.comparison-difference').text()).toContain('项目二')
  expect(view.findAll('tbody tr').at(-1).text()).toContain('一致')
  view.unmount()
})
