import { positiveInteger, requestJson } from './requestJson.js'

const base = '/api/competition-rule-packages'
export const competitionRulePackageApi = {
  list: signal => requestJson(base, { signal }),
  copy: (sourcePackageId, targetCycle, idempotencyKey) => requestJson(`${base}/copy`, {
    method: 'POST', data: { source_package_id: positiveInteger(sourcePackageId),
      target_cycle: positiveInteger(targetCycle), idempotency_key: idempotencyKey }
  }),
  edit: (id, draftRevision, snapshot) => requestJson(`${base}/${positiveInteger(id)}/draft`, {
    method: 'PUT', data: { draft_revision: positiveInteger(draftRevision), snapshot }
  }),
  diff: (id, signal) => requestJson(`${base}/${positiveInteger(id)}/diff`, { signal }),
  validate: (id, signal) => requestJson(`${base}/${positiveInteger(id)}/validate`, {
    method: 'POST', signal
  }),
  publish: (id, draftRevision, idempotencyKey) => requestJson(
    `${base}/${positiveInteger(id)}/publish`, { method: 'POST', data: {
      draft_revision: positiveInteger(draftRevision), idempotency_key: idempotencyKey
    } }
  )
}
export default competitionRulePackageApi
