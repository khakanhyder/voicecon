import { describe, expect, it } from 'vitest'
import { normalizeWebsiteUrl } from './validation'

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

  it('rejects an ending that is not a real top-level domain', () => {
    // Reported from onboarding: this saved as a company website.
    expect(() => normalizeWebsiteUrl('as.asdfdsf')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('https://www.acme.comm')).toThrow(/valid website/)
    expect(() => normalizeWebsiteUrl('acme.local')).toThrow(/valid website/)
  })

  it('accepts newer and country-code endings', () => {
    expect(normalizeWebsiteUrl('voicecon.ai')).toBe('https://voicecon.ai')
    expect(normalizeWebsiteUrl('acme.com.pk')).toBe('https://acme.com.pk')
    expect(normalizeWebsiteUrl('acme.technology')).toBe('https://acme.technology')
  })

  it('refuses any scheme that is not http(s)', () => {
    expect(() => normalizeWebsiteUrl('javascript://acme.com')).toThrow(/http/)
    expect(() => normalizeWebsiteUrl('ftp://acme.com')).toThrow(/http/)
  })
})
