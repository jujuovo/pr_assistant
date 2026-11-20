import { requestJson, positiveInteger } from './requestJson.js'

export const MATERIAL_CATEGORIES = Object.freeze([
  'academic',
  'competition',
  'language',
  'student_work',
  'honor',
  'certification',
  'social_practice',
  'research',
  'competition_evidence',
  'volunteer'
])
const base = '/api/materials'
function recordsPath(category) {
  if (!MATERIAL_CATEGORIES.includes(category)) throw new TypeError('不支持的材料类别')
  return `${base}/${category}/records`
}
const recordPath = (category, id) => `${recordsPath(category)}/${positiveInteger(id)}`
const versionAction = (action, category, id, version) =>
  requestJson(`${recordPath(category, id)}/${action}`, {
    method: 'POST',
    data: { version: positiveInteger(version) }
  })

export const materialApi = {
  getCompetitionContext: (signal) => requestJson(`${base}/competition/context`, { signal }),
  estimateCompetition: (data) =>
    requestJson(`${base}/competition/estimate`, { method: 'POST', data: { data } }),
  saveCompetitionDraft: (id, version, data, files) => {
    const form = new FormData()
    form.append('version', String(positiveInteger(version)))
    form.append('data', JSON.stringify(data))
    for (const file of Array.from(files || [])) form.append('files', file)
    return requestJson(recordPath('competition', id), {
      method: 'PATCH',
      data: form,
      timeoutMs: 60000
    })
  },
  getCompetitionWorkbenchSummary: (signal) =>
    requestJson(`${base}/competition/workbench-summary`, { signal }),
  getCompetitionPackage: (signal) => requestJson(`${base}/competition/rules/current`, { signal }),
  searchCompetitionCatalog: (q = '', signal) =>
    requestJson(`${base}/competition/catalog?q=${encodeURIComponent(q)}`, { signal }),
  getCompetitionCatalogItem: (competitionId, signal) =>
    requestJson(`${base}/competition/catalog/${encodeURIComponent(competitionId)}`, { signal }),
  getCompetitionFeedback: (year, signal) =>
    requestJson(`${base}/competition/feedback?year=${positiveInteger(year)}`, { signal }),
  getCompetitionReviewContext: (id, signal) =>
    requestJson(`${recordPath('competition', id)}/review-context`, { signal }),
  getTeacherCompetitionSummary: (studentId, year, signal) =>
    requestJson(
      `${base}/competition/students/${encodeURIComponent(studentId)}/summary?year=${positiveInteger(year)}`,
      { signal }
    ),
  getTypes: (signal) => requestJson(`${base}/types`, { signal }),
  getOpenApi: (signal) => requestJson(`${base}/openapi.json`, { signal }),
  listRecords: (category, filters = {}, signal) => {
    const query = new URLSearchParams()
    for (const key of ['year', 'student_id', 'status', 'limit', 'after_id', 'reviewed']) {
      const value = filters[key]
      if (value !== undefined && value !== null && value !== '' && value !== 'all')
        query.set(key, String(value))
    }
    return requestJson(`${recordsPath(category)}${query.size ? `?${query}` : ''}`, { signal })
  },
  createRecord: (category, data) => requestJson(recordsPath(category), { method: 'POST', data }),
  createManualRecord: (category, year, data, files, signal) => {
    const form = new FormData()
    form.append('year', String(positiveInteger(year)))
    form.append('data', JSON.stringify(data))
    const originals = Array.from(files || [])
    if (!originals.length || originals.length > 10) throw new TypeError('请选择1至10个证明原件')
    for (const file of originals) {
      if (!(file instanceof Blob)) throw new TypeError('证明原件必须为文件')
      form.append('files', file)
    }
    return requestJson(recordsPath(category), {
      method: 'POST',
      data: form,
      signal,
      timeoutMs: 60000
    })
  },
  getRecord: (category, id, signal) => requestJson(recordPath(category, id), { signal }),
  // PATCH 完整替换 data，调用方须传所有要保留的业务字段。
  updateRecord: (category, id, version, data) =>
    requestJson(recordPath(category, id), {
      method: 'PATCH',
      data: { version: positiveInteger(version), data }
    }),
  uploadAttachments: (category, id, version, files, signal) => {
    const path = recordPath(category, id)
    const form = new FormData()
    form.append('version', String(positiveInteger(version)))
    const items = Array.from(files || [])
    if (!items.length || items.length > 10) throw new TypeError('请选择 1 至 10 个附件')
    for (const file of items) {
      if (!(file instanceof Blob)) throw new TypeError('附件必须是文件')
      form.append('files', file)
    }
    return requestJson(`${path}/attachments`, {
      method: 'POST',
      data: form,
      signal,
      timeoutMs: 60000
    })
  },
  getAttachmentUrl: (category, id, attachmentId) =>
    `${recordPath(category, id)}/attachments/${positiveInteger(attachmentId)}`,
  submit: (category, id, version) => versionAction('submit', category, id, version),
  startVolunteerOcr: (id, version) => versionAction('ocr', 'volunteer', id, version),
  appealVolunteer: (id, version, reason) =>
    requestJson(`${recordPath('volunteer', id)}/appeal`, {
      method: 'POST',
      data: { version: positiveInteger(version), reason }
    }),
  reconfirmSubmit: (category, id, version, ruleVersionId) =>
    requestJson(`${recordPath(category, id)}/reconfirm-submit`, {
      method: 'POST',
      data: {
        version: positiveInteger(version),
        rule_version_id: positiveInteger(ruleVersionId),
        confirmed: true
      }
    }),
  reconfirmCompetition: (id, version, confirmedTerms) =>
    requestJson(`${recordPath('competition', id)}/reconfirm-submit`, {
      method: 'POST',
      data: { version: positiveInteger(version), confirmed_terms: confirmedTerms, confirmed: true }
    }),
  abandon: (category, id, version) => versionAction('abandon', category, id, version),
  createCorrection: (category, id, version, confirmedTerms) =>
    requestJson(`${recordPath(category, id)}/corrections`, {
      method: 'POST',
      data: { version: positiveInteger(version), confirmed_terms: confirmedTerms }
    }),
  startCompetitionOcr: (id, version) =>
    requestJson(`${recordPath('competition', id)}/ocr`, {
      method: 'POST',
      data: { version: positiveInteger(version) }
    }),
  getCompetitionOcr: (id, jobId, signal) =>
    requestJson(`${recordPath('competition', id)}/ocr/${encodeURIComponent(jobId)}`, { signal }),
  cancelCompetitionOcr: (id, version, jobId) =>
    requestJson(`${recordPath('competition', id)}/ocr/${encodeURIComponent(jobId)}/cancel`, {
      method: 'POST',
      data: { version: positiveInteger(version) }
    }),
  withdraw: (category, id, version) => versionAction('withdraw', category, id, version),
  check: (category, id, version) => versionAction('check', category, id, version),
  review: (category, id, version, decision, comment) =>
    requestJson(`${recordPath(category, id)}/review`, {
      method: 'POST',
      data: { version: positiveInteger(version), decision, comment }
    }),
  reviewCompetition: (id, version, decision, comment, idempotencyKey, ocrConfirmed) => {
    if (!['approve', 'return'].includes(decision)) throw new TypeError('竞赛审核只能通过或退回')
    if (!idempotencyKey) throw new TypeError('竞赛审核必须提供幂等键')
    return requestJson(`${recordPath('competition', id)}/review`, {
      method: 'POST',
      data: {
        version: positiveInteger(version),
        decision,
        comment: String(comment || '').trim(),
        idempotency_key: String(idempotencyKey),
        ...(ocrConfirmed === undefined ? {} : { ocr_confirmed: ocrConfirmed })
      }
    })
  },
  getEvents: (category, id, signal) =>
    requestJson(`${recordPath(category, id)}/events`, { signal }),
  // 传入 version、attachment_id、project_key 启动已适配的识别；不自动确认或提交。
  recognize: (category, id, data) =>
    requestJson(`${recordPath(category, id)}/recognize`, { method: 'POST', data }),
  parseAcademicCsv: (term, file, signal) => {
    if (!(file instanceof Blob)) throw new TypeError('请选择 CSV 文件')
    const form = new FormData()
    form.append('term', term)
    form.append('file', file)
    return requestJson(`${base}/academic/parse-csv`, { method: 'POST', data: form, signal })
  },
  importSources: (data) => requestJson(`${base}/sources/import`, { method: 'POST', data }),
  getSource: (id, signal) => requestJson(`${base}/sources/${positiveInteger(id)}`, { signal })
}

export default materialApi
