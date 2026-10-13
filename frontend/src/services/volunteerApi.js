// 志愿工时 OCR：使用同源代理和现有登录 Cookie，返回后端原始字段。
// 上传成功仅表示入队；页面应查询批次状态，完成后使用最新 version 提交。
async function request(path, { method = 'GET', data, signal, timeoutMs = 30000 } = {}) {
  const controller = new AbortController()
  let timedOut = false
  const cancel = () => controller.abort()
  signal?.addEventListener('abort', cancel, { once: true })
  if (signal?.aborted) cancel()
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  try {
    const multipart = data instanceof FormData
    const response = await fetch(`/api/automation${path}`, {
      method,
      credentials: 'include',
      cache: 'no-store',
      signal: controller.signal,
      headers: data !== undefined && !multipart ? { 'Content-Type': 'application/json' } : {},
      body: data === undefined ? undefined : multipart ? data : JSON.stringify(data)
    })
    // 网关可能返回 HTML；错误保留 HTTP 状态，供页面处理 401/409/413。
    const raw = await response.text()
    let payload
    try {
      payload = JSON.parse(raw)
    } catch {
      payload = null
    }
    if (!response.ok || payload === null) {
      const error = new Error(
        payload?.error || payload?.message || `接口异常（HTTP ${response.status}）`
      )
      error.status = response.status
      error.payload = payload
      throw error
    }
    return payload
  } catch (error) {
    if (timedOut) {
      const timeout = new Error('请求超时；请先查询批次状态，勿重复上传或提交')
      timeout.code = 'REQUEST_TIMEOUT'
      throw timeout
    }
    // 主动取消保留 AbortError，让页面静默结束查询。
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
  }
}

function positiveInteger(value) {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new TypeError('ID、年度、页码和版本必须为正整数')
  }
  return value
}

const batchPath = id => `/volunteer/batches/${positiveInteger(id)}`

export const volunteerApi = {
  getPolicy: year => request(`/volunteer/policies/${positiveInteger(year)}`),
  savePolicy: (year, policy) => request(`/volunteer/policies/${positiveInteger(year)}`, {
    method: 'PUT', data: policy
  }),
  listBatches: (page = 1, signal) => request(`/volunteer/batches?page=${positiveInteger(page)}`, { signal }),
  getBatch: (id, signal) => request(batchPath(id), { signal }),
  getEvidence: (id, signal) => request(`/items/${positiveInteger(id)}/evidence`, { signal }),
  // 图片为受保护的二进制响应，供 img.src 使用，不能走 JSON 请求封装。
  getImageUrl: id => `/api/automation/items/${positiveInteger(id)}/image`,
  // FormData: material_type、year、重复的 files、可选 claimed_hours JSON 数组。
  upload: (form, signal) => {
    if (!(form instanceof FormData)) throw new TypeError('上传参数必须是 FormData')
    return request('/volunteer/batches', { method: 'POST', data: form, signal, timeoutMs: 60000 })
  },
  retry: (id, version) => request(`${batchPath(id)}/retry`, {
    method: 'POST', data: { version: positiveInteger(version) }
  }),
  reclassify: (id, version, material_type) => request(`${batchPath(id)}/reclassify`, {
    method: 'POST', data: { version: positiveInteger(version), material_type }
  }),
  submit: (id, version, item_ids) => request(`${batchPath(id)}/submit`, {
    method: 'POST', data: {
      version: positiveInteger(version),
      ...(item_ids === undefined ? {} : { item_ids: item_ids.map(positiveInteger) })
    }
  }),
  // data 包含 version/status/reviewComment/items，分数由后端计算。
  review: (id, data) => request(`${batchPath(id)}/review`, {
    method: 'POST', data: { ...data, version: positiveInteger(data.version) }
  })
}

export default volunteerApi
