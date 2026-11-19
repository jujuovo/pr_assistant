import { requestJson, positiveInteger } from './requestJson.js'

const inFlight = new Map()

export function buildReviewPayload({ status, comment = '', overrideEnabled = false,
  overrideScore = null, overrideReason = '', idempotencyKey }) {
  if (!['approved', 'rejected', 'needs_correction'].includes(status)) throw new TypeError('审核状态无效')
  const payload = { status, reviewComment: String(comment || '').trim() }
  if (idempotencyKey) payload.idempotency_key = idempotencyKey
  if (overrideEnabled) {
    const reason = String(overrideReason || '').trim()
    const score = Number(overrideScore)
    if (!Number.isFinite(score) || score < 0) throw new TypeError('人工改写分数必须为非负数')
    if (!reason) throw new TypeError('人工改写必须填写理由')
    payload.override_score = score
    payload.override_reason = reason
  }
  return payload
}

export function reviewApplication(applicationId, input) {
  const id = positiveInteger(applicationId)
  const payload = buildReviewPayload(input)
  const key = `${id}:${payload.idempotency_key || JSON.stringify(payload)}`
  if (inFlight.has(key)) return inFlight.get(key)
  const pending = requestJson(`/api/applications/${id}/review`, { method: 'POST', data: payload })
    .finally(() => inFlight.delete(key))
  inFlight.set(key, pending)
  return pending
}

export default { reviewApplication }
