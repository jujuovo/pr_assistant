import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('admin score recalculation is a preview-confirm-execute workflow', () => {
  const source = readFileSync(new URL('../src/pages/admin/scores/ScoreManagement.vue', import.meta.url), 'utf8')
  assert.match(source, /workflowApi\.previewScoreRecalculation\(payload\)/)
  assert.match(source, /workflowApi\.executeScoreRecalculation\(/)
  assert.match(source, /preview_digest: preview\.preview_digest/)
  assert.match(source, /failed_objects/)
  assert.doesNotMatch(source, /recalculateComprehensiveScores/)
  assert.doesNotMatch(source, /for\s*\([^)]*\)[\s\S]{0,200}executeScoreRecalculation/)
})

test('workflow adapter uses exactly one bulk endpoint per phase', () => {
  const source = readFileSync(new URL('../src/services/workflowApi.js', import.meta.url), 'utf8')
  assert.match(source, /previewScoreRecalculation:[^\n]+\/scores\/recalculation-previews/)
  assert.match(source, /executeScoreRecalculation:[^\n]+\/scores\/recalculation-executions/)
  assert.doesNotMatch(source, /recalculateScores:/)
})
