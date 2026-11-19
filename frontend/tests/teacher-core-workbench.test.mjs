import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

test('teacher navigation unifies pending, history and read-only student summary', () => {
  const navigation = read('../src/config/navigation.js')
  const layout = read('../src/pages/teacher/TeacherLayout.vue')
  for (const key of ['pending-review', 'review-history', 'student-summary']) assert(navigation.includes(key))
  assert.match(layout, /'student-summary': TeacherStudentSummary/)
})

test('teacher summary renders authority facts and scores without mutation controls', () => {
  const source = read('../src/pages/teacher/students/TeacherStudentSummary.vue')
  assert.match(source, /getTeacherCompetitionSummary/)
  for (const field of ['key_facts', 'candidate_score', 'effective_score', 'exclusion_reason']) assert(source.includes(field))
  for (const forbidden of ['@click="edit', 'override_score', 'rule_id', 'final_score']) assert(!source.includes(forbidden))
})

test('shared review modal emits only comment and idempotency, never score override', () => {
  const source = read('../src/components/common/ApplicationDetailModal.vue')
  const method = source.slice(source.indexOf('const approveApplication'), source.indexOf('const rejectApplication'))
  assert.match(method, /approveComment/); assert.match(method, /idempotencyKey/)
  assert.doesNotMatch(method, /override/)
  assert.doesNotMatch(source, /人工改写规则分/)
})
