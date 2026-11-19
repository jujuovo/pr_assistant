// @vitest-environment happy-dom
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  api: { sessionCheck: vi.fn(), getCurrentUser: vi.fn() }
}))

vi.mock('@/services/api.js', () => ({
  default: state.api,
  getFileFullUrl: (value) => value
}))

import { useAuthStore } from '../src/stores/auth.js'

const savedStudent = { username: 'student001', name: '演示同学', role: 'student' }

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  localStorage.setItem('user', JSON.stringify(savedStudent))
  setActivePinia(createPinia())
})

describe('auth bootstrap recovery', () => {
  it('preserves the local role when session check is unreachable', async () => {
    state.api.sessionCheck.mockRejectedValueOnce(
      Object.assign(new TypeError('Failed to fetch'), {
        status: undefined
      })
    )
    const auth = useAuthStore()
    await auth.initialize()

    expect(auth.isAuthenticated).toBe(true)
    expect(auth.role).toBe('student')
    expect(localStorage.getItem('user')).not.toBeNull()
  })

  it('clears local auth only for an explicit unauthorized response', async () => {
    state.api.sessionCheck.mockRejectedValueOnce(
      Object.assign(new Error('未登录'), { status: 401 })
    )
    const auth = useAuthStore()
    await auth.initialize()

    expect(auth.isAuthenticated).toBe(false)
    expect(auth.role).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })

  it('clears a successfully checked but expired session', async () => {
    state.api.sessionCheck.mockResolvedValueOnce({ logged_in: false })
    const auth = useAuthStore()
    await auth.initialize()

    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('user')).toBeNull()
  })
})
