/**
 * Helpers that talk to a real backend. Used only by the `e2e` project.
 *
 * Registration normally requires a code emailed to the address
 * (REQUIRE_EMAIL_VERIFICATION=true). In local dev with no mail transport the
 * send-code endpoint returns the code as `debug_code`, which lets a test create
 * its own verified user with no fixture account to maintain.
 */
import type { APIRequestContext } from '@playwright/test'

export const API_URL = process.env.API_URL ?? 'http://localhost:8001'

export interface TestAccount {
  email: string
  password: string
  full_name: string
}

/**
 * A fresh address per run, so reruns never collide on the unique email index.
 *
 * The domain is deliberately `example.com`: it is IANA-reserved and can never
 * receive mail, yet it still passes the backend's `email-validator` check.
 * `.test`, `.invalid` and `.localhost` all *look* safer but are special-use
 * names that the validator rejects outright with a 422.
 */
export function uniqueEmail(prefix = 'qa'): string {
  return `${prefix}+${Date.now()}.${Math.floor(Math.random() * 1e6)}@example.com`
}

export async function createVerifiedAccount(
  request: APIRequestContext,
  overrides: Partial<TestAccount> = {},
): Promise<TestAccount> {
  const account: TestAccount = {
    email: overrides.email ?? uniqueEmail(),
    password: overrides.password ?? 'qa-password-123',
    full_name: overrides.full_name ?? 'QA Bot',
  }

  const sent = await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
    data: { email: account.email, purpose: 'signup' },
  })
  if (!sent.ok()) {
    throw new Error(`send-code failed (${sent.status()}): ${await sent.text()}`)
  }

  const { debug_code: code } = await sent.json()
  if (!code) {
    throw new Error(
      'send-code returned no debug_code, so tests cannot read the verification ' +
        'code. The backend only exposes it when DEBUG is on AND no real mail ' +
        'transport is configured. backend/.env ships real SMTP credentials, so ' +
        'start the test backend with EMAIL_PROVIDER=console:\n\n' +
        '  EMAIL_PROVIDER=console ./venv/bin/python -m uvicorn app.main:app --port 8001\n\n' +
        'That also stops the suite emailing real people on every run.',
    )
  }

  const verified = await request.post(`${API_URL}/api/v1/auth/email/verify-code`, {
    data: { email: account.email, code },
  })
  if (!verified.ok()) {
    throw new Error(`verify-code failed (${verified.status()}): ${await verified.text()}`)
  }
  const { email_verification_token } = await verified.json()

  const registered = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: { ...account, email_verification_token },
  })
  if (!registered.ok()) {
    throw new Error(`register failed (${registered.status()}): ${await registered.text()}`)
  }

  return account
}

export interface Session {
  account: TestAccount
  access_token: string
  refresh_token: string
  user: { id: string; email: string; full_name: string | null; is_verified: boolean }
}

/** Log in an existing account and return its live tokens. */
export async function login(
  request: APIRequestContext,
  account: Pick<TestAccount, 'email' | 'password'>,
): Promise<Session> {
  const res = await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: account.email, password: account.password },
  })
  if (!res.ok()) {
    throw new Error(`login failed (${res.status()}): ${await res.text()}`)
  }
  const body = await res.json()
  return { account: account as TestAccount, ...body }
}

/** Create a brand-new verified account and sign straight into it. */
export async function createSession(
  request: APIRequestContext,
  overrides: Partial<TestAccount> = {},
): Promise<Session> {
  const account = await createVerifiedAccount(request, overrides)
  return { ...(await login(request, account)), account }
}

/** Bearer header for an authenticated call. */
export function auth(session: Session) {
  return { Authorization: `Bearer ${session.access_token}` }
}

/**
 * Delete an agent, ignoring the outcome.
 *
 * Used in cleanup: a test that already failed should report its own reason, not
 * be buried under a teardown error.
 */
export async function deleteAgentQuietly(
  request: APIRequestContext,
  session: Session,
  agentId: string,
) {
  try {
    await request.delete(`${API_URL}/api/v1/agents/${agentId}`, { headers: auth(session) })
  } catch {
    // Best effort — the account is disposable anyway.
  }
}

/**
 * Start the card-free trial for the session's workspace.
 *
 * Registration creates an owner workspace but **no** subscription: entitlements
 * come back `expired`, and every write endpoint guarded by `require_entitlement`
 * answers 402. So a fresh account cannot create an agent until this runs.
 *
 * The trial grants `agents: 1` — deliberately, so the plan-limit path is
 * reachable by creating a second one.
 */
export async function startTrial(request: APIRequestContext, session: Session) {
  const res = await request.post(`${API_URL}/api/v1/billing/trial`, {
    headers: auth(session),
    data: { billing_period: 'monthly' },
  })
  if (!res.ok()) {
    throw new Error(`starting the trial failed (${res.status()}): ${await res.text()}`)
  }
  return res.json()
}

/** A verified account, signed in, with a live trial — ready to create things. */
export async function createTrialSession(
  request: APIRequestContext,
  overrides: Partial<TestAccount> = {},
): Promise<Session> {
  const session = await createSession(request, overrides)
  await startTrial(request, session)
  return session
}
