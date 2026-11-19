import { positiveInteger, requestJson } from './requestJson.js'

const inFlightPublishes = new Map()

export function buildStructuredRuleDraft(input) {
  const awardLevel = String(input.awardLevel || '').trim()
  if (!awardLevel) throw new TypeError('奖项等级不能为空')
  const competitionName = String(input.competitionName || '').trim()
  if (!competitionName) throw new TypeError('竞赛名称不能为空')
  const score = Number(input.score)
  if (!Number.isFinite(score) || score < 0) throw new TypeError('分值必须为非负数')

  const term = (value, allowAny = true) => {
    const text = String(value || '').trim()
    return text || (allowAny ? { any: true } : '')
  }
  return {
    name: String(input.name || '').trim(),
    faculty_id: input.facultyId || null,
    material_category: 'competition',
    score,
    description: String(input.description || '').trim() || null,
    match_terms: {
      competition_name: competitionName,
      award_level: awardLevel,
      competition_level: term(input.competitionLevel),
      region: term(input.region),
      group: term(input.group),
      track: term(input.track)
    }
  }
}

export function createStructuredRuleDraft(data, signal) {
  return requestJson('/api/structured-rules/drafts', { method: 'POST', data, signal })
}

export function previewStructuredRule(id, signal) {
  return requestJson(`/api/structured-rules/${positiveInteger(id)}/preview`, {
    method: 'POST', signal
  })
}

export function publishStructuredRule(id, version, signal) {
  const ruleId = positiveInteger(id)
  const draftVersion = positiveInteger(version)
  const key = `${ruleId}:${draftVersion}`
  if (inFlightPublishes.has(key)) return inFlightPublishes.get(key)
  const request = requestJson(`/api/structured-rules/${ruleId}/publish`, {
    method: 'POST', data: { version: draftVersion }, signal
  }).finally(() => inFlightPublishes.delete(key))
  inFlightPublishes.set(key, request)
  return request
}

export function disableStructuredRule(id, signal) {
  return requestJson(`/api/structured-rules/${positiveInteger(id)}/disable`, {
    method: 'POST', signal
  })
}

export function getUncoveredTerms(signal) {
  return requestJson('/api/structured-rules/uncovered-terms', { signal })
}

export default {
  buildStructuredRuleDraft,
  createStructuredRuleDraft,
  previewStructuredRule,
  publishStructuredRule,
  disableStructuredRule,
  getUncoveredTerms
}
