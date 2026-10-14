import { requestJson, positiveInteger } from './requestJson.js'

export const MATERIAL_CATEGORIES = Object.freeze(['academic', 'competition', 'language', 'student_work', 'honor'])
const base = '/api/materials'
function recordsPath(category) {
  if (!MATERIAL_CATEGORIES.includes(category)) throw new TypeError('不支持的材料类别')
  return `${base}/${category}/records`
}
const recordPath = (category, id) => `${recordsPath(category)}/${positiveInteger(id)}`
const versionAction = (action, category, id, version) => requestJson(`${recordPath(category, id)}/${action}`, {
  method: 'POST', data: { version: positiveInteger(version) }
})

export const materialApi = {
  getTypes: signal => requestJson(`${base}/types`, { signal }),
  getOpenApi: signal => requestJson(`${base}/openapi.json`, { signal }),
  listRecords: (category, filters = {}, signal) => {
    const query = new URLSearchParams()
    for (const key of ['year', 'student_id', 'status', 'limit', 'after_id']) {
      const value = filters[key]
      if (value !== undefined && value !== null && value !== '' && value !== 'all') query.set(key, String(value))
    }
    return requestJson(`${recordsPath(category)}${query.size ? `?${query}` : ''}`, { signal })
  },
  createRecord: (category, data) => requestJson(recordsPath(category), { method: 'POST', data }),
  getRecord: (category, id, signal) => requestJson(recordPath(category, id), { signal }),
  // PATCH 完整替换 data，调用方须传所有要保留的业务字段。
  updateRecord: (category, id, version, data) => requestJson(recordPath(category, id), {
    method: 'PATCH', data: { version: positiveInteger(version), data }
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
    return requestJson(`${path}/attachments`, { method: 'POST', data: form, signal, timeoutMs: 60000 })
  },
  getAttachmentUrl: (category, id, attachmentId) => `${recordPath(category, id)}/attachments/${positiveInteger(attachmentId)}`,
  submit: (category, id, version) => versionAction('submit', category, id, version),
  withdraw: (category, id, version) => versionAction('withdraw', category, id, version),
  check: (category, id, version) => versionAction('check', category, id, version),
  review: (category, id, version, decision, comment) => requestJson(`${recordPath(category, id)}/review`, {
    method: 'POST', data: { version: positiveInteger(version), decision, comment }
  }),
  getEvents: (category, id, signal) => requestJson(`${recordPath(category, id)}/events`, { signal }),
  // 预留接口目前返回 HTTP 501；调用方处理 error.code，不能显示“已识别”。
  recognize: (category, id) => requestJson(`${recordPath(category, id)}/recognize`, { method: 'POST' }),
  parseAcademicCsv: (term, file, signal) => {
    if (!(file instanceof Blob)) throw new TypeError('请选择 CSV 文件')
    const form = new FormData()
    form.append('term', term)
    form.append('file', file)
    return requestJson(`${base}/academic/parse-csv`, { method: 'POST', data: form, signal })
  },
  importSources: data => requestJson(`${base}/sources/import`, { method: 'POST', data }),
  getSource: (id, signal) => requestJson(`${base}/sources/${positiveInteger(id)}`, { signal })
}

export default materialApi
