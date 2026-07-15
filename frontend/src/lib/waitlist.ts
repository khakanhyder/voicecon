/**
 * Public waitlist sign-up. Talks to the backend, which forwards the email to
 * the Voicecon Mailchimp Audience. Uses a bare fetch (no auth interceptor) since
 * this runs on the public "Launching Soon" page for anonymous visitors.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface WaitlistResult {
  success: boolean
  message: string
}

export async function joinWaitlist(email: string): Promise<WaitlistResult> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/v1/waitlist/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
  } catch {
    throw new Error('Network error — please check your connection and try again.')
  }

  let data: Partial<WaitlistResult> & { detail?: string } = {}
  try {
    data = await res.json()
  } catch {
    /* non-JSON response — fall through to status handling */
  }

  if (!res.ok) {
    throw new Error(data.detail || 'Something went wrong. Please try again.')
  }

  return {
    success: data.success ?? true,
    message: data.message ?? "You're on the list!",
  }
}
