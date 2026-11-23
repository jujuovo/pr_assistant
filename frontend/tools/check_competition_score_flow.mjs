/** Real HTTP acceptance using the same adapters and score mapping as Vue pages. */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import materialApi from '../src/services/materialApi.js'
import workflowApi from '../src/services/workflowApi.js'
import { buildCompetitionFacts } from '../src/services/competitionMaterial.js'
import { scoreRows } from '../src/services/scorePresentation.js'

let input = ''
for await (const part of process.stdin) input += part
const config = JSON.parse(input)
const nativeFetch = globalThis.fetch
const requests = []
let identity = 'student0'
globalThis.fetch = async (path, options = {}) => {
  const response = await nativeFetch(new URL(path, config.base), {
    ...options, headers: { ...options.headers, Cookie: config.cookies[identity] }
  })
  requests.push({ method: options.method || 'GET', path, status: response.status })
  return response
}
const scope = { facultyId: config.faculty, departmentId: config.department, majorId: config.major, year: 2028 }
const samples = []
const pdf = () => new File(['%PDF-1.4\nacceptance synthetic proof'], 'proof.pdf', { type: 'application/pdf' })
async function verifyScore(studentId, recordId, expected) {
  const dto = await workflowApi.getCurrentStudentScore(studentId)
  const entry = scoreRows(dto).find(row => Number(row.sourceId) === recordId && row.sourceType === 'material')
  assert.ok(entry, JSON.stringify(dto))
  assert.equal(entry.group, 'academic')
  assert.equal(Number(entry.candidateScore), expected)
  assert.equal(Number(entry.includedScore), expected)
  assert.ok(dto.faculty_scoring_policy?.title)
  assert.equal(Number(dto.categories.academic.effective_score), expected)
  assert.equal(Number(dto.comprehensive_score), Number((60.8 + expected).toFixed(4)))
  return dto
}
async function journey(role, facts, expected, image = false) {
  identity = role
  const detail = await materialApi.getCompetitionCatalogItem(facts.competition_id)
  const form = buildCompetitionFacts(facts, detail.field_schema)
  const estimate = await materialApi.estimateCompetition(form)
  assert.equal(Number(estimate.declared_estimate), expected)
  const file = image ? new File([readFileSync(config.sample)], 'sample.jpg', { type: 'image/jpeg' }) : pdf()
  let row = await materialApi.createManualRecord('competition', 2028, form, [file])
  assert.equal(row.data.level, form.level)
  assert.equal(Number(row.ocr_assessment.declared_estimate), expected)
  if (image) {
    assert.equal(row.workflow_state, 'ocr_queued')
    return { id: row.id, facts: form, role, expected }
  }
  assert.equal(row.workflow_state, 'ready_to_submit')
  row = await materialApi.submit('competition', row.id, row.version)
  identity = 'teacher'
  const context = await materialApi.getCompetitionReviewContext(row.id)
  assert.ok(context)
  await materialApi.reviewCompetition(row.id, row.version, 'approve', '', 'mapping-' + row.id, true)
  identity = role
  const approved = await materialApi.getRecord('competition', row.id)
  assert.equal(approved.workflow_state, 'approved')
  return { id: row.id, facts: form, role, expected }
}
const fact = (extra = {}) => ({
  competition_id: 'c15-lanqiao-cup', project_name: '独立映射测试', award_date: '2027-05-01',
  event_year: 2027, level: 'national', award: 'first_or_above', participation_mode: 'individual', ...extra
})
if (config.phase === 'matrix') {
  const awards = [['national', 'first_or_above', 10], ['national', 'second', 5],
    ['national', 'third', 2], ['provincial', 'first_or_above', 1], ['provincial', 'second', 0.5]]
  const teams = [[null, null, 3], [2, 1, 3], [3, 2, 3], [4, 3, 4], [6, 5, 5]]
  let index = 0
  for (const [level, award, base] of awards) for (const [size, rank, divisor] of teams) {
    const role = 'student' + index++
    const facts = fact({ level, award, project_name: '映射-' + index,
      ...(size ? { participation_mode: 'team', team_size: size, personal_rank: rank } : {}) })
    const expected = Number((base / divisor).toFixed(4))
    const record = await journey(role, facts, expected)
    await verifyScore(config.students[role], record.id, expected)
    identity = 'teacher'
    const teacher = await workflowApi.getStudentScore(config.students[role], 2028)
    assert.equal(Number(teacher.categories.academic.effective_score), expected)
    samples.push({ ...record, base, divisor })
  }
  identity = 'student0'
  await assert.rejects(materialApi.estimateCompetition(fact({ level: 'provincial', award: 'third' })), e => e.code === 'provincial_third_award_forbidden')
  await assert.rejects(materialApi.estimateCompetition(fact({ participation_mode: 'team', team_size: 6, personal_rank: 6 })), e => e.code === 'team_rank_not_eligible')
  await assert.rejects(materialApi.estimateCompetition({ ...fact(), candidate_score: 999 }), e => e.status === 400)
  // Four different event years isolate the top-three limit from same-event deduplication.
  const values = [3.3333, 1.6667, 0.3333, 0.1667]
  const aggregate = []
  for (let i = 0; i < 4; i++) aggregate.push(await journey('aggregate', fact({
    project_name: '限项-' + i, event_year: 2025 + i, award_date: (2025 + i) + (i === 3 ? '-05-01' : '-10-01'),
    level: i < 2 ? 'national' : 'provincial', award: i % 2 ? 'second' : 'first_or_above'
  }), values[i]))
  identity = 'aggregate'
  const total = await workflowApi.getCurrentStudentScore(config.students.aggregate)
  assert.equal(Number(total.categories.academic.effective_score), 5.3333)
  const excluded = scoreRows(total).find(row => Number(row.sourceId) === aggregate[3].id)
  assert.equal(excluded.included, false)
  assert.equal(Number(excluded.includedScore), 0)
  // Same work across national/provincial stages must not receive two scores.
  const high = await journey('duplicate', fact({ project_name: '同一作品' }), 3.3333)
  await journey('duplicate', fact({ project_name: '同一作品', level: 'provincial' }), 0.3333)
  identity = 'duplicate'
  const duplicate = await workflowApi.getCurrentStudentScore(config.students.duplicate)
  assert.equal(Number(duplicate.categories.academic.effective_score), 3.3333)
  assert.equal(scoreRows(duplicate).filter(row => row.included).length, 1)
  // Three A+ awards give 30 item points but the academic group is capped at 15.
  for (const id of ['c01-china-college-student-innovation', 'c02-challenge-cup-academic', 'c03-challenge-cup-business-plan'])
    await journey('cap', fact({ competition_id: id, project_name: '封顶-' + id }), 10)
  identity = 'cap'
  const capped = await workflowApi.getCurrentStudentScore(config.students.cap)
  assert.equal(scoreRows(capped).reduce((sum, row) => sum + Number(row.includedScore), 0), 30)
  assert.equal(Number(capped.categories.academic.effective_score), 15)
  assert.equal(Number(capped.comprehensive_score), 75.8)
  identity = 'teacher'
  const report = await workflowApi.getTeacherScoreReport(scope)
  for (const sample of samples) {
    const student = report.students.find(s => s.student_id === config.students[sample.role])
    assert.equal(Number(student.academic_total), sample.expected)
    assert.equal(Number(student.items[0].included_score), sample.expected)
  }
  identity = 'work'
  const work = await materialApi.createManualRecord('student_work', 2028, {
    as_of: '2028-08-31', appointments: [{ organization: '学院', position: '院学生会主席团成员',
      position_level: '院', start_date: '2025-09-01', end_date: null, assessment_result: '自评100' }]
  }, [pdf()])
  const workSubmitted = await materialApi.submit('student_work', work.id, work.version)
  identity = 'teacher'
  await materialApi.review('student_work', work.id, workSubmitted.version, 'verified', '核定岗位与考核表', {
    idempotency_key: 'work-mapping', verified_facts: { assessments: [{
      appointment_index: 0, academic_year: 2025, scope: 'college', mapped_position: '院学生会主席团成员',
      mapping_basis: '任职证明第一条', tenure: 'full_year', tenure_basis: '完整学年',
      assessment_score: 80, assessor_role: '辅导员', assessment_source: '签章考核表', proof_date: '2028-08-31'
    }] }
  })
  identity = 'work'
  const workScore = await workflowApi.getCurrentStudentScore(config.students.work)
  const workRow = scoreRows(workScore).find(row => row.category === 'student_work')
  assert.equal(workRow.group, 'comprehensive')
  assert.equal(Number(workRow.includedScore), 1.2)
  assert.equal(Number(workScore.categories.academic.effective_score), 0)
  assert.equal(Number(workScore.categories.comprehensive.effective_score), 1.2)
  assert.equal(Number(workScore.comprehensive_score), 62)
  const queued = await journey('ocr', fact({ project_name: '真实OCR链路验收', level: 'provincial', award: 'second' }), 0.1667, true)
  console.log(JSON.stringify({ matrix: samples, aggregate_total: 5.3333, duplicate_total: 3.3333,
    cap: { item_total: 30, group_total: 15, comprehensive: 75.8 }, queued, requests }))
} else {
  const record = config.record
  identity = record.role
  let row = await materialApi.getRecord('competition', record.id)
  assert.equal(row.workflow_state, 'ready_to_submit', JSON.stringify(row.ocr_assessment))
  assert.ok(row.ocr_raw_terms?.report?.fields)
  assert.equal(row.data.award, record.facts.award)
  assert.equal(row.data.level, record.facts.level)
  assert.equal(Number(row.ocr_assessment.declared_estimate), record.expected)
  const report = row.ocr_raw_terms.report
  row = await materialApi.submit('competition', row.id, row.version)
  identity = 'teacher'
  await assert.rejects(materialApi.reviewCompetition(row.id, row.version, 'approve', '', 'ocr-no-confirm'),
    e => e.code === 'ocr_manual_confirmation_required')
  await materialApi.reviewCompetition(row.id, row.version, 'approve', '', 'ocr-confirm', true)
  identity = record.role
  await verifyScore(config.students[record.role], record.id, record.expected)
  console.log(JSON.stringify({ ocr_fields: report.fields, ocr_status: report.status,
    declared_score: record.expected, teacher_confirmation_required: true, requests }))
}
