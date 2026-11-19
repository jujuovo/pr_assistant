import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

test('student navigation exposes the four core workflow destinations', () => {
  const source = read('../src/components/student/StudentNavigation.vue')
  for (const title of ['提交材料', '我的材料', '加分统计', '我的排名']) assert(source.includes(title))
})

test('competition selection routes only to MaterialRecord workflow', () => {
  const layout = read('../src/pages/student/StudentLayout.vue')
  assert.match(layout, /category\.key === 'competition'/)
  assert.match(layout, /page: 'materials', category: 'competition'/)
  const categories = read('../src/pages/student/applications/ApplicationCategories.vue')
  assert.match(categories, /key: 'competition'/)
  assert.match(categories, /非竞赛兼容入口/)
})

test('my materials keeps competition and legacy application views explicitly separated', () => {
  const source = read('../src/pages/student/applications/StudentMaterialsHub.vue')
  assert.match(source, /mode === 'competition'/)
  assert.match(source, /<CompetitionWorkflow/)
  assert.match(source, /<ApplicationHistory/)
  assert.match(source, /不会创建竞赛 MaterialRecord/)
})
