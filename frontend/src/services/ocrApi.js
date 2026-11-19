import { requestJson } from './requestJson.js'

const base = '/api/ocr'
export const OCR_PROJECTS = Object.freeze([
  'lanqiao', 'computer-design', 'software-design', 'challenge-cup', 'csp', 'social-practice', 'other'
])
function jobPath(id) {
  if (typeof id !== 'string' || !/^(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$/i.test(id)) {
    throw new TypeError('识别任务编号无效')
  }
  return `${base}/jobs/${id}`
}

export const ocrApi = {
  getCategories: signal => requestJson(`${base}/categories`, { signal }),
  recognize: (project, file, signal) => {
    if (!OCR_PROJECTS.includes(project)) throw new TypeError('不支持的识别项目')
    if (!(file instanceof Blob)) throw new TypeError('请选择图片文件')
    const form = new FormData()
    form.append('file', file, file.name || 'upload.png')
    return requestJson(`${base}/${project}/recognize`, { method: 'POST', data: form, signal, timeoutMs: 60000 })
  },
  getJob: (id, signal) => requestJson(jobPath(id), { signal }),
  getMapping: (id, signal) => requestJson(`${jobPath(id)}/mapping`, { signal }),
  // data 为学生确认后的完整业务字段；关联已有材料还须 material_record_id 和 version。
  confirmMaterial: (id, data) => requestJson(`${jobPath(id)}/confirm-material`, { method: 'POST', data })
}
export default ocrApi
