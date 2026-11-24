import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { submissionQuery } from '../src/services/materialWorkflowRoutes.js'
const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('student navigation exposes the four core workflow destinations', () => {
  const source = read('../src/components/student/StudentNavigation.vue')
  for (const title of ['提交材料', '我的材料', '加分统计', '我的排名'])
    assert(source.includes(title))
})

test('competition and volunteer selections use the shared material workflow', () => {
  assert.deepEqual(submissionQuery('competition'), { page: 'materials', category: 'competition' })
  assert.deepEqual(submissionQuery('volunteer-service'), {
    page: 'materials',
    category: 'volunteer'
  })
  const layout = read('../src/pages/student/StudentLayout.vue')
  assert.match(layout, /submissionQuery\(category.key\)/)
})

test('other scored categories route to their MaterialRecord workflows', () => {
  assert.deepEqual(submissionQuery('social-practice'), { page: 'materials', category: 'social_practice' })
  assert.deepEqual(submissionQuery('academic-innovation'), { page: 'application-categories' })
  assert.deepEqual(submissionQuery('academic-paper'), { page: 'materials', category: 'research_paper' })
  assert.deepEqual(submissionQuery('innovation-training'), { page: 'materials', category: 'innovation_training' })
  assert.deepEqual(submissionQuery('social-work'), { page: 'materials', category: 'student_work' })
  assert.deepEqual(submissionQuery('arts-sports'), { page: 'materials', category: 'arts_sports' })
  assert.deepEqual(submissionQuery('unknown-category'), { page: 'application-categories' })
  const categories = read('../src/pages/student/applications/ApplicationCategories.vue')
  assert.match(categories, /key: 'competition'/)
})

test('my materials renders history without a submission form or autofill wizard', () => {
  const source = read('../src/pages/student/applications/StudentMaterialsHub.vue')
  assert.doesNotMatch(source, /ApplicationHistory|历史兼容记录/)
  assert.match(source, /workflow_state/)
  assert.match(source, /OCR队列中/)
  assert.doesNotMatch(source, /<CompetitionWorkflow|<OcrUploadPreview|type="file"/)
})
