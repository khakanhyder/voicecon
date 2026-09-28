import { describe, expect, it, vi } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { formatMonthly, formatPhoneNumber, friendlyPhoneError, validateSearch } from './phoneNumbers'

function axiosError(status?: number, data?: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() }
  const response = status === undefined
    ? undefined
    : { status, statusText: '', headers: {}, config, data }
  return new AxiosError(`Request failed with status code ${status}`, 'ERR', config, null, response as never)
}

describe('friendlyPhoneError', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})

  it('shows a detail the API wrote for users', () => {
    const err = axiosError(400, { detail: 'US and Canadian area codes are 3 digits, for example 415.' })
    expect(friendlyPhoneError(err, 'search')).toBe('US and Canadian area codes are 3 digits, for example 415.')
  })

  it('never shows a server error, whatever its body says', () => {
    const err = axiosError(500, { detail: 'psycopg2.OperationalError: connection to server at 10.0.0.5 failed' })
    expect(friendlyPhoneError(err, 'search')).toBe('We couldn’t load available numbers right now. Please try again.')
    expect(friendlyPhoneError(err, 'purchase')).toBe('Unable to complete the purchase. Please try again or contact support.')
  })

  it('never shows a validation payload', () => {
    const err = axiosError(422, { detail: [{ loc: ['body', 'agent_id'], msg: 'value is not a valid uuid' }] })
    expect(friendlyPhoneError(err, 'purchase')).toBe('Unable to complete the purchase. Please try again or contact support.')
  })

  it('never shows a proxy HTML page', () => {
    const err = axiosError(503, { detail: '<html><body>502 Bad Gateway nginx</body></html>' })
    expect(friendlyPhoneError(err, 'search')).toMatch(/couldn’t load available numbers/)
  })

  it('explains a network failure instead of "Network Error"', () => {
    expect(friendlyPhoneError(axiosError(undefined), 'search')).toMatch(/internet connection/)
  })

  it('handles non-HTTP errors', () => {
    expect(friendlyPhoneError(new TypeError("Cannot read properties of undefined (reading 'data')"), 'purchase'))
      .toBe('Unable to complete the purchase. Please try again or contact support.')
  })
})

describe('formatting', () => {
  it('formats North American numbers', () => {
    expect(formatPhoneNumber('+14155550100')).toBe('+1 (415) 555-0100')
  })

  it('leaves other countries readable', () => {
    expect(formatPhoneNumber('+442071838750')).toMatch(/^\+44 /)
  })

  it('formats monthly prices', () => {
    expect(formatMonthly(1.15, 'USD')).toBe('$1.15/mo')
    expect(formatMonthly(null)).toBeNull()
  })
})

describe('validateSearch', () => {
  it('requires 3-digit US area codes', () => {
    expect(validateSearch('US', '41', '')).toMatch(/3 digits/)
    expect(validateSearch('US', '415', '')).toBeNull()
  })

  it('requires digits in "contains"', () => {
    expect(validateSearch('US', '', 'abc')).toMatch(/digits only/)
    expect(validateSearch('GB', '20', '55*')).toBeNull()
  })
})
