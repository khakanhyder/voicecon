import { test, expect } from '../support/mocks'
import { enterDashboard, signIn } from '../support/session'
import { ROUTES } from '../support/routes'
import { TEST_USER } from '../support/data'

/**
 * A name field only takes a name.
 *
 * "123" and "!!!" used to go straight through registration, the profile and
 * onboarding and became the account's name (or the first agent's). Each page now
 * says what is wrong under the field, and nothing is sent until it is fixed.
 * The rules are shared with the API: see lib/validation.ts.
 */

const profile = {
  ...TEST_USER, company_name: null, phone_number: null, bio: null, avatar_url: null,
  timezone: 'UTC', language: 'en', is_active: true, has_password: true,
}

test('sign-up: a number is not a name, and the message appears as soon as they leave the field', async ({ page }) => {
  await page.goto('/register')
  const name = page.getByLabel('Your Name')

  await name.fill('123')
  await name.blur()
  await expect(page.getByText("A name can't contain numbers.")).toBeVisible()

  await name.fill('!!!')
  await name.blur()
  await expect(page.getByText('That name is too short. Enter at least 2 letters.')).toBeVisible()

  await name.fill("Mary-Jane O'Brien")
  await name.blur()
  await expect(page.getByRole('alert').filter({ hasText: /name/i })).toHaveCount(0)
})

test('sign-up: continuing is refused until the name is real', async ({ page }) => {
  await page.goto('/register')
  await page.getByLabel('Your Name').fill('John2')
  // The verification step comes first, so this is the form's own submit guard.
  await page.getByRole('button', { name: /create account|sign up|register/i }).first().click()
  await expect(page.getByText("A name can't contain numbers.")).toBeVisible()
})

test('profile: saving is blocked on a bad name and nothing is sent', async ({ page, api }) => {
  await enterDashboard(page, api, '/dashboard/settings/profile', { user: profile })
  const name = page.getByLabel('Full Name')
  await expect(name).toHaveValue(TEST_USER.full_name)

  await name.fill('Sara 99')
  await page.getByRole('button', { name: /save/i }).first().click()

  await expect(page.getByText("A name can't contain numbers.")).toBeVisible()
  await expect(name).toBeFocused()
  expect(api.callsOf('PUT', '/users/me').concat(api.callsOf('PATCH', '/users/me'))).toHaveLength(0)
})

test('onboarding: company and assistant names need to be names', async ({ page, api }) => {
  await api.on(ROUTES.me, { body: TEST_USER })
  await api.on('**/api/v1/onboarding/status', {
    body: { onboarding_completed: false, step: 'company', has_company_profile: false, has_subscription: false, company: null },
  })
  await api.on('**/api/v1/onboarding/company', { body: {} }, { method: 'POST' })
  await signIn(page)
  await page.goto('/onboarding/company')
  await expect(page.getByRole('heading', { name: 'Company Information' })).toBeVisible({ timeout: 30_000 })

  await page.getByLabel('Company Name').fill('123')
  await page.getByLabel('Assistant Name').fill('!!!')
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(page.getByText('The company name needs at least one letter.')).toBeVisible()
  await expect(page.getByText('The assistant name needs at least one letter.')).toBeVisible()
  expect(api.callsOf('POST', '/onboarding/company')).toHaveLength(0)

  // Digits are fine when a letter comes with them, and the tidied value is what is sent.
  await page.getByLabel('Company Name').fill('  3M   Health ')
  await page.getByLabel('Assistant Name').fill('Aria')
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect.poll(() => api.callsOf('POST', '/onboarding/company').length).toBe(1)
  expect(api.callsOf('POST', '/onboarding/company')[0].body).toMatchObject({
    company_name: '3M Health',
    assistant_name: 'Aria',
  })
})
