import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import workflowApi from '../src/services/workflowApi.js'

test('admin score recalculation is a preview-confirm-execute workflow', () => {
  const source = readFileSync(new URL('../src/pages/admin/scores/ScoreManagement.vue', import.meta.url), 'utf8')
  assert.match(source, /workflowApi\.previewScoreRecalculation\(payload\)/)
  assert.match(source, /workflowApi\.executeScoreRecalculation\(/)
  assert.match(source, /preview_digest: preview\.preview_digest/)
  assert.match(source, /failed_objects/)
  assert.doesNotMatch(source, /recalculateComprehensiveScores/)
  assert.doesNotMatch(source, /for\s*\([^)]*\)[\s\S]{0,200}executeScoreRecalculation/)
})

test('workflow adapter uses exactly one bulk endpoint per phase', async () => {
  const original=globalThis.fetch,calls=[]
  globalThis.fetch=async(url,options)=>{calls.push({url,...options});return new Response('{}',{headers:{'Content-Type':'application/json'}})}
  try{
    const preview={year:2028,faculty_id:1},execution={...preview,preview_digest:'checked',idempotency_key:'one-command'}
    await workflowApi.previewScoreRecalculation(preview)
    await workflowApi.executeScoreRecalculation(execution)
    assert.deepEqual(calls.map(c=>[c.url,c.method]),[['/api/workflow/scores/recalculation-previews','POST'],['/api/workflow/scores/recalculation-executions','POST']])
    assert.deepEqual(JSON.parse(calls[0].body),preview)
    assert.deepEqual(JSON.parse(calls[1].body),execution)
  }finally{globalThis.fetch=original}
})
