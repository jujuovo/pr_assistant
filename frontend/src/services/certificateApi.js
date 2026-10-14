import { requestJson, positiveInteger } from './requestJson.js'

const base = '/api/certificates'
// 组件的申请 ID 可能来自路由字符串；只接受规范的正整数。
function applicationPath(id) {
  if (typeof id === 'string' && /^[1-9]\d*$/.test(id)) id = Number(id)
  return `${base}/applications/${positiveInteger(id)}`
}

export const certificateApi = {
  createPreview: (files, signal) => {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    return requestJson(`${base}/previews`, { method: 'POST', data: form, signal, timeoutMs: 60000 })
  },
  confirmPreview: (id, data) => requestJson(`${applicationPath(id)}/confirm-preview`, { method: 'POST', data }),
  getCatalog: signal => requestJson(`${base}/catalog`, { signal }),
  getAssessment: (id, signal) => requestJson(applicationPath(id), { signal }),
  retry: (id, version) => requestJson(`${applicationPath(id)}/retry`, {
    method: 'POST', data: { version: positiveInteger(version) }
  }),
  getArtifactUrl: (id, version, path) => {
    if (typeof path !== 'string' || path.split('/').some(part => !part || part === '.' || part === '..' || part.includes('\\'))) {
      throw new TypeError('无效的证据文件路径')
    }
    return `${applicationPath(id)}/artifacts/${positiveInteger(version)}/${path.split('/').map(encodeURIComponent).join('/')}`
  }
}

export default certificateApi
