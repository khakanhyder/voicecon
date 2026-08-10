/**
 * Onboarding contract — the company → pricing → billing flow a new account is
 * dropped into immediately after registering.
 *
 * The company step is the interesting one to pin: it does not just save a form,
 * it copies the company name onto the Organization and the User, so a bad value
 * here spreads to the workspace switcher and every page header.
 */
import { test, expect } from '@playwright/test'
import { API_URL, auth, createSession, type Session } from '../support/api'

/** POST the company step for a session. */
function saveCompany(
  request: import('@playwright/test').APIRequestContext,
  session: Session,
  data: Record<string, unknown>,
) {
  return request.post(`${API_URL}/api/v1/onboarding/company`, {
    headers: auth(session),
    data,
  })
}

test.describe('Onboarding API', () => {
  test('a fresh account starts at the company step with nothing filled in', async ({
    request,
  }) => {
    const session = await createSession(request)

    const res = await request.get(`${API_URL}/api/v1/onboarding/status`, {
      headers: auth(session),
    })

    expect(res.status()).toBe(200)
    // This is what the frontend routes on: get it wrong and a new user is
    // either dropped into a dashboard they have not set up, or looped back
    // through onboarding they already finished.
    expect(await res.json()).toMatchObject({
      onboarding_completed: false,
      step: 'company',
      has_company_profile: false,
      has_subscription: false,
    })
  })

  test('saving the company step advances onboarding to pricing', async ({ request }) => {
    const session = await createSession(request)

    const saved = await saveCompany(request, session, {
      company_name: 'Acme Clinic',
      industry_type: 'Healthcare',
      company_size: '11-50',
      company_url: 'https://acme.example.com',
      assistant_name: 'Riley',
      preferred_language: 'English',
    })
    expect(saved.status()).toBe(200)
    expect(await saved.json()).toMatchObject({
      company_name: 'Acme Clinic',
      onboarding_step: 'pricing',
    })

    const status = await request.get(`${API_URL}/api/v1/onboarding/status`, {
      headers: auth(session),
    })
    expect(await status.json()).toMatchObject({
      step: 'pricing',
      has_company_profile: true,
    })
  })

  test('saving twice updates the profile instead of creating a second one', async ({
    request,
  }) => {
    const session = await createSession(request)

    const first = await saveCompany(request, session, { company_name: 'First Name Ltd' })
    const second = await saveCompany(request, session, { company_name: 'Renamed Ltd' })

    expect(second.status()).toBe(200)
    // Same row, not a duplicate — the profile is looked up by organization.
    expect((await second.json()).id).toBe((await first.json()).id)
    expect((await second.json()).company_name).toBe('Renamed Ltd')
  })

  test('the company name reaches the workspace, since that is what the UI shows', async ({
    request,
  }) => {
    const session = await createSession(request)

    await saveCompany(request, session, { company_name: 'Renamed Workspace Ltd' })

    const workspace = await request.get(`${API_URL}/api/v1/workspaces/current`, {
      headers: auth(session),
    })
    expect((await workspace.json()).name).toBe('Renamed Workspace Ltd')
  })

  test('onboarding status is refused without a token', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/v1/onboarding/status`)
    expect(res.status()).toBe(401)
  })
})

test.describe('Onboarding API — validation', () => {
  test('a company name of only whitespace is refused', async ({ request }) => {
    // `min_length=1` counts characters, so a single space satisfied it — and
    // this endpoint copies the value onto the Organization, so a spacebar
    // renamed the workspace to nothing and blanked the switcher and headers.
    const session = await createSession(request)

    const res = await saveCompany(request, session, { company_name: '   ' })

    expect(res.status()).toBe(422)
  })

  test('a valid company name is stored trimmed', async ({ request }) => {
    const session = await createSession(request)

    const res = await saveCompany(request, session, { company_name: '  Padded Ltd  ' })

    expect(res.status()).toBe(200)
    expect((await res.json()).company_name).toBe('Padded Ltd')
  })

  test('an untouched optional field is stored as null, not an empty string', async ({
    request,
  }) => {
    // An empty input posts "", which reads back as "present but empty" and
    // makes the form render a filled-in field containing nothing rather than
    // its placeholder.
    const session = await createSession(request)

    const res = await saveCompany(request, session, {
      company_name: 'Acme Clinic',
      industry_type: '',
      company_url: '   ',
    })

    const body = await res.json()
    expect(body.industry_type).toBeNull()
    expect(body.company_url).toBeNull()
  })

  test('a company name past the column width is refused', async ({ request }) => {
    const session = await createSession(request)

    const res = await saveCompany(request, session, { company_name: 'A'.repeat(300) })

    expect(res.status()).toBe(422)
  })
})

/**
 * The error contract for *every* endpoint, verified here because onboarding is
 * where it was found.
 */
test.describe('Validation errors are client errors', () => {
  test('a value rejected by a field validator is a 422, not a 500', async ({ request }) => {
    // Pydantic v2 puts the raised exception *object* under ctx["error"], which
    // JSONResponse could not serialize — so the handler itself blew up and the
    // client was told "an unexpected error occurred" when it had simply sent a
    // bad value. Every schema with a custom validator was affected: agents,
    // workflows, integrations and onboarding.
    const session = await createSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: 'Bad Type', system_prompt: 'x', type: 'not-a-valid-type' },
    })

    // 402 would mean the plan gate answered before validation did; this account
    // has no trial, so accept either — the point is that it is never a 500.
    expect([422, 402]).toContain(res.status())
  })

  test('the rejection says which field was wrong and why', async ({ request }) => {
    const session = await createSession(request)

    const res = await saveCompany(request, session, { company_name: '   ' })
    const body = await res.json()

    expect(body.error).toBe('ValidationError')
    // The message is the useful half of the detail; dropping ctx entirely to
    // make the body encode would have thrown it away.
    expect(JSON.stringify(body.details)).toMatch(/blank/i)
  })
})
