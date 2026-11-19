import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { isNonCompetitionCompatibilityApplication, nonCompetitionRules } from '../src/services/teacherApplicationBoundary.js'

test('legacy teacher review excludes competition applications and rules', () => {
  assert.equal(isNonCompetitionCompatibilityApplication({ rule: { sub_type: 'competition' } }), false)
  assert.equal(isNonCompetitionCompatibilityApplication({ rule: { sub_type: 'research' } }), true)
  assert.deepEqual(nonCompetitionRules([{ id: 1, sub_type: 'competition' }, { id: 2, sub_type: 'honor' }]).map(x => x.id), [2])
})

test('competition teacher page uses only material APIs and authority-free payload', () => {
  const source = readFileSync(new URL('../src/pages/teacher/reviews/TeacherCompetitionReview.vue', import.meta.url), 'utf8')
  assert.match(source, /materialApi\.reviewCompetition/)
  for (const forbidden of ['getRules', '/rules', 'rule_id', 'self_score', 'final_score', 'dynamic_coefficients', 'override_score', 'override_reason']) assert(!source.includes(forbidden))
})

test('general teacher pages explicitly apply noncompetition compatibility boundary', () => {
  for (const path of ['../src/pages/teacher/reviews/PendingReview.vue', '../src/pages/teacher/reviews/ReviewHistory.vue']) {
    const source = readFileSync(new URL(path, import.meta.url), 'utf8')
    assert.match(source, /isNonCompetitionCompatibilityApplication/)
    assert.match(source, /nonCompetitionRules/)
  }
})
