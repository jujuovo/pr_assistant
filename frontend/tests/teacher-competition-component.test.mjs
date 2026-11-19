import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/teacher/reviews/TeacherCompetitionReview.vue', import.meta.url), 'utf8')

test('competition reviewer exposes evidence sections and only approve/return actions', () => {
  for (const heading of ['证明原件','OCR 原文（仅辅助）','学生确认事实','固定规则依据','后端候选分']) assert(source.includes(heading))
  assert(source.includes("review('approve')")); assert(source.includes("review('return')"))
  for (const forbidden of ['override_score','override_reason','rule_id','final_score','type="number"']) assert(!source.includes(forbidden))
})

test('teacher summary supports material navigation without edit or merge controls', () => {
  assert(source.includes('getTeacherCompetitionSummary')); assert(source.includes('open(item.record_id)'))
  assert(!source.includes('编辑')); assert(!source.includes('合并')); assert(!source.includes('改分'))
})
