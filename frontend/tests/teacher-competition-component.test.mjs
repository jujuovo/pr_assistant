import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/teacher/reviews/TeacherCompetitionReview.vue', import.meta.url), 'utf8')

const evidence = readFileSync(new URL('../src/pages/teacher/reviews/CompetitionReviewEvidence.vue', import.meta.url), 'utf8')

test('competition reviewer exposes evidence sections and only approve/return actions', () => {
  assert(evidence.includes('ReviewEvidenceLayout'))
  for (const heading of ['OCR 原文（仅辅助）','固定规则依据','后端候选分']) assert(evidence.includes(heading))
  assert(evidence.includes("review('approve')")); assert(evidence.includes("review('return')"))
  for (const forbidden of ['override_score','override_reason','rule_id','final_score','type="number"']) assert(!(source + evidence).includes(forbidden))
})

test('teacher history cards support material navigation without edit or merge controls', () => {
  assert(source.includes('reviewed_items')); assert(source.includes('open(row.id)'))
  assert(!source.includes('编辑')); assert(!source.includes('合并')); assert(!source.includes('改分'))
})
