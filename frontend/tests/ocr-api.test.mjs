import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import ocrApi, { OCR_PROJECTS } from '../src/services/ocrApi.js'
import materialApi from '../src/services/materialApi.js'

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })
const id = '01234567-1234-1234-1234-1234567890ab'
function capture() {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, ...options })
    return new Response(JSON.stringify({ id, status: 'queued' }), { headers: { 'Content-Type': 'application/json' } })
  }
  return calls
}

test('all seven projects upload privately; mapping and explicit confirmation keep fields intact', async () => {
  const calls = capture()
  assert.equal(OCR_PROJECTS.length, 7)
  for (const project of OCR_PROJECTS) {
    await ocrApi.recognize(project, new File(['image'], 'certificate.png'))
    assert.equal(calls.at(-1).url, `/api/ocr/${project}/recognize`)
    assert.equal(calls.at(-1).body.get('file').name, 'certificate.png')
    assert.deepEqual(calls.at(-1).headers, {})
    assert.equal(calls.at(-1).credentials, 'include')
  }
  await ocrApi.getCategories()
  await ocrApi.getJob(id)
  await ocrApi.getMapping(id)
  assert.deepEqual(calls.slice(-3).map(c => c.url), ['/api/ocr/categories', `/api/ocr/jobs/${id}`, `/api/ocr/jobs/${id}/mapping`])
  const data = { material_record_id: 1, version: 2, data: { score: 0, full_score: 500, task_scores: [0,0,0,0,0] } }
  await ocrApi.confirmMaterial(id, data)
  assert.equal(calls.at(-1).url, `/api/ocr/jobs/${id}/confirm-material`)
  assert.equal(calls.at(-1).method, 'POST')
  assert.deepEqual(JSON.parse(calls.at(-1).body), data)
  const input = { version: 2, attachment_id: 3, project_key: 'csp' }
  await materialApi.recognize('certification', 1, input)
  assert.deepEqual(JSON.parse(calls.at(-1).body), input)
  assert.equal(calls.at(-1).url, '/api/materials/certification/records/1/recognize')
})

test('invalid project/task paths fail locally and duplicate confirmation is not retried', async () => {
  const calls = capture()
  assert.throws(() => ocrApi.getJob('../private'), TypeError)
  assert.throws(() => ocrApi.getMapping(1), TypeError)
  assert.throws(() => ocrApi.recognize('../csp', new Blob(['x'])), TypeError)
  assert.throws(() => ocrApi.recognize('csp', 'not a file'), TypeError)
  assert.equal(calls.length, 0)
  let count = 0
  globalThis.fetch = async () => { count++; return new Response(JSON.stringify({ error: '已关联材料' }), { status: 409 }) }
  await assert.rejects(ocrApi.confirmMaterial(id, { year: 2026, data: {} }), e => e.status === 409)
  assert.equal(count, 1)
})
