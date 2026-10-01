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

import cases from './__fixtures__/name-cases.json'
import { displayNameError, validateDisplayName, validatePersonName } from './validation'

describe('validatePersonName', () => {
  it.each(cases.person.valid)('accepts %j and tidies it to %j', (input, tidy) => {
    expect(validatePersonName(input)).toBe(tidy)
  })

  it.each(cases.person.invalid)('rejects %j', (input) => {
    expect(() => validatePersonName(input)).toThrow()
  })

  it('rejects a name past the length limit and says so', () => {
    expect(() => validatePersonName('a b'.repeat(40))).toThrow(/too long/)
    expect(() => validatePersonName('Ab'.repeat(cases.person.too_long))).toThrow(/too long/)
  })

  it('gives each kind of mistake its own sentence', () => {
    expect(() => validatePersonName('')).toThrow('Enter your name.')
    expect(() => validatePersonName('123')).toThrow("A name can't contain numbers.")
    expect(() => validatePersonName('A')).toThrow(/too short/)
    expect(() => validatePersonName('John!')).toThrow(/letters, spaces, hyphens and apostrophes/)
    expect(() => validatePersonName('-John')).toThrow(/valid name/)
  })
})

describe('validateDisplayName', () => {
  it.each(cases.display.valid)('accepts %j and tidies it to %j', (input, tidy) => {
    expect(validateDisplayName(input)).toBe(tidy)
  })

  it.each(cases.display.invalid)('rejects %j', (input) => {
    expect(() => validateDisplayName(input)).toThrow()
  })

  it('names the field in its messages', () => {
    expect(displayNameError('', 'company name')).toBe('Enter a company name.')
    expect(displayNameError('123', 'assistant name')).toMatch(/assistant name needs at least one letter/)
    expect(displayNameError('Acme')).toBeUndefined()
  })

  it('enforces the length a caller asks for', () => {
    expect(displayNameError('A'.repeat(51), 'assistant name', 50)).toMatch(/too long/)
    expect(displayNameError('A'.repeat(50), 'assistant name', 50)).toBeUndefined()
  })
})
