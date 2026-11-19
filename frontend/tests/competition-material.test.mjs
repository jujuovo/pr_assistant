import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildCompetitionFacts, competitionErrorMessage, legalCompetitionOptions, ocrView, validateCompetitionForm } from '../src/services/competitionMaterial.js'

const schema = { levels: ['national', 'provincial'], awards_by_level: {
  national: ['first_or_above', 'second', 'third'], provincial: ['first_or_above', 'second']
}, formats: ['regional', 'world_final'], participation_modes: ['individual', 'team'] }

test('catalog schema excludes provincial third and invitation and category is not writable', () => {
  assert.deepEqual(legalCompetitionOptions(schema, 'provincial').awards, ['first_or_above', 'second'])
  assert(!legalCompetitionOptions(schema, 'national').formats.includes('invitation'))
  assert.throws(() => buildCompetitionFacts({ competition_id: '', level: 'national' }, schema), /正式目录/)
  const facts = buildCompetitionFacts({ competition_id: 'c01', project_name: '作品', award_date: '2027-01-01',
    level: 'national', award: 'first_or_above', event_year: '2027', participation_mode: 'individual', category: 'A+' }, schema)
  assert(!('category' in facts))
})

test('team fields are linked and legacy authority fields never enter payload', () => {
  assert.throws(() => buildCompetitionFacts({ competition_id: 'c01', level: 'national', award: 'second',
    participation_mode: 'team', team_size: 2, personal_rank: 3 }, schema), /团队/)
  assert.throws(() => buildCompetitionFacts({ competition_id: 'c01', rule_id: 9 }, schema), /禁止字段/)
})

test('OCR raw and confirmed values remain distinct including late result isolation', () => {
  const view = ocrView({ status: 'ignored', raw_result: { award: 'OCR值' }, late_result_ignored: true }, { award: '学生值' })
  assert.equal(view.raw.award, 'OCR值'); assert.equal(view.confirmed.award, '学生值'); assert(view.lateResultIgnored)
})

test('OCR view preserves slow, failed and cancelled manual-entry states', () => {
  assert.equal(ocrView({ status: 'running' }, {}).status, 'running')
  assert.equal(ocrView({ status: 'failed', error: 'offline' }, { project_name: '手填' }).confirmed.project_name, '手填')
  assert.equal(ocrView({ status: 'cancelled' }, { award: 'second' }).status, 'cancelled')
  assert.equal(ocrView({ status: 'ignored', late_result_ignored: true }, { award: 'second' }).confirmed.award, 'second')
})

test('journey errors have stable student-facing messages', () => {
  for (const code of ['duplicate_submission', 'version_conflict', 'rule_package_changed']) assert.notEqual(competitionErrorMessage(code), competitionErrorMessage('unknown'))
})

test('field validation links required, date, award and team relationships', () => {
  const requiredSchema = { ...schema, required: ['competition_id', 'project_name', 'award_date', 'level', 'award', 'event_year', 'participation_mode'] }
  const missing = validateCompetitionForm({}, requiredSchema, { start: '2025-09-01', end: '2028-08-31' })
  assert.equal(missing.competition_id, '正式目录条目为必填项')
  assert(missing.project_name)
  const invalid = validateCompetitionForm({ competition_id: 'c01', project_name: '作品', award_date: '2029-01-01',
    level: 'provincial', award: 'third', event_year: '2027', participation_mode: 'team', team_size: 2, personal_rank: 3 },
  requiredSchema, { start: '2025-09-01', end: '2028-08-31' })
  assert.match(invalid.award_date, /不得晚于/)
  assert.match(invalid.award, /不匹配/)
  assert.match(invalid.personal_rank, /团队人数范围/)
})
