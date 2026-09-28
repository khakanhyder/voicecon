import type { Page } from '@playwright/test'
import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'
import { TEST_USER } from '../support/data'

/**
 * Settings → Profile → changing the account email.
 *
 * The address must not change until the code sent to the new one has been
 * accepted, so these follow what the page sends and what it shows at each step.
 */

const NEW_EMAIL = 'new.address@example.com'
const PASSWORD = 'Correct-horse-42'
const REQUEST = /\/api\/v1\/users\/me\/email\/change-request$/
const CONFIRM = /\/api\/v1\/users\/me\/email\/change-confirm$/

const profile = (overrides: Record<string, unknown> = {}) => ({
  ...TEST_USER,
  company_name: null,
  phone_number: null,
  bio: null,
  avatar_url: null,
  timezone: 'UTC',
  language: 'en',
  is_active: true,
  has_password: true,
  ...overrides,
})

async function openDialog(page: Page, api: any, user = profile()) {
  await enterDashboard(page, api, '/dashboard/settings/profile', { user })
  await expect(page.getByLabel('Email', { exact: true })).toHaveValue(TEST_USER.email)
  await page.getByRole('button', { name: 'Change', exact: true }).click()
  return page.getByRole('dialog')
}

async function typeCode(page: Page, code: string) {
  await page.getByRole('dialog').getByRole('textbox').first().click()
  await page.keyboard.type(code)
}

test.describe('Change email', () => {
  test('changes the address only after the code is confirmed', async ({ page, api }) => {
    await api.on(REQUEST, { body: { message: 'sent', expires_in_minutes: 10, debug_code: null } })
    await api.on(CONFIRM, {
      body: {
        access_token: 'rotated-access-token',
        refresh_token: 'rotated-refresh-token',
        token_type: 'bearer',
        user: { ...TEST_USER, email: NEW_EMAIL },
      },
    })
    const dialog = await openDialog(page, api)

    await expect(dialog.getByText(TEST_USER.email)).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Send code' })).toBeDisabled()
    await dialog.getByLabel(/New email/).fill(NEW_EMAIL)
    await dialog.getByLabel(/Your password/).fill(PASSWORD)
    await dialog.getByRole('button', { name: 'Send code' }).click()

    // Waiting on the code: the account still has its old address.
    await expect(dialog.getByText('Your email address has not changed yet.')).toBeVisible()
    await expect(dialog.getByText(NEW_EMAIL)).toBeVisible()
    const [asked] = api.callsOf('POST', '/users/me/email/change-request')
    expect(asked.body).toEqual({ new_email: NEW_EMAIL, current_password: PASSWORD })
    expect(api.callsOf('POST', '/users/me/email/change-confirm')).toHaveLength(0)

    // From here the profile reads back the new address.
    await api.on(ROUTES.me, { body: profile({ email: NEW_EMAIL }) })
    await typeCode(page, '482913')

    await expect(dialog).toBeHidden()
    await expect(page.getByText(`Your email address is now ${NEW_EMAIL}`)).toBeVisible()
    await expect(page.getByLabel('Email', { exact: true })).toHaveValue(NEW_EMAIL)
    const [confirmed] = api.callsOf('POST', '/users/me/email/change-confirm')
    expect(confirmed.body).toEqual({ new_email: NEW_EMAIL, code: '482913' })

    // The session carries on with the tokens the server issued in exchange.
    const stored = await page.evaluate(() => ({
      access: localStorage.getItem('access_token'),
      refresh: localStorage.getItem('refresh_token'),
      workspace: localStorage.getItem('active_organization_id'),
    }))
    expect(stored.access).toBe('rotated-access-token')
    expect(stored.refresh).toBe('rotated-refresh-token')
    expect(stored.workspace).not.toBeNull()
  })

  test('a wrong code is explained and changes nothing', async ({ page, api }) => {
    await api.on(REQUEST, { body: { message: 'sent', expires_in_minutes: 10, debug_code: null } })
    await api.on(CONFIRM, { status: 400, body: { detail: 'That code is not correct. 4 attempts left.' } })
    const dialog = await openDialog(page, api)

    await dialog.getByLabel(/New email/).fill(NEW_EMAIL)
    await dialog.getByLabel(/Your password/).fill(PASSWORD)
    await dialog.getByRole('button', { name: 'Send code' }).click()
    await typeCode(page, '000000')

    await expect(dialog.getByRole('alert')).toContainText('That code is not correct. 4 attempts left.')
    await expect(dialog).toBeVisible()
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByLabel('Email', { exact: true })).toHaveValue(TEST_USER.email)
    expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBe('test-access-token')
  })

  test('an address another account uses is refused before any code is sent', async ({ page, api }) => {
    await api.on(REQUEST, {
      status: 409,
      body: { detail: 'That email address is already used by another account.' },
    })
    const dialog = await openDialog(page, api)

    await dialog.getByLabel(/New email/).fill(NEW_EMAIL)
    await dialog.getByLabel(/Your password/).fill(PASSWORD)
    await dialog.getByRole('button', { name: 'Send code' }).click()

    await expect(dialog.getByRole('alert')).toContainText('already used by another account')
    await expect(dialog.getByLabel(/New email/)).toHaveValue(NEW_EMAIL)
    await expect(dialog.getByText('Check your new inbox')).toHaveCount(0)
  })

  test('the current address cannot be chosen', async ({ page, api }) => {
    const dialog = await openDialog(page, api)

    await dialog.getByLabel(/New email/).fill(TEST_USER.email.toUpperCase())
    await dialog.getByLabel(/Your password/).fill(PASSWORD)

    await expect(dialog.getByText('That is already your email address.')).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Send code' })).toBeDisabled()
  })

  test('a new code can be asked for once the wait is over', async ({ page, api }) => {
    await api.on(REQUEST, { body: { message: 'sent', expires_in_minutes: 10, debug_code: null } })
    await page.clock.install()
    const dialog = await openDialog(page, api)

    await dialog.getByLabel(/New email/).fill(NEW_EMAIL)
    await dialog.getByLabel(/Your password/).fill(PASSWORD)
    await dialog.getByRole('button', { name: 'Send code' }).click()

    await expect(dialog.getByRole('button', { name: /Resend in \d+s/ })).toBeDisabled()
    await page.clock.runFor(61_000)
    await dialog.getByRole('button', { name: 'Send a new code' }).click()

    await expect(dialog.getByRole('status')).toContainText('The earlier one no longer works')
    expect(api.callsOf('POST', '/users/me/email/change-request')).toHaveLength(2)
  })

  test('cancelling while waiting for the code changes nothing', async ({ page, api }) => {
    await api.on(REQUEST, { body: { message: 'sent', expires_in_minutes: 10, debug_code: null } })
    const dialog = await openDialog(page, api)

    await dialog.getByLabel(/New email/).fill(NEW_EMAIL)
    await dialog.getByLabel(/Your password/).fill(PASSWORD)
    await dialog.getByRole('button', { name: 'Send code' }).click()
    await dialog.getByRole('button', { name: 'Cancel' }).click()

    await expect(dialog).toBeHidden()
    await expect(page.getByLabel('Email', { exact: true })).toHaveValue(TEST_USER.email)
    expect(api.callsOf('POST', '/users/me/email/change-confirm')).toHaveLength(0)
  })

  test('an account without a password is not asked for one', async ({ page, api }) => {
    await api.on(REQUEST, { body: { message: 'sent', expires_in_minutes: 10, debug_code: null } })
    const dialog = await openDialog(page, api, profile({ has_password: false }))

    await expect(dialog.getByLabel(/Your password/)).toHaveCount(0)
    await dialog.getByLabel(/New email/).fill(NEW_EMAIL)
    await dialog.getByRole('button', { name: 'Send code' }).click()

    await expect(dialog.getByText('Your email address has not changed yet.')).toBeVisible()
    const [asked] = api.callsOf('POST', '/users/me/email/change-request')
    expect(asked.body).toEqual({ new_email: NEW_EMAIL })
  })
})
