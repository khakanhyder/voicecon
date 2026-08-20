import { describe, expect, it } from 'vitest'
import { isPlausiblePhoneNumber, normalizeWebsiteUrl } from './validation'

describe('normalizeWebsiteUrl', () => {
  it('treats empty input as "not provided"', () => {
    expect(normalizeWebsiteUrl('')).toBeNull()
    expect(normalizeWebsiteUrl('   ')).toBeNull()
  })

  it('accepts what people actually type and adds a scheme', () => {
    expect(normalizeWebsiteUrl('acme.com')).toBe('https://acme.com')
    expect(normalizeWebsiteUrl('www.acme.com')).toBe('https://www.acme.com')
    expect(normalizeWebsiteUrl('  Acme.COM  ')).toBe('https://acme.com')
  })

  it('keeps an explicit scheme, path, and query', () => {
    expect(normalizeWebsiteUrl('http://acme.com')).toBe('http://acme.com')
    expect(normalizeWebsiteUrl('https://acme.com/careers')).toBe('https://acme.com/careers')
    expect(normalizeWebsiteUrl('https://acme.co.uk/a?b=1')).toBe('https://acme.co.uk/a?b=1')
  })

  it('rejects a bare word — the bug this was written for', () => {
    expect(() => normalizeWebsiteUrl('dcsdcs')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('localhost')).toThrow(/valid website/)
  })

  it('rejects malformed hosts', () => {
    expect(() => normalizeWebsiteUrl('acme.')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('.com')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('acme..com')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('acme.c')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('acme.123')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('acme .com')).toThrow(/without spaces/)
  })

  it('refuses any scheme that is not http(s)', () => {
    expect(() => normalizeWebsiteUrl('javascript://acme.com')).toThrow(/http/)
    expect(() => normalizeWebsiteUrl('ftp://acme.com')).toThrow(/http/)
  })
})

describe('isPlausiblePhoneNumber', () => {
  it('accepts formatted real numbers', () => {
    expect(isPlausiblePhoneNumber('(301) 798 1897')).toBe(true)
    expect(isPlausiblePhoneNumber('301-798-1897')).toBe(true)
  })

  it('rejects lengths no subscriber number has', () => {
    expect(isPlausiblePhoneNumber('123')).toBe(false)
    expect(isPlausiblePhoneNumber('12345678901234567')).toBe(false)
    expect(isPlausiblePhoneNumber('abc')).toBe(false)
  })
})
