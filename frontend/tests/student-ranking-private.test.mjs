import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/student/rankings/StudentRanking.vue', import.meta.url), 'utf8')

test('student ranking renders all lifecycle states and only personal fields', () => {
  for (const status of ['draft', 'stale', 'frozen', 'published']) assert(source.includes(status))
  for (const field of ['own?.rank', 'ranking.total_count', 'own?.comprehensive_score', 'ranking.scope', 'ranking.status', 'ranking.generated_at', 'ranking.published_at']) assert(source.includes(field))
  assert.match(source, /ranking\.value\?\.entries\?\.\[0\]/)
})

test('student page has no complete-list loop or staff controls', () => {
  for (const forbidden of ['v-for="row in ranking.entries"', 'score_basis', 'generateRanking', 'rankingCommand', 'exportRanking']) assert(!source.includes(forbidden))
})
