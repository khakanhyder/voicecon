/**
 * Request to join the affiliate program, from the public form.
 *
 * A bare fetch (no auth interceptor): the form is on a marketing page for
 * anonymous visitors. Staff review the request in the admin console.
 */
import { API_BASE } from '@/lib/constants'

export interface AffiliateApplicationInput {
  name: string
  email: string
  company?: string
  website?: string
  message: string
  /** Honeypot. Left empty by people. */
  fax?: string
}

const GENERIC_ERROR = 'Something went wrong. Please try again.'

/** Sends the request and returns the confirmation message to show. */
export async function applyToAffiliateProgram(input: AffiliateApplicationInput): Promise<string> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/v1/affiliate-public/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    })
  } catch {
    throw new Error('Network error. Please check your connection and try again.')
  }

  let data: { message?: unknown; detail?: unknown } = {}
  try {
    data = await res.json()
  } catch {
    /* non-JSON response: fall through to status handling */
  }

  if (!res.ok) {
    if (res.status === 422) throw new Error('Please check the form and try again.')
    // Only a plain sentence from the server is shown; anything else is ours.
    const text = typeof data.detail === 'string' ? data.detail : typeof data.message === 'string' ? data.message : ''
    throw new Error(text || GENERIC_ERROR)
  }
  return typeof data.message === 'string' ? data.message : 'Thanks — your request is in.'
}
