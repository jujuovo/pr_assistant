import { afterEach, describe, expect, it, vi } from 'vitest'

import { randomUuid } from '@/utils/uuid.js'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('randomUuid', () => {
  it('uses the browser implementation when available', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'native-uuid' })
    expect(randomUuid()).toBe('native-uuid')
  })

  it('generates a UUID v4 without crypto.randomUUID', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes) => bytes.fill(0),
    })
    expect(randomUuid()).toBe('00000000-0000-4000-8000-000000000000')
  })

  it('still returns a UUID v4 when Web Crypto is unavailable', () => {
    vi.stubGlobal('crypto', undefined)
    expect(randomUuid()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })
})
