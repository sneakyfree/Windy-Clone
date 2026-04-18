import { describe, it, expect } from 'vitest'
import { parseWindyCloneUrl, sanitizeCloneId } from './parseWindyCloneUrl'

describe('parseWindyCloneUrl', () => {
  it('maps dashboard to /legacy', () => {
    expect(parseWindyCloneUrl('windyclone://dashboard')).toEqual({
      route: '/legacy',
      params: {},
    })
  })

  it('maps discover to /discover', () => {
    expect(parseWindyCloneUrl('windyclone://discover')).toEqual({
      route: '/discover',
      params: {},
    })
  })

  it('maps studio/{cloneId} with allowed characters', () => {
    expect(parseWindyCloneUrl('windyclone://studio/abc-123_DEF')).toEqual({
      route: '/studio/clone/abc-123_DEF',
      params: { cloneId: 'abc-123_DEF' },
    })
  })

  it('maps order/{orderId}', () => {
    expect(parseWindyCloneUrl('windyclone://order/ord_42')).toEqual({
      route: '/order/ord_42',
      params: { orderId: 'ord_42' },
    })
  })

  it('normalises scheme and head to lowercase', () => {
    expect(parseWindyCloneUrl('WINDYCLONE://Dashboard')?.route).toBe('/legacy')
  })

  it('strips trailing query string before matching', () => {
    expect(parseWindyCloneUrl('windyclone://order/ok?ref=sms')?.route).toBe('/order/ok')
  })

  it.each([
    ['non-string', 42 as unknown],
    ['empty', ''],
    ['wrong scheme', 'windypro://dashboard'],
    ['http scheme', 'http://example.com/dashboard'],
    ['no target', 'windyclone://'],
    ['unknown head', 'windyclone://unknown'],
    ['extra segments on dashboard', 'windyclone://dashboard/extra'],
    ['studio without id', 'windyclone://studio'],
    ['path traversal', 'windyclone://studio/../../etc/passwd'],
    ['url-encoded slash is rejected', 'windyclone://studio/a%2Fb'],
    ['whitespace id', 'windyclone://order/bad id'],
    ['special char id', 'windyclone://order/bad!id'],
    ['oversized id', 'windyclone://order/' + 'a'.repeat(200)],
    ['multi-segment id', 'windyclone://order/a/b'],
  ])('rejects %s', (_label, input) => {
    expect(parseWindyCloneUrl(input)).toBeNull()
  })
})

describe('sanitizeCloneId', () => {
  it('accepts alphanum + dash + underscore', () => {
    expect(sanitizeCloneId('abc-123_DEF')).toBe('abc-123_DEF')
  })

  it.each([
    '',
    '   ',
    'a/b',
    'a\\b',
    '..',
    'has space',
    'dot.dot',
    'a'.repeat(200),
  ])('rejects %s', (input) => {
    expect(sanitizeCloneId(input)).toBeNull()
  })
})
