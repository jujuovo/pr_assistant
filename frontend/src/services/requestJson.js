// JSON / multipart 请求：保留 HTTP 状态及业务错误，不自动重试写操作。
export async function requestJson(path, { method = 'GET', data, signal, timeoutMs = 30000 } = {}) {
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
    const response = await fetch(path, {
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
      error.code = payload?.code
      throw error
    }
    return payload
  } catch (error) {
    if (timedOut) {
      const timeout = new Error('请求超时；请先查询服务端状态，勿重复上传或提交')
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


export function positiveInteger(value) {
  if (!Number.isSafeInteger(value) || value <= 0) throw new TypeError("ID 和版本必须为正整数")
  return value
}
