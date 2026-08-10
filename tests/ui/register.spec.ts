import type { Page } from '@playwright/test'
import { test, expect } from '../support/mocks'
import { fillOtp } from '../support/session'
import { ROUTES } from '../support/routes'
import {
  apiError,
  loginResponse,
  sendCodeResponse,
  TEST_PASSWORD,
  TEST_USER,
  VERIFICATION_TOKEN,
  verifyCodeResponse,
} from '../support/data'

/**
 * Sign-up is gated on proving the email address: the submit button stays
 * disabled until /auth/email/verify-code echoes back the address in the form
 * (frontend/src/app/(auth)/register/page.tsx:45,374).
 */
test.describe('Registration', () => {
  const NEW_EMAIL = 'new.user@voicecon.test'

  async function requestCode(page: Page, email = NEW_EMAIL) {
    await page.getByLabel('Email Id :').fill(email)
    await page.getByRole('button', { name: 'Verify', exact: true }).click()
  }

  /**
   * Filling the last box submits the code by itself (OtpInput's onComplete).
   * Waits for the verified state to land — the form silently refuses to submit
   * while the address is still unverified.
   */
  async function verifyEmail(page: Page, email = NEW_EMAIL) {
    await requestCode(page, email)
    await fillOtp(page, '123456')
    await expect(page.getByRole('button', { name: 'Verified' })).toBeVisible()
  }

  test.beforeEach(async ({ page, api }) => {
    await api.on('**/api/v1/auth/email/send-code', { body: sendCodeResponse() })
    await api.on('**/api/v1/auth/email/verify-code', { body: verifyCodeResponse(NEW_EMAIL) })
    await page.goto('/register')
  })

  test('keeps sign-up locked until the email is verified', async ({ page }) => {
    await page.getByLabel('Your Name').fill('New User')
    await page.getByLabel('Email Id :').fill(NEW_EMAIL)

    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeDisabled()
  })

  test('asks for a code, accepts it, and unlocks sign-up', async ({ page, api }) => {
    await verifyEmail(page)

    await expect(page.getByRole('button', { name: 'Verified' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeEnabled()
    expect(api.callsTo('/auth/email/send-code')[0].body).toMatchObject({
      email: NEW_EMAIL,
      purpose: 'signup',
    })
    expect(api.callsTo('/auth/email/verify-code')[0].body).toMatchObject({
      email: NEW_EMAIL,
      code: '123456',
    })
  })

  test('creates the account and continues into onboarding', async ({ page, api }) => {
    await api.on('**/api/v1/auth/register', { status: 201, body: { id: TEST_USER.id } })
    await api.on('**/api/v1/auth/login', { body: loginResponse() })

    await verifyEmail(page)
    await page.getByLabel('Your Name').fill('New User')
    await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD)
    await page.getByLabel('Confirm Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Sign up Now' }).click()

    await expect(page).toHaveURL(/\/onboarding\/company/)

    // The proof-of-email token must reach the backend, or sign-up is only
    // gated in the UI.
    expect(api.callsTo('/auth/register')[0].body).toMatchObject({
      email: NEW_EMAIL,
      email_verification_token: VERIFICATION_TOKEN,
    })
  })

  test('reports a rejected code without unlocking sign-up', async ({ page, api }) => {
    await api.on('**/api/v1/auth/email/verify-code', {
      status: 400,
      body: apiError('That code is incorrect or has expired'),
    })

    await requestCode(page)
    await fillOtp(page, '123456')

    await expect(page.getByText('That code is incorrect or has expired')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeDisabled()
  })

  test('refuses an address that already has an account', async ({ page, api }) => {
    await api.on('**/api/v1/auth/email/send-code', {
      status: 400,
      body: apiError('An account with this email already exists'),
    })

    await requestCode(page, TEST_USER.email)

    await expect(page.getByText('An account with this email already exists')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeDisabled()
  })

  test('re-locks sign-up if the address is changed after verifying', async ({ page }) => {
    await verifyEmail(page)
    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeEnabled()

    await page.getByRole('button', { name: 'Verified' }).click()
    await page.getByLabel('Email Id :').fill('someone.else@voicecon.test')

    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeDisabled()
  })

  test('pre-fills the code in dev mode, where the API returns it', async ({ page, api }) => {
    await api.on('**/api/v1/auth/email/send-code', {
      body: sendCodeResponse({ debug_code: '654321' }),
    })

    await requestCode(page)

    // register/page.tsx:88 drops the emailed code straight into the boxes so
    // local dev can skip the inbox round-trip.
    await expect(page.getByLabel('Digit 1')).toHaveValue('6')
    await expect(page.getByLabel('Digit 6')).toHaveValue('1')
    await expect(page.getByRole('button', { name: 'Verify email' })).toBeEnabled()
  })
})

/**
 * The name field. Required by the API, and now by the form — it used to be
 * neither, so a nameless account was reachable straight from the product.
 */
test.describe('Registration — the name is required', () => {
  const NEW_EMAIL = 'named.user@voicecon.test'

  test.beforeEach(async ({ page, api }) => {
    await api.on('**/api/v1/auth/email/send-code', { body: sendCodeResponse() })
    await api.on('**/api/v1/auth/email/verify-code', { body: verifyCodeResponse(NEW_EMAIL) })
    await api.on(ROUTES.register, { body: { message: 'ok', user: TEST_USER } })
    await api.on(ROUTES.login, { body: loginResponse() })
    await page.goto('/register')
  })

  /** Verify the address so the only thing standing in the way is the name. */
  async function verifyThenFillPasswords(page: Page) {
    await page.getByLabel('Email Id :').fill(NEW_EMAIL)
    await page.getByRole('button', { name: 'Verify', exact: true }).click()
    await fillOtp(page, '123456')
    await expect(page.getByRole('button', { name: 'Verified' })).toBeVisible()
    await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD)
    await page.getByLabel('Confirm Password').fill(TEST_PASSWORD)
  }

  test('refuses to submit with the name left empty', async ({ page, api }) => {
    await verifyThenFillPasswords(page)

    await page.getByRole('button', { name: 'Sign up Now' }).click()

    // An empty required field is caught by the browser's own constraint
    // validation, which blocks submission before any handler runs — so the
    // assertion is on the field being invalid and nothing being sent, not on
    // the app's message, which in this case never gets a chance to appear.
    await expect(page.getByLabel('Your Name')).toHaveJSProperty('validity.valid', false)
    // The point is that nothing was sent — a form that posts and lets the
    // server say no is a slower version of the same answer.
    expect(api.callsTo('/auth/register')).toHaveLength(0)
  })

  test('refuses a name that is only spaces', async ({ page, api }) => {
    await page.getByLabel('Your Name').fill('   ')
    await verifyThenFillPasswords(page)

    await page.getByRole('button', { name: 'Sign up Now' }).click()

    await expect(page.getByText('Please enter your name')).toBeVisible()
    expect(api.callsTo('/auth/register')).toHaveLength(0)
  })

  test('sends the name trimmed once it is filled in', async ({ page, api }) => {
    await page.getByLabel('Your Name').fill('  Ada Lovelace  ')
    await verifyThenFillPasswords(page)

    await page.getByRole('button', { name: 'Sign up Now' }).click()

    await expect.poll(() => api.callsTo('/auth/register').length).toBe(1)
    expect(api.callsTo('/auth/register')[0].body).toMatchObject({
      full_name: 'Ada Lovelace',
    })
  })
})

/**
 * The code arrives by email, so the realistic way a person enters it is to
 * select it in their inbox and paste — not to retype six digits.
 */
test.describe('Registration — entering the emailed code', () => {
  const NEW_EMAIL = 'paste.user@voicecon.test'

  test.beforeEach(async ({ page, api }) => {
    await api.on('**/api/v1/auth/email/send-code', { body: sendCodeResponse() })
    await api.on('**/api/v1/auth/email/verify-code', { body: verifyCodeResponse(NEW_EMAIL) })
    await page.goto('/register')
    await page.getByLabel('Email Id :').fill(NEW_EMAIL)
    await page.getByRole('button', { name: 'Verify', exact: true }).click()
  })

  /** Paste into a box the way the browser delivers a clipboard drop. */
  async function pasteCode(page: Page, text: string, intoDigit = 1) {
    const box = page.getByLabel(`Digit ${intoDigit}`)
    await box.click()
    await box.evaluate((el, value) => {
      const data = new DataTransfer()
      data.setData('text/plain', value)
      el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true }))
    }, text)
  }

  test('pasting spreads the digits across the boxes, not into the first', async ({ page }) => {
    // Five digits on purpose: a complete code fires onComplete, which verifies
    // and unmounts the boxes, so there would be nothing left to assert on.
    await pasteCode(page, '13579')

    for (const [i, digit] of [...'13579'].entries()) {
      await expect(page.getByLabel(`Digit ${i + 1}`), `box ${i + 1}`).toHaveValue(digit)
    }
    await expect(page.getByLabel('Digit 6')).toHaveValue('')
  })

  test('a pasted code submits itself, like typing the last digit does', async ({ page, api }) => {
    await pasteCode(page, '135790')

    await expect(page.getByRole('button', { name: 'Verified' })).toBeVisible()
    expect(api.callsTo('/auth/email/verify-code')[0].body).toMatchObject({ code: '135790' })
  })

  test('a code copied with surrounding text still lands cleanly', async ({ page, api }) => {
    // People select generously in an inbox — "Your code is 135-790" and stray
    // whitespace are what actually reaches the clipboard. Everything that is
    // not a digit has to be dropped, or the code is silently wrong.
    await pasteCode(page, '  Your code is 135-790  ')

    await expect(page.getByRole('button', { name: 'Verified' })).toBeVisible()
    expect(api.callsTo('/auth/email/verify-code')[0].body).toMatchObject({ code: '135790' })
  })

  test('pasting into a later box still reads as the whole code', async ({ page, api }) => {
    // Clicking box 3 before pasting is easy to do by accident; the pasted value
    // is still the whole code and must not be scattered from box 3 onwards.
    await pasteCode(page, '135790', 3)

    await expect(page.getByRole('button', { name: 'Verified' })).toBeVisible()
    expect(api.callsTo('/auth/email/verify-code')[0].body).toMatchObject({ code: '135790' })
  })
})
