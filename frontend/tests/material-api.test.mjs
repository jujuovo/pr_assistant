import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import materialApi, { MATERIAL_CATEGORIES } from '../src/services/materialApi.js'
import certificateApi from '../src/services/certificateApi.js'
import workflowApi from '../src/services/workflowApi.js'
import { buildReviewPayload, reviewApplication } from '../src/services/applicationReviewApi.js'
import { scoreRows } from '../src/services/scorePresentation.js'
import { requestJson } from '../src/services/requestJson.js'
import structuredRuleApi from '../src/services/structuredRuleApi.js'
import { teacherReviewError } from '../src/services/teacherReviewFeedback.js'

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
  await materialApi.reconfirmSubmit('competition', 4, 6, 9)
  assert.equal(calls.at(-1).url, '/api/materials/competition/records/4/reconfirm-submit')
  assert.deepEqual(JSON.parse(calls.at(-1).body), {
    version: 6, rule_version_id: 9, confirmed: true
  })
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

test('competition API uses catalog schema, versioned OCR and authority-free reconfirm payloads', async () => {
  const calls = capture()
  await materialApi.getCompetitionContext(); await materialApi.getCompetitionPackage(); await materialApi.searchCompetitionCatalog('程序 设计')
  await materialApi.getCompetitionCatalogItem('c01/test')
  await materialApi.startCompetitionOcr(4, 5); await materialApi.getCompetitionOcr(4, 'job/1')
  await materialApi.cancelCompetitionOcr(4, 5, 'job/1')
  const facts = { competition_id: 'c01', project_name: '作品', award_date: '2027-01-01',
    level: 'national', award: 'first_or_above', event_year: 2027, participation_mode: 'individual' }
  await materialApi.reconfirmCompetition(4, 6, facts)
  assert.equal(calls[0].url, '/api/materials/competition/context')
  assert.equal(calls[2].url, '/api/materials/competition/catalog?q=%E7%A8%8B%E5%BA%8F%20%E8%AE%BE%E8%AE%A1')
  assert.equal(calls[3].url, '/api/materials/competition/catalog/c01%2Ftest')
  assert.deepEqual(JSON.parse(calls[4].body), { version: 5 })
  assert.equal(calls[5].url, '/api/materials/competition/records/4/ocr/job%2F1')
  assert.deepEqual(JSON.parse(calls[6].body), { version: 5 })
  const reconfirm = JSON.parse(calls[7].body)
  assert.deepEqual(reconfirm, { version: 6, confirmed_terms: facts, confirmed: true })
  for (const forbidden of ['rule_id','self_score','final_score','dynamic_coefficients']) assert(!(forbidden in reconfirm.confirmed_terms))
})

test('teacher competition review is read-only and sends no legacy rule or override fields', async () => {
  const calls = capture()
  await materialApi.getCompetitionReviewContext(4)
  await materialApi.getTeacherCompetitionSummary('S 1', 2028)
  await materialApi.reviewCompetition(4, 5, 'approve', '核验一致', 'review-key-1')
  assert.equal(calls[0].url, '/api/materials/competition/records/4/review-context')
  assert.equal(calls[1].url, '/api/materials/competition/students/S%201/summary?year=2028')
  const payload = JSON.parse(calls[2].body)
  assert.deepEqual(payload, { version: 5, decision: 'approve', comment: '核验一致', idempotency_key: 'review-key-1' })
  for (const field of ['rule_id','override_score','override_reason','final_score','confirmed_terms']) assert(!(field in payload))
  assert.throws(() => materialApi.reviewCompetition(4, 5, 'rejected', '', 'key'), /只能通过或退回/)
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

test('workflow api maps score and ranking requests without field fallbacks', async () => {
  const calls = capture()
  await workflowApi.getStudentScore('S 1', 2026)
  await workflowApi.getCurrentStudentScore('S 1')
  await workflowApi.previewScoreRecalculation({ year: 2026 })
  await workflowApi.executeScoreRecalculation({ preview_digest: 'digest' })
  await workflowApi.getRanking(3)
  await workflowApi.exportRanking(3, '学院公示')
  assert.deepEqual(calls.map(c => c.url), ['/api/workflow/students/S%201/score?year=2026',
    '/api/workflow/students/S%201/score/current',
    '/api/workflow/scores/recalculation-previews', '/api/workflow/scores/recalculation-executions',
    '/api/workflow/rankings/3', '/api/workflow/rankings/3/export'])
})

test('teacher review defaults to automatic score and explicit override requires a reason', async () => {
  const automatic = buildReviewPayload({ status: 'approved', comment: '原件真实' })
  assert.deepEqual(automatic, { status: 'approved', reviewComment: '原件真实' })
  assert.equal('finalScore' in automatic, false)
  assert.equal('override_score' in automatic, false)
  assert.throws(() => buildReviewPayload({ status: 'approved', overrideEnabled: true,
    overrideScore: 4, overrideReason: ' ' }), /理由/)
  assert.deepEqual(buildReviewPayload({ status: 'approved', overrideEnabled: true,
    overrideScore: 4, overrideReason: '复核等级', idempotencyKey: 'review-1' }), {
    status: 'approved', reviewComment: '', idempotency_key: 'review-1',
    override_score: 4, override_reason: '复核等级'
  })
})

test('review preserves blocked error codes and coalesces duplicate clicks', async () => {
  for (const code of ['needs_rule', 'source_version_conflict']) {
    globalThis.fetch = async () => new Response(JSON.stringify({ error: code, code }), { status: 409 })
    await assert.rejects(reviewApplication(7, { status: 'approved', idempotencyKey: code }),
      error => error.status === 409 && error.code === code)
  }
  let calls = 0
  let release
  globalThis.fetch = async () => {
    calls++
    await new Promise(resolve => { release = resolve })
    return new Response(JSON.stringify({ scoring_status: 'scored', score: { effective_score: '5.0000' } }))
  }
  const input = { status: 'approved', idempotencyKey: 'same-click' }
  const first = reviewApplication(7, input)
  const second = reviewApplication(7, input)
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(calls, 1)
  release()
  assert.deepEqual(await first, await second)

  globalThis.fetch = async () => new Response(JSON.stringify({
    overall_status: 'complete', verification_status: 'verified',
    scoring_status: 'verified_not_eligible', allowed_actions: ['view']
  }))
  const outside = await reviewApplication(7, {
    status: 'approved', idempotencyKey: 'outside-date'
  })
  assert.equal(outside.scoring_status, 'verified_not_eligible')
  assert.deepEqual(outside.allowed_actions, ['view'])
})

test('student score presentation keeps authoritative five and explains zero across refresh', () => {
  const dto = { entries: [
    { id: 1, project_source: { type: 'material', id: '7', category: 'competition' },
      verification_status: 'verified', scoring_status: 'scored', rule_version_id: 12,
      automatic_score: '5.0000', override_score: null, included_score: '5.0000',
      exclusion_reason: null, allowed_actions: [] },
    { id: null, project_source: { type: 'material', id: '8', category: 'honor_title' },
      verification_status: 'verified', scoring_status: 'verified_not_eligible',
      rule_version_id: null, automatic_score: null, override_score: null,
      included_score: '0', exclusion_reason: 'award_date_outside_cycle_window',
      allowed_actions: ['view'] }
  ] }
  const first = scoreRows(dto)
  assert.equal(first[0].includedScore, '5.0000')
  assert.equal(first[1].includedScore, '0')
  assert.equal(first[1].reason, 'award_date_outside_cycle_window')
  assert.deepEqual(scoreRows(structuredClone(dto)), first)
})

test('student pending rule states remain explicit without legacy total fallbacks', () => {
  const dto = { status: 'no_authoritative_snapshot', comprehensive_score: null, entries: [
    { id: null, source_version: 2,
      project_source: { type: 'material', id: '8', category: 'competition' },
      verification_status: 'unreviewed', scoring_status: 'rule_unmatched',
      rule_version_id: null, candidate_score: null, included_score: '0',
      exclusion_reason: '材料词条没有对应计分', allowed_actions: ['edit'] },
    { id: null, source_version: 3,
      project_source: { type: 'material', id: '9', category: 'competition' },
      verification_status: 'unreviewed', scoring_status: 'rule_available',
      rule_version_id: 12, candidate_score: '3.0', included_score: '0',
      exclusion_reason: '规则已可用，等待学生确认', allowed_actions: ['confirm_submit'] }
  ] }
  const rows = scoreRows(dto)
  assert.equal(rows[0].includedScore, '0')
  assert.equal(rows[0].reason, '材料词条没有对应计分')
  assert.equal(rows[1].ruleVersionId, 12)
  assert.equal(rows[1].sourceVersion, 3)
  assert.equal(dto.comprehensive_score, null)
})

test('structured rule draft maps third prize and explicit wildcard dimensions', () => {
  assert.deepEqual(structuredRuleApi.buildStructuredRuleDraft({
    name: '蓝桥杯三等奖', facultyId: 3, competitionName: '蓝桥杯', awardLevel: '三等奖',
    competitionLevel: '国家级', region: '', group: '软件类', track: '', score: 3
  }), {
    name: '蓝桥杯三等奖', faculty_id: 3, material_category: 'competition', score: 3,
    description: null, match_terms: { competition_name: '蓝桥杯', award_level: '三等奖',
      competition_level: '国家级', region: { any: true }, group: '软件类', track: { any: true } }
  })
  assert.throws(() => structuredRuleApi.buildStructuredRuleDraft({
    name: '缺少等级', competitionName: '蓝桥杯', awardLevel: '', score: 3
  }), /奖项等级/)
})

test('structured rule api preserves ambiguity conflicts and coalesces publish clicks', async () => {
  globalThis.fetch = async (url) => {
    if (url.endsWith('/preview')) return new Response(JSON.stringify({
      publishable: false, conflicts: [12, 19], cycle_code: 2026
    }))
    return new Response(JSON.stringify({ error: '规则存在歧义', code: 'ambiguous_scoring_rules',
      conflicts: [12, 19] }), { status: 409 })
  }
  const preview = await structuredRuleApi.previewStructuredRule(7)
  assert.deepEqual(preview.conflicts, [12, 19])
  await assert.rejects(structuredRuleApi.publishStructuredRule(7, 2), error =>
    error.code === 'ambiguous_scoring_rules' && error.payload.conflicts.length === 2)

  let calls = 0; let release
  globalThis.fetch = async () => {
    calls++
    await new Promise(resolve => { release = resolve })
    return new Response(JSON.stringify({ rule_version_id: 21, created: true }))
  }
  const first = structuredRuleApi.publishStructuredRule(8, 1)
  const second = structuredRuleApi.publishStructuredRule(8, 1)
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(calls, 1)
  release()
  assert.deepEqual(await first, await second)
})

test('uncovered term api reads only the privacy-safe aggregate endpoint', async () => {
  const calls = capture({ items: [{ affected_count: 2, normalized_terms: { award_level: '三等奖' } }] })
  const result = await structuredRuleApi.getUncoveredTerms()
  assert.equal(calls[0].url, '/api/structured-rules/uncovered-terms')
  assert.equal(calls[0].method, 'GET')
  assert.equal(result.items[0].affected_count, 2)
})

test('teacher feedback assigns unmatched materials to student and admin workflow', () => {
  assert.equal(teacherReviewError({ code: 'review_not_available' }),
    '该材料尚未由学生正式提交，无需教师处理')
  assert.equal(teacherReviewError({ code: 'source_version_conflict' }),
    '材料版本已变化，请刷新后重试')
  assert.doesNotMatch(teacherReviewError({ code: 'review_not_available' }), /缺少.*规则|教师.*配置/)
})
