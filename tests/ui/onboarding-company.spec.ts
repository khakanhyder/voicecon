import { test, expect } from '../support/mocks'
import { TEST_USER } from '../support/data'
import { ROUTES } from '../support/routes'
import { signIn } from '../support/session'

/**
 * Onboarding never sells a phone number.
 *
 * A number is a recurring charge at the carrier, and this screen comes before
 * the workspace has a plan. It used to offer a number search with a "Get this
 * number" button, which the API then refused. Numbers are bought on the Phone
 * Numbers page once there is a plan; here the field is a contact number only.
 */

test('the company step asks for a contact number and offers no number to buy', async ({ page, api }) => {
  await api.on(ROUTES.me, { body: TEST_USER })
  await api.on('**/api/v1/onboarding/status', {
    body: {
      onboarding_completed: false,
      step: 'company',
      has_company_profile: false,
      has_subscription: false,
      company: null,
    },
  })
  // Even when Voicecon numbers are on sale, this screen must not offer them.
  await api.on(ROUTES.phoneNumberPurchaseOptions, {
    body: { voicecon_available: true, own_providers: [], supported_providers: [] },
  })
  await api.on('**/api/v1/onboarding/company', { body: {} }, { method: 'POST' })

  await signIn(page)
  await page.goto('/onboarding/company')

  await expect(page.getByRole('heading', { name: 'Company Information' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByLabel(/Phone Number/)).toBeVisible()

  await expect(page.getByRole('button', { name: /Get a number/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Search' })).toHaveCount(0)
  await expect(page.getByText(/buys it right away/)).toHaveCount(0)

  // Filling in the form and continuing saves the profile and nothing else.
  await page.getByLabel('Company Name').fill('Acme Inc.')
  await page.getByLabel(/Phone Number/).fill('3017981897')
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect.poll(() => api.callsOf('POST', '/onboarding/company').length).toBe(1)

  expect(api.callsOf('POST', '/onboarding/company')[0].body).toMatchObject({
    company_name: 'Acme Inc.',
    phone_number: '+1 3017981897',
  })
  // No number search, no purchase: the carrier account is never involved.
  expect(api.callsTo('/phone-numbers')).toHaveLength(0)
  expect(api.callsTo('/onboarding/phone-number')).toHaveLength(0)
})
