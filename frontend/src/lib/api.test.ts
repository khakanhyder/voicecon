import { describe, expect, it } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { GENERIC_ERROR, getErrorMessage, looksTechnical, publicErrorText } from './api'

function axiosError(status?: number, data?: unknown, code = 'ERR'): AxiosError {
  const config = { headers: new AxiosHeaders() }
  const response = status === undefined
    ? undefined
    : { status, statusText: '', headers: {}, config, data }
  return new AxiosError(`Request failed with status code ${status}`, code, config, null, response as never)
}

describe('getErrorMessage', () => {
  it('shows a sentence the API wrote for a 4xx', () => {
    expect(getErrorMessage(axiosError(400, { detail: 'Agent name is required' }))).toBe('Agent name is required')
    expect(getErrorMessage(axiosError(401, { detail: 'Incorrect email or password' }))).toBe('Incorrect email or password')
  })

  it('reads the first validation message without the pydantic prefix', () => {
    const err = axiosError(422, { message: 'Request validation failed', details: [{ msg: 'Value error, Password is too short' }] })
    expect(getErrorMessage(err)).toBe('Password is too short')
  })

  it('never shows a 500 body, even a dev-mode exception string', () => {
    const err = axiosError(500, { error: 'InternalServerError', message: "'NoneType' object has no attribute 'id'" })
    expect(getErrorMessage(err)).toBe('Something went wrong on our side. Please try again in a moment.')
    expect(getErrorMessage(err, 'Could not save the agent')).toBe('Could not save the agent')
  })

  it('shows a worded 503 but not a technical one', () => {
    expect(getErrorMessage(axiosError(503, { detail: 'Our payment provider could not complete this request.' })))
      .toBe('Our payment provider could not complete this request.')
    expect(getErrorMessage(axiosError(503, { detail: "HTTPSConnectionPool(host='api.twilio.com'): Max retries exceeded" })))
      .toBe('Something went wrong on our side. Please try again in a moment.')
  })

  it('hides provider text inside a 4xx', () => {
    const err = axiosError(400, { detail: "Client error '401 Unauthorized' for url 'https://api.hubapi.com/x'" })
    expect(getErrorMessage(err, 'Could not connect HubSpot')).toBe('Could not connect HubSpot')
  })

  it('uses a status message when the body has nothing usable', () => {
    expect(getErrorMessage(axiosError(403, {}))).toBe('You don’t have permission to do that in this workspace.')
    expect(getErrorMessage(axiosError(429, '<html>rate limited</html>'))).toBe('Too many attempts. Please wait a moment and try again.')
  })

  it('explains network failures and timeouts instead of "Network Error"', () => {
    expect(getErrorMessage(axiosError())).toMatch(/couldn’t reach Voicecon/)
    expect(getErrorMessage(axiosError(undefined, undefined, 'ECONNABORTED'))).toMatch(/longer than expected/)
  })

  it('filters plain Error messages too', () => {
    expect(getErrorMessage(new Error('Please choose a plan first'))).toBe('Please choose a plan first')
    expect(getErrorMessage(new TypeError("Cannot read properties of undefined (reading 'id')"))).toBe(GENERIC_ERROR)
    expect(getErrorMessage(new TypeError('Failed to fetch'), 'Offline')).toBe('Offline')
    expect(getErrorMessage('boom')).toBe(GENERIC_ERROR)
  })
})

describe('looksTechnical / publicErrorText', () => {
  it('passes written sentences and rejects dumps', () => {
    expect(looksTechnical('Slack channel not found. Pick another channel.')).toBe(false)
    expect(looksTechnical('{"error":"x"}')).toBe(true)
    expect(looksTechnical('x'.repeat(300))).toBe(true)
    expect(publicErrorText('KeyError: \'email\'', 'This step failed.')).toBe('This step failed.')
    expect(publicErrorText(null, 'This step failed.')).toBe('This step failed.')
  })
})
