import { requestJson, positiveInteger } from './requestJson.js'
const base = '/api/workflow'
export const workflowApi = {
  getScoreSource: (studentId, year, sourceType, sourceId, signal) =>
    requestJson(
      `${base}/students/${encodeURIComponent(studentId)}/score-sources/${encodeURIComponent(sourceType)}/${positiveInteger(Number(sourceId))}?year=${positiveInteger(year)}`,
      { signal }
    ),
  getStudentScore: (studentId, year, signal) =>
    requestJson(
      `${base}/students/${encodeURIComponent(studentId)}/score?year=${positiveInteger(year)}`,
      { signal }
    ),
  getCurrentStudentScore: (studentId, signal) =>
    requestJson(`${base}/students/${encodeURIComponent(studentId)}/score/current`, { signal }),
  previewScoreRecalculation: (data) =>
    requestJson(`${base}/scores/recalculation-previews`, { method: 'POST', data }),
  executeScoreRecalculation: (data) =>
    requestJson(`${base}/scores/recalculation-executions`, { method: 'POST', data }),
  getRanking: (batchId, signal) =>
    requestJson(`${base}/rankings/${positiveInteger(batchId)}`, { signal }),
  exportRanking: (batchId, purpose) =>
    requestJson(`${base}/rankings/${positiveInteger(batchId)}/export`, {
      method: 'POST',
      data: { purpose }
    }),
  generateRanking: (data) => requestJson(`${base}/rankings/generate`, { method: 'POST', data }),
  rankingCommand: (batchId, action, version, idempotencyKey, data = {}) =>
    requestJson(
      `${base}/rankings/${positiveInteger(batchId)}/commands/${encodeURIComponent(action)}`,
      {
        method: 'POST',
        data: { ...data, version: positiveInteger(version), idempotency_key: idempotencyKey }
      }
    )
}
export default workflowApi
