import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('legacy rule service refuses competition but keeps generic compatibility endpoint',()=>{
  const source=readFileSync(new URL('../src/services/api.js',import.meta.url),'utf8')
  assert.match(source,/data\?\.sub_type === 'competition'/)
  assert.match(source,/竞赛规则必须使用规则包工作台/)
  assert.match(source,/apiRequest\('\/rules', 'POST', data\)/)
})

test('admin navigation routes competition rules and ranking to controlled workbenches',()=>{
  const navigation=readFileSync(new URL('../src/config/navigation.js',import.meta.url),'utf8')
  const layout=readFileSync(new URL('../src/pages/admin/AdminLayout.vue',import.meta.url),'utf8')
  const legacy=readFileSync(new URL('../src/pages/admin/rules/RuleManagement.vue',import.meta.url),'utf8')
  assert.match(navigation,/competition-rule-packages/)
  assert.match(layout,/rankings: RankingPublication/)
  assert.match(legacy,/rule\.sub_type !== 'competition'/)
})
