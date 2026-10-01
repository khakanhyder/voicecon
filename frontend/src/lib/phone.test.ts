import { describe, expect, it } from 'vitest'
import {
  phoneCountries,
  phoneError,
  phoneFromStored,
  phoneToE164,
  sanitizePhoneInput,
} from './phone'

describe('sanitizePhoneInput', () => {
  it('drops letters and symbols but keeps phone punctuation', () => {
    expect(sanitizePhoneInput('(301) 798-1897abc!@#')).toBe('(301) 798-1897')
    expect(sanitizePhoneInput('+44 20.7946 0958')).toBe('44 20.7946 0958')
  })
})

describe('phoneToE164 / phoneError', () => {
  it('accepts real numbers and normalises them', () => {
    expect(phoneToE164({ country: 'PK', national: '0300 1234567' })).toBe('+923001234567')
    expect(phoneToE164({ country: 'GB', national: '020 7946 0958' })).toBe('+442079460958')
    expect(phoneToE164({ country: 'US', national: '(415) 555-2671' })).toBe('+14155552671')
  })
  it('rejects numbers no plan allows', () => {
    expect(phoneError({ country: 'US', national: '123' })).toBeTruthy()
    expect(phoneError({ country: 'US', national: '1111111111' })).toBeTruthy()
  })
  it('treats empty as fine when optional, an error when required', () => {
    expect(phoneError({ country: 'US', national: '  ' })).toBeUndefined()
    expect(phoneError({ country: 'US', national: '' }, true)).toBeTruthy()
  })
})

describe('phoneFromStored', () => {
  it('splits an E.164 number into country and national digits', () => {
    const v = phoneFromStored('+923001234567')
    expect(v.country).toBe('PK')
    expect(phoneToE164(v)).toBe('+923001234567')
  })
  it('handles empty', () => {
    expect(phoneFromStored(null).national).toBe('')
  })
})

describe('phoneCountries', () => {
  it('lists countries with + prefixed codes, A-Z', () => {
    const list = phoneCountries()
    expect(list.length).toBeGreaterThan(200)
    expect(list.find((c) => c.iso === 'PK')).toMatchObject({ name: 'Pakistan', dial: '+92' })
    expect(list.find((c) => c.iso === 'GB')?.dial).toBe('+44')
  })
})
