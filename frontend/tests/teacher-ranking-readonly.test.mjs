import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/teacher/rankings/TeacherRanking.vue', import.meta.url), 'utf8')

test('teacher ranking shows complete read-only rows and score basis', () => {
  const shared = readFileSync(new URL('../src/pages/common/statistics/RankingBatch.vue', import.meta.url), 'utf8')
  assert.match(source, /title="专业排名"\s+show-basis\s+embedded\s+prefer-latest/)
  assert.match(shared, /v-for="row in ranking.entries"/)
  assert.match(shared, /row.score_basis/)
  assert.match(shared, /allowed_actions.includes\('export'\)/)
})

test('teacher ranking has no ranking mutation controls', () => {
  for (const forbidden of ['generateRanking(', 'rankingCommand(', "'freeze'", "'publish'", "'withdraw'", '@click="edit']) assert(!source.includes(forbidden))
})
