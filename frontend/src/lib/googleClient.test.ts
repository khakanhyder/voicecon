import { describe, expect, it } from 'vitest'
import { resolveGoogleClientId } from './googleClient'

const BUILD = 'build-time.apps.googleusercontent.com'
const SERVER = 'server.apps.googleusercontent.com'

describe('resolveGoogleClientId', () => {
  it('uses the client the backend redeems codes with, not the build-time one', () => {
    expect(resolveGoogleClientId({ google: true, google_client_id: SERVER }, BUILD)).toBe(SERVER)
  })

  it('falls back to the build-time id when the backend did not answer', () => {
    expect(resolveGoogleClientId(undefined, BUILD)).toBe(BUILD)
  })

  it('falls back to the build-time id for a backend that does not report one', () => {
    expect(resolveGoogleClientId({ google: true }, BUILD)).toBe(BUILD)
  })

  it('turns Google off when the backend has it unconfigured', () => {
    expect(resolveGoogleClientId({ google: false, google_client_id: null }, BUILD)).toBe('')
  })
})
