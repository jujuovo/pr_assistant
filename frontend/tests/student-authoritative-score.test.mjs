import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { scoreRows } from '../src/services/scorePresentation.js'

const source = readFileSync(new URL('../src/pages/student/statistics/Statistics.vue', import.meta.url), 'utf8')

test('statistics page is driven only by authoritative workflow snapshot', () => {
  assert.match(source, /workflow\.loadCurrentScore/)
  for (const field of ['snapshot_version', 'score.status', 'updated_at', 'rule_version_ids', 'candidateScore', 'includedScore', 'reason', 'updatedAt']) assert(source.includes(field))
  for (const forbidden of ['overrideScore', 'override_score', '人工调整', 'fetchStatistics', 'getFacultyScoreSetting', '专业排名']) assert(!source.includes(forbidden))
})

test('same-work and top-count exclusions remain server explanations', () => {
  const rows = scoreRows({ entries: [
    { id: 1, project_source: { type: 'material', id: '7', category: 'competition' }, candidate_score: '5', included_score: '5', included: true, rule_version_id: 8, updated_at: 'now' },
    { id: 2, project_source: { type: 'material', id: '8', category: 'competition' }, candidate_score: '4', included_score: '0', included: false, exclusion_reason: 'same_work_lower_score' },
    { id: 3, project_source: { type: 'material', id: '9', category: 'competition' }, candidate_score: '3', included_score: '0', included: false, exclusion_reason: 'max_count_exceeded' }
  ] })
  assert.deepEqual(rows.map(row => row.reason), [undefined, 'same_work_lower_score', 'max_count_exceeded'])
  assert.equal(rows[0].candidateScore, '5'); assert.equal(rows[1].included, false)
})

test('reconfirmation stays an explicit backend allowed action', () => {
  assert.match(source, /allowedActions\.includes\('confirm_submit'\)/)
  assert.match(source, /materialApi\.reconfirmSubmit/)
  assert.doesNotMatch(source, /automaticScore|estimatedScore/)
})
