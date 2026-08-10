/**
 * Auth contract, driven directly against FastAPI.
 *
 * The mocked UI tests assume these shapes; if this file goes red, those mocks
 * are lying and their green is worthless.
 */
import { test, expect } from '@playwright/test'
import { API_URL, createSession, createVerifiedAccount, login, uniqueEmail } from '../support/api'

test.describe('Auth API', () => {
  test('login returns the token pair and user the frontend stores', async ({ request }) => {
    const account = await createVerifiedAccount(request)

    const res = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: account.email, password: account.password },
    })

    expect(res.status()).toBe(200)
    const body = await res.json()
    // Exactly the fields lib/auth.ts writes to localStorage. A rename here
    // logs every user out on deploy.
    expect(body).toMatchObject({
      token_type: 'bearer',
      user: { email: account.email, is_verified: true },
    })
    expect(typeof body.access_token).toBe('string')
    expect(typeof body.refresh_token).toBe('string')
    // The password must never come back on any response.
    expect(JSON.stringify(body)).not.toContain(account.password)
  })

  test('a wrong password is rejected with the same message as a missing account', async ({
    request,
  }) => {
    const account = await createVerifiedAccount(request)

    const wrongPassword = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: account.email, password: 'not-the-password' },
    })
    const noSuchUser = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: uniqueEmail('ghost'), password: 'not-the-password' },
    })

    expect(wrongPassword.status()).toBe(401)
    expect(noSuchUser.status()).toBe(401)
    // Differing responses turn the login form into an account enumeration oracle.
    expect((await wrongPassword.json()).detail).toBe((await noSuchUser.json()).detail)
  })

  test('registration is refused without proof of the email address', async ({ request }) => {
    const res = await request.post(`${API_URL}/api/v1/auth/register`, {
      data: { email: uniqueEmail('unverified'), password: 'qa-password-123', full_name: 'No Token' },
    })

    expect(res.status()).toBe(400)
    expect((await res.json()).detail).toContain('verify your email')
  })

  test('an email address cannot be registered twice', async ({ request }) => {
    const account = await createVerifiedAccount(request)

    const res = await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
      data: { email: account.email, purpose: 'signup' },
    })

    expect(res.status()).toBe(400)
    expect((await res.json()).detail).toMatch(/already registered/i)
  })

  test('a malformed payload is a 422, not a 500', async ({ request }) => {
    const res = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: 'not-an-email-address' },
    })

    // Pydantic validation, so the client can tell "you sent junk" from
    // "the server broke".
    expect(res.status()).toBe(422)
  })

  test('a refresh token buys a fresh access token', async ({ request }) => {
    const session = await createSession(request)

    const res = await request.post(`${API_URL}/api/v1/auth/refresh`, {
      data: { refresh_token: session.refresh_token },
    })

    expect(res.status()).toBe(200)
    // This is the silent-renewal path in lib/api.ts:40 — if the shape drifts,
    // every user is logged out the moment their access token expires.
    expect(typeof (await res.json()).access_token).toBe('string')
  })

  test('a garbage refresh token is rejected', async ({ request }) => {
    const res = await request.post(`${API_URL}/api/v1/auth/refresh`, {
      data: { refresh_token: 'not.a.real.token' },
    })

    expect(res.status()).toBe(401)
  })

  test('an access token is not accepted as a refresh token', async ({ request }) => {
    const session = await createSession(request)

    // Token types must be distinguishable, or a leaked short-lived access token
    // can be traded for indefinite access.
    const res = await request.post(`${API_URL}/api/v1/auth/refresh`, {
      data: { refresh_token: session.access_token },
    })

    expect(res.status()).toBe(401)
  })

  test('protected endpoints reject a missing or forged bearer token', async ({ request }) => {
    const anonymous = await request.get(`${API_URL}/api/v1/users/me`)
    expect(anonymous.status()).toBe(401)

    const forged = await request.get(`${API_URL}/api/v1/users/me`, {
      headers: { Authorization: 'Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature' },
    })
    expect(forged.status()).toBe(401)
  })

  test('a valid token identifies the right user', async ({ request }) => {
    const session = await createSession(request)

    const res = await request.get(`${API_URL}/api/v1/users/me`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })

    expect(res.status()).toBe(200)
    expect(await res.json()).toMatchObject({ email: session.account.email })
  })

  test('a verification code cannot be reused for a second account', async ({ request }) => {
    const email = uniqueEmail('replay')
    const sent = await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
      data: { email, purpose: 'signup' },
    })
    const { debug_code: code } = await sent.json()
    test.skip(!code, 'Backend has a real mail transport; the code is not readable here.')

    const first = await request.post(`${API_URL}/api/v1/auth/email/verify-code`, {
      data: { email, code },
    })
    expect(first.status()).toBe(200)

    // One-time means one time — otherwise a code intercepted once grants
    // repeated proof of ownership.
    const second = await request.post(`${API_URL}/api/v1/auth/email/verify-code`, {
      data: { email, code },
    })
    expect(second.status()).toBe(400)
  })

  test('an incorrect code is refused', async ({ request }) => {
    const email = uniqueEmail('badcode')
    await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
      data: { email, purpose: 'signup' },
    })

    const res = await request.post(`${API_URL}/api/v1/auth/email/verify-code`, {
      data: { email, code: '000000' },
    })

    expect(res.status()).toBe(400)
  })

  test('logout is accepted for a live session', async ({ request }) => {
    const session = await createSession(request)

    const res = await request.post(`${API_URL}/api/v1/auth/logout`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      data: {},
    })

    expect(res.ok()).toBeTruthy()
  })

  test('a second login for the same account still works', async ({ request }) => {
    // Guards against a session model that invalidates on re-login and breaks
    // people signed in on two devices.
    const account = await createVerifiedAccount(request)
    await login(request, account)
    const second = await login(request, account)

    expect(typeof second.access_token).toBe('string')
  })
})

/**
 * Regressions found during the systematic QA pass.
 *
 * Each of these reproduced a real defect against the running backend before the
 * corresponding fix landed. They are grouped separately so it stays obvious
 * what they are protecting.
 */
test.describe('Auth API — regressions', () => {
  test('an address can be signed in with whatever casing the user types', async ({ request }) => {
    // Registration stores the address normalized (lowercased), so a login that
    // compared the raw input rejected the *exact* address the account was
    // created with. Anyone whose keyboard autocapitalises — every phone — hit
    // this on their first sign-in attempt.
    const mixedCase = `QaCase.${Date.now()}.${Math.floor(Math.random() * 1e6)}@Example.com`
    const account = await createVerifiedAccount(request, { email: mixedCase })

    for (const attempt of [mixedCase, mixedCase.toLowerCase(), mixedCase.toUpperCase()]) {
      const res = await request.post(`${API_URL}/api/v1/auth/login`, {
        data: { email: attempt, password: account.password },
      })
      expect(res.status(), `login with ${attempt}`).toBe(200)
    }
  })

  test('surrounding whitespace does not lock a user out', async ({ request }) => {
    const account = await createVerifiedAccount(request)

    const res = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: `  ${account.email}  `, password: account.password },
    })

    expect(res.status()).toBe(200)
  })

  test('the wrong password is still refused after normalization', async ({ request }) => {
    // The lookup was loosened to normalize the address; make sure that did not
    // loosen the credential check with it.
    const account = await createVerifiedAccount(request)

    const res = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: account.email.toUpperCase(), password: 'definitely-not-it' },
    })

    expect(res.status()).toBe(401)
  })

  test('two people whose addresses share a local part can both sign up', async ({ request }) => {
    // The personal workspace's slug was taken straight from the local part of
    // the address, and Organization.slug is UNIQUE. alice@one.com registering
    // meant alice@two.com got a 500 and simply could not create an account —
    // and the common local parts (info@, hello@, admin@, sales@) are exactly
    // the ones a B2B signup form sees most.
    const localPart = `shared${Date.now()}.${Math.floor(Math.random() * 1e6)}`

    const first = await createVerifiedAccount(request, { email: `${localPart}@example.com` })
    expect(first.email).toContain(localPart)

    const second = await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
      data: { email: `${localPart}@example.org`, purpose: 'signup' },
    })
    const { debug_code: code } = await second.json()
    test.skip(!code, 'Backend has a real mail transport; the code is not readable here.')

    const verified = await request.post(`${API_URL}/api/v1/auth/email/verify-code`, {
      data: { email: `${localPart}@example.org`, code },
    })
    const { email_verification_token } = await verified.json()

    const registered = await request.post(`${API_URL}/api/v1/auth/register`, {
      data: {
        email: `${localPart}@example.org`,
        password: 'qa-password-123',
        full_name: 'Second Namesake',
        email_verification_token,
      },
    })

    expect(registered.status(), await registered.text()).toBe(201)
  })
})

/**
 * Password reset — the whole flow was previously untested, despite being the
 * one path that hands out a session to someone who cannot produce a password.
 */
test.describe('Auth API — password reset', () => {
  /** Ask for a reset code and return it, skipping if mail delivery is live. */
  async function requestResetCode(request: import('@playwright/test').APIRequestContext, email: string) {
    const res = await request.post(`${API_URL}/api/v1/auth/password/forgot`, { data: { email } })
    expect(res.status()).toBe(200)
    const { debug_code } = await res.json()
    return debug_code as string | null
  }

  test('a reset code lets the user set a new password and signs them in', async ({ request }) => {
    const account = await createVerifiedAccount(request)
    const code = await requestResetCode(request, account.email)
    test.skip(!code, 'Backend has a real mail transport; the code is not readable here.')

    const newPassword = 'a-brand-new-password-456'
    const reset = await request.post(`${API_URL}/api/v1/auth/password/reset`, {
      data: { email: account.email, code, new_password: newPassword },
    })

    expect(reset.status()).toBe(200)
    // The flow signs the user straight in, so it must return a usable session.
    const body = await reset.json()
    expect(typeof body.access_token).toBe('string')
    expect(JSON.stringify(body)).not.toContain(newPassword)

    // The new password works...
    const withNew = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: account.email, password: newPassword },
    })
    expect(withNew.status()).toBe(200)

    // ...and the old one is dead. A reset that leaves the previous password
    // valid does not lock out whoever the account was stolen from.
    const withOld = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: account.email, password: account.password },
    })
    expect(withOld.status()).toBe(401)
  })

  test('a reset code is single-use', async ({ request }) => {
    const account = await createVerifiedAccount(request)
    const code = await requestResetCode(request, account.email)
    test.skip(!code, 'Backend has a real mail transport; the code is not readable here.')

    const first = await request.post(`${API_URL}/api/v1/auth/password/reset`, {
      data: { email: account.email, code, new_password: 'first-new-password-1' },
    })
    expect(first.status()).toBe(200)

    const replay = await request.post(`${API_URL}/api/v1/auth/password/reset`, {
      data: { email: account.email, code, new_password: 'attacker-chosen-pass-1' },
    })
    expect(replay.status()).toBe(400)
  })

  test('a wrong reset code cannot change the password', async ({ request }) => {
    const account = await createVerifiedAccount(request)
    await requestResetCode(request, account.email)

    const res = await request.post(`${API_URL}/api/v1/auth/password/reset`, {
      data: { email: account.email, code: '000000', new_password: 'attacker-chosen-pass-1' },
    })
    expect(res.status()).toBe(400)

    // The original password must still be the one that works.
    const stillOld = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: account.email, password: account.password },
    })
    expect(stillOld.status()).toBe(200)
  })

  test('forgot-password does not reveal whether an address has an account', async ({ request }) => {
    const account = await createVerifiedAccount(request)

    const known = await request.post(`${API_URL}/api/v1/auth/password/forgot`, {
      data: { email: account.email },
    })
    const unknown = await request.post(`${API_URL}/api/v1/auth/password/forgot`, {
      data: { email: uniqueEmail('nobody') },
    })

    expect(known.status()).toBe(unknown.status())
    // Same status *and* same wording — a different message is the same leak.
    expect((await known.json()).message).toBe((await unknown.json()).message)
  })

  test('a signup code cannot be spent as a password reset', async ({ request }) => {
    // Codes are HMACed with their purpose precisely so one flow's proof cannot
    // be replayed into another. This is the test that says so.
    const email = uniqueEmail('crosspurpose')
    const sent = await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
      data: { email, purpose: 'signup' },
    })
    const { debug_code: signupCode } = await sent.json()
    test.skip(!signupCode, 'Backend has a real mail transport; the code is not readable here.')

    const res = await request.post(`${API_URL}/api/v1/auth/password/reset`, {
      data: { email, code: signupCode, new_password: 'attacker-chosen-pass-1' },
    })

    expect(res.status()).toBe(400)
  })

  test('send-code refuses to issue reset codes, which would leak account existence', async ({
    request,
  }) => {
    const res = await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
      data: { email: uniqueEmail('viasendcode'), purpose: 'password_reset' },
    })

    // /email/send-code 400s on a registered address, so honouring
    // purpose=password_reset there would turn it into an enumeration oracle.
    expect(res.status()).toBe(400)
  })

  test('a password shorter than the minimum is rejected on reset', async ({ request }) => {
    const account = await createVerifiedAccount(request)
    const code = await requestResetCode(request, account.email)
    test.skip(!code, 'Backend has a real mail transport; the code is not readable here.')

    const res = await request.post(`${API_URL}/api/v1/auth/password/reset`, {
      data: { email: account.email, code, new_password: 'short' },
    })

    expect(res.status()).toBe(422)
  })
})

/**
 * Throttling.
 *
 * The rate-limit middleware existed in the tree but was never installed, so the
 * API shipped with none of this: 50 consecutive failed logins were answered 401
 * fifty times, as fast as they could be sent.
 */
test.describe('Auth API — throttling', () => {
  test('guessing one account’s password gets locked out', async ({ request }) => {
    const account = await createVerifiedAccount(request)

    const codes: number[] = []
    for (let i = 0; i < 8; i++) {
      const res = await request.post(`${API_URL}/api/v1/auth/login`, {
        data: { email: account.email, password: `guess-number-${i}` },
      })
      codes.push(res.status())
    }

    // Wrong first, then cut off — rather than an unlimited run of 401s.
    expect(codes.slice(0, 5)).toEqual([401, 401, 401, 401, 401])
    expect(codes.at(-1)).toBe(429)
  })

  test('a lockout is confined to the address being guessed', async ({ request }) => {
    // Keyed per account precisely so one person under attack cannot take
    // everyone behind the same office IP down with them.
    const victim = await createVerifiedAccount(request)
    const bystander = await createVerifiedAccount(request)

    for (let i = 0; i < 8; i++) {
      await request.post(`${API_URL}/api/v1/auth/login`, {
        data: { email: victim.email, password: `guess-number-${i}` },
      })
    }

    const res = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: bystander.email, password: bystander.password },
    })
    expect(res.status()).toBe(200)
  })

  test('signing in successfully clears the failure count', async ({ request }) => {
    // Someone who fat-fingers their password twice and then gets it right must
    // not be one typo away from a lockout for the next fifteen minutes.
    const account = await createVerifiedAccount(request)

    for (let i = 0; i < 4; i++) {
      await request.post(`${API_URL}/api/v1/auth/login`, {
        data: { email: account.email, password: `typo-${i}` },
      })
    }

    const good = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: account.email, password: account.password },
    })
    expect(good.status()).toBe(200)

    // Four more failures must again be merely wrong, not locked out.
    for (let i = 0; i < 4; i++) {
      const res = await request.post(`${API_URL}/api/v1/auth/login`, {
        data: { email: account.email, password: `typo-again-${i}` },
      })
      expect(res.status(), `failure ${i + 1} after a success`).toBe(401)
    }
  })

  test('a lockout is not an account-existence oracle', async ({ request }) => {
    // Failures are counted for unregistered addresses too. If they were not,
    // "401 forever" vs "429 after five" would tell an attacker which addresses
    // have accounts — the exact leak the matching 401 bodies exist to prevent.
    const ghost = uniqueEmail('ghost')

    const codes: number[] = []
    for (let i = 0; i < 8; i++) {
      const res = await request.post(`${API_URL}/api/v1/auth/login`, {
        data: { email: ghost, password: `guess-number-${i}` },
      })
      codes.push(res.status())
    }

    expect(codes.at(-1)).toBe(429)
  })

  test('responses advertise the caller’s remaining budget', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/v1/auth/providers`)

    expect(res.status()).toBe(200)
    const headers = res.headers()
    expect(headers['x-ratelimit-limit']).toBeDefined()
    expect(headers['x-ratelimit-remaining']).toBeDefined()
    // Enforcement and the headers must read the same table. They used to be two
    // separate functions that disagreed, so the advertised budget was fiction.
    expect(Number(headers['x-ratelimit-remaining'])).toBeLessThanOrEqual(
      Number(headers['x-ratelimit-limit']),
    )
  })

  test('provider webhooks are never throttled', async ({ request }) => {
    // Twilio POSTs the voice and status callbacks on every call, from its own
    // egress IPs, unauthenticated — so the limiter could only key them by an
    // address shared across every customer on the platform. A 60/min write
    // ceiling there is not a safety net, it is a cap on concurrent calls, and
    // exceeding it drops live ones. Stripe and inbound workflow webhooks are
    // exempt for the same reason; each authenticates itself instead.
    const machinePaths = [
      '/api/v1/telephony/twilio/status',
      '/api/v1/billing/webhooks/stripe',
    ]

    for (const path of machinePaths) {
      const res = await request.post(`${API_URL}${path}`, { data: {} })
      // The body is junk, so the endpoint itself will reject it — the point is
      // only that the limiter did not claim a budget for the caller.
      expect(res.headers()['x-ratelimit-limit'], `${path} must not be throttled`).toBeUndefined()
    }
  })

  test('walking ids does not buy a fresh allowance per id', async ({ request }) => {
    // Buckets are keyed by route shape, not by resolved URL. Keying by URL gave
    // /agents/{id} its own budget per id, so enumeration — the one pattern a
    // scraping limit exists to catch — was effectively unthrottled.
    const session = await createSession(request)

    const first = await request.get(
      `${API_URL}/api/v1/agents/00000000-0000-0000-0000-000000000001`,
      { headers: { Authorization: `Bearer ${session.access_token}` } },
    )
    const second = await request.get(
      `${API_URL}/api/v1/agents/00000000-0000-0000-0000-000000000002`,
      { headers: { Authorization: `Bearer ${session.access_token}` } },
    )

    const remainingAfterFirst = Number(first.headers()['x-ratelimit-remaining'])
    const remainingAfterSecond = Number(second.headers()['x-ratelimit-remaining'])
    // Two different ids, one budget — so the second call must have cost one.
    expect(remainingAfterSecond).toBeLessThan(remainingAfterFirst)
  })

  test('health checks are never throttled', async ({ request }) => {
    // The platform decides whether to keep the container by polling this. Rate
    // limiting it turns a traffic spike into a restart loop.
    for (let i = 0; i < 30; i++) {
      const res = await request.get(`${API_URL}/health`)
      expect(res.status()).toBe(200)
    }
  })
})

/**
 * Sign-up validation.
 *
 * The API is the gate: the form's own checks are a courtesy, and anything that
 * reaches this endpoint by other means — a stale build, a script, a curl — gets
 * exactly the same treatment.
 */
test.describe('Auth API — signup validation', () => {
  /** A verified address, ready to be registered with whatever payload. */
  async function verifiedEmail(request: import('@playwright/test').APIRequestContext) {
    const email = uniqueEmail('validation')
    const sent = await request.post(`${API_URL}/api/v1/auth/email/send-code`, {
      data: { email, purpose: 'signup' },
    })
    const { debug_code: code } = await sent.json()
    test.skip(!code, 'Backend has a real mail transport; the code is not readable here.')
    const verified = await request.post(`${API_URL}/api/v1/auth/email/verify-code`, {
      data: { email, code },
    })
    return { email, token: (await verified.json()).email_verification_token }
  }

  /** Register with `overrides` merged over a payload that would otherwise pass. */
  async function register(
    request: import('@playwright/test').APIRequestContext,
    overrides: Record<string, unknown> = {},
  ) {
    const { email, token } = await verifiedEmail(request)
    return request.post(`${API_URL}/api/v1/auth/register`, {
      data: {
        email,
        password: 'correct-horse-battery',
        full_name: 'Ada Lovelace',
        email_verification_token: token,
        ...overrides,
      },
    })
  }

  test('an account cannot be created without a name', async ({ request }) => {
    // `full_name` was Optional and the form did not mark it required, so a
    // nameless account was reachable from the product itself — and then showed
    // as a blank row in the team list and every invitation it sent.
    const res = await register(request, { full_name: undefined })

    expect(res.status()).toBe(422)
  })

  test.describe('names that are not names', () => {
    const rejected: Array<[string, string]> = [
      ['empty', ''],
      ['only whitespace', '   '],
      ['a single character', 'a'],
      ['digits only', '123'],
      ['punctuation only', '...'],
      ['longer than the column', 'A'.repeat(500)],
    ]

    for (const [label, full_name] of rejected) {
      test(`rejects a name that is ${label}`, async ({ request }) => {
        const res = await register(request, { full_name })
        // 500 characters used to overflow the 255-char column and surface as a
        // 500 — a crash where a validation message belonged.
        expect(res.status()).toBe(422)
      })
    }
  })

  test('accepts a real name, stored trimmed', async ({ request }) => {
    const res = await register(request, { full_name: '  Ada Lovelace  ' })

    expect(res.status()).toBe(201)
    expect((await res.json()).user.full_name).toBe('Ada Lovelace')
  })

  test('accepts a name in a non-Latin script', async ({ request }) => {
    // The letter check uses Unicode-aware `isalpha`, not `[A-Za-z]`, so this
    // must not be collateral damage from rejecting "123".
    const res = await register(request, { full_name: 'Зоя Мюллер' })

    expect(res.status()).toBe(201)
  })

  test.describe('passwords', () => {
    const rejected: Array<[string, string]> = [
      ['shorter than the minimum', 'Sh0rt!x'],
      ['one of the most common ones', 'password'],
      ['a run of digits', '12345678'],
      ['the same character repeated', 'aaaaaaaa'],
      // bcrypt reads 72 bytes and ignores the rest, so anything longer would
      // be silently truncated — two different passwords authenticating each
      // other. Refused instead of quietly trimmed.
      ['longer than bcrypt can read', 'A'.repeat(400)],
    ]

    for (const [label, password] of rejected) {
      test(`rejects a password that is ${label}`, async ({ request }) => {
        const res = await register(request, { password })
        expect(res.status()).toBe(422)
      })
    }

    test('rejects a password that is just the user’s own address', async ({ request }) => {
      const { email, token } = await verifiedEmail(request)

      const res = await request.post(`${API_URL}/api/v1/auth/register`, {
        data: {
          email,
          password: email.split('@')[0],
          full_name: 'Ada Lovelace',
          email_verification_token: token,
        },
      })

      expect(res.status()).toBe(422)
    })

    test('accepts a long passphrase with no symbols or digits', async ({ request }) => {
      // The policy is length-and-blocklist based, not composition based, so a
      // passphrase — which is genuinely stronger than "Passw0rd!" — must pass.
      const res = await register(request, { password: 'correct horse battery staple' })

      expect(res.status()).toBe(201)
    })
  })

  test('rejects a phone number that cannot be dialled', async ({ request }) => {
    const res = await register(request, { phone_number: 'not-a-phone!!' })

    expect(res.status()).toBe(422)
  })

  test('accepts a phone number as the country picker formats it', async ({ request }) => {
    // The form submits `${dialCode} ${number}`, so spaces and a leading + are
    // the normal shape and must not be rejected.
    const res = await register(request, { phone_number: '+1 555 010 1234' })

    expect(res.status()).toBe(201)
  })

  test('rejects a company name that is only whitespace', async ({ request }) => {
    const res = await register(request, { company_name: '   ' })

    expect(res.status()).toBe(422)
  })

  test('a rejection says what is wrong in a sentence', async ({ request }) => {
    // The frontend surfaces `details[0].msg` to the user, so it has to read as
    // something a person can act on — not a regex or a field path.
    const res = await register(request, { password: 'password' })
    const body = await res.json()

    const message = String(body.details?.[0]?.msg ?? '')
    expect(message).toMatch(/commonly used/i)
    expect(message).not.toMatch(/pattern|regex|\^|\$/)
  })

  test('the password policy also guards the reset flow', async ({ request }) => {
    // Otherwise "forgot password" is a way to set a password that sign-up
    // would have refused.
    const account = await createVerifiedAccount(request)
    const forgot = await request.post(`${API_URL}/api/v1/auth/password/forgot`, {
      data: { email: account.email },
    })
    const { debug_code: code } = await forgot.json()
    test.skip(!code, 'Backend has a real mail transport; the code is not readable here.')

    const res = await request.post(`${API_URL}/api/v1/auth/password/reset`, {
      data: { email: account.email, code, new_password: 'password' },
    })

    expect(res.status()).toBe(422)
  })
})
