import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/student/rankings/StudentRanking.vue', import.meta.url), 'utf8')

test('student ranking uses the shared selection and renders only its personal result', () => {
  assert.match(source, /<RankingBatch title="我的排名">/)
  for (const field of ['ranking.entries[0].rank', 'ranking.total_count', 'ranking.entries[0].comprehensive_score', 'ranking.status']) {
    assert(source.includes(field))
  }
})

test('student page has no complete-list loop or staff controls', () => {
  for (const forbidden of ['v-for="row in ranking.entries"', 'score_basis', 'generateRanking', 'rankingCommand', 'exportRanking']) assert(!source.includes(forbidden))
})
