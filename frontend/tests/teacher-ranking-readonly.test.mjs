import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/teacher/rankings/TeacherRanking.vue', import.meta.url), 'utf8')

test('teacher ranking shows complete read-only rows and score basis', () => {
  for (const value of ['ranking.status', 'ranking.scope', 'ranking.version', 'ranking.entries', 'row.score_basis']) assert(source.includes(value))
  assert.match(source, /workflowApi\.getRanking/)
})

test('teacher ranking has no ranking mutation controls', () => {
  for (const forbidden of ['generateRanking(', 'rankingCommand(', "'freeze'", "'publish'", "'withdraw'", '@click="edit']) assert(!source.includes(forbidden))
})
