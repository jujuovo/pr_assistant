import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import materialApi, { MATERIAL_CATEGORIES } from '../src/services/materialApi.js'
import certificateApi from '../src/services/certificateApi.js'
import { requestJson } from '../src/services/requestJson.js'

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })
function capture(payload = { id: 1, version: 2 }) {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, ...options })
    return new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })
  }
  return calls
}

test('five categories preserve backend fields, PATCH replaces data, filters encode safely', async () => {
  const calls = capture()
  for (const category of MATERIAL_CATEGORIES) {
    const data = { year: 2026, data: { certificate_no: '测试' } }
    await materialApi.createRecord(category, data)
    assert.equal(calls.at(-1).url, `/api/materials/${category}/records`)
    assert.deepEqual(JSON.parse(calls.at(-1).body), data)
    assert.equal(calls.at(-1).credentials, 'include')
    await materialApi.updateRecord(category, 1, 2, { score: '560' })
    assert.equal(calls.at(-1).method, 'PATCH')
    assert.deepEqual(JSON.parse(calls.at(-1).body), { version: 2, data: { score: '560' } })
  }
  await materialApi.listRecords('language', { student_id: 'A&B', status: 'all', after_id: 0 })
  assert.equal(calls.at(-1).url, '/api/materials/language/records?student_id=A%26B&after_id=0')
  assert.throws(() => materialApi.getRecord('../other', 1), TypeError)
  assert.throws(() => materialApi.getRecord('language', true), TypeError)
})

test('multipart sends repeated files and version without Content-Type override', async () => {
  const calls = capture()
  const files = [new File(['one'], 'one.png'), new File(['two'], 'two.pdf')]
  await materialApi.uploadAttachments('honor', 1, 3, files)
  const sent = calls.at(-1)
  assert.equal(sent.url, '/api/materials/honor/records/1/attachments')
  assert.equal(sent.body.get('version'), '3')
  assert.deepEqual(sent.body.getAll('files').map(file => file.name), ['one.png', 'two.pdf'])
  assert.deepEqual(sent.headers, {})
  await materialApi.parseAcademicCsv('2026秋', new File(['csv'], 'grades.csv'))
  assert.equal(calls.at(-1).body.get('term'), '2026秋')
  assert.equal(calls.at(-1).body.get('file').name, 'grades.csv')
})

test('state changes carry version and review contract', async () => {
  const calls = capture()
  for (const action of ['submit', 'withdraw', 'check']) {
    await materialApi[action]('competition', 4, 5)
    assert.equal(calls.at(-1).url, `/api/materials/competition/records/4/${action}`)
    assert.deepEqual(JSON.parse(calls.at(-1).body), { version: 5 })
  }
  await materialApi.review('competition', 4, 5, 'verified', '已核对原件')
  assert.deepEqual(JSON.parse(calls.at(-1).body), { version: 5, decision: 'verified', comment: '已核对原件' })
})

test('catalog, sources, events and binary URLs use their correct endpoints', async () => {
  const calls = capture()
  await materialApi.getTypes(); await materialApi.getOpenApi()
  await materialApi.getRecord('academic', 1); await materialApi.getEvents('academic', 1)
  await materialApi.importSources({ records: [] }); await materialApi.getSource(2)
  await certificateApi.getCatalog(); await certificateApi.getAssessment('3'); await certificateApi.retry(3, 4)
  assert.deepEqual(calls.map(c => c.url), ['/api/materials/types', '/api/materials/openapi.json', '/api/materials/academic/records/1', '/api/materials/academic/records/1/events', '/api/materials/sources/import', '/api/materials/sources/2', '/api/certificates/catalog', '/api/certificates/applications/3', '/api/certificates/applications/3/retry'])
  assert.deepEqual(JSON.parse(calls.at(-1).body), { version: 4 })
  assert.equal(materialApi.getAttachmentUrl('honor', 1, 2), '/api/materials/honor/records/1/attachments/2')
  assert.equal(certificateApi.getArtifactUrl(3, 4, 'pages/a b.png'), '/api/certificates/applications/3/artifacts/4/pages/a%20b.png')
  assert.throws(() => certificateApi.getArtifactUrl(3, 4, '../private'), TypeError)
})

test('errors retain HTTP status/code, including unimplemented OCR; POST is not retried', async () => {
  for (const [status, payload] of [[401, { message: '请登录' }], [409, { error: '版本冲突' }], [501, { error: '未实现', code: 'recognition_not_implemented' }]]) {
    let calls = 0
    globalThis.fetch = async () => { calls++; return new Response(JSON.stringify(payload), { status }) }
    await assert.rejects(materialApi.recognize('language', 1), e => e.status === status && e.message === (payload.error || payload.message) && e.code === payload.code)
    assert.equal(calls, 1)
  }
  globalThis.fetch = async () => new Response('<html>too large</html>', { status: 413 })
  await assert.rejects(materialApi.getTypes(), e => e.status === 413 && e.payload === null)
})

test('cancellation and timeout remain distinguishable', async () => {
  globalThis.fetch = async (_, { signal }) => {
    signal.throwIfAborted()
    return new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true }))
  }
  const controller = new AbortController(); controller.abort()
  await assert.rejects(materialApi.getTypes(controller.signal), e => e.name === 'AbortError' && !e.code?.startsWith?.('REQUEST_'))
  await assert.rejects(requestJson('/api/materials/types', { timeoutMs: 5 }), e => e.code === 'REQUEST_TIMEOUT')
})

test('certificate preview uploads privately then confirms declarations on the same application', async () => {
  const calls = capture()
  await certificateApi.createPreview([new File(['image'], 'certificate.png')])
  assert.equal(calls[0].url, '/api/certificates/previews')
  assert.equal(calls[0].body.getAll('files')[0].name, 'certificate.png')
  assert.deepEqual(calls[0].headers, {})
  const declaration = { version: 2, student_values: [{ student: '学生修改值' }], submit: true }
  await certificateApi.confirmPreview(7, declaration)
  assert.equal(calls[1].url, '/api/certificates/applications/7/confirm-preview')
  assert.equal(calls[1].method, 'POST')
  assert.deepEqual(JSON.parse(calls[1].body), declaration)
})
