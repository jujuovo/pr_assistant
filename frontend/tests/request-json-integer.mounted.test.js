import { describe, expect, it } from 'vitest'

import { positiveInteger } from '@/services/requestJson.js'

describe('positiveInteger', () => {
  it('accepts numeric route query parameters', () => {
    expect(positiveInteger('17')).toBe(17)
    expect(positiveInteger(17)).toBe(17)
  })

  it.each(['', '0', '-1', '1.5', '01', '1x', null, undefined])(
    'rejects a non-canonical positive integer: %s',
    (value) => {
      expect(() => positiveInteger(value)).toThrow('ID 和版本必须为正整数')
    }
  )
})
