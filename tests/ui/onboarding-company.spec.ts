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
    phone_number: '+13017981897',
  })
  // No number search, no purchase: the carrier account is never involved.
  expect(api.callsTo('/phone-numbers')).toHaveLength(0)
  expect(api.callsTo('/onboarding/phone-number')).toHaveLength(0)
})

/**
 * The website is optional, but what is typed has to be a real one. "as.asdfdsf"
 * used to save: it has a dot and ends in letters, which was all that was asked.
 * The form now knows which endings exist; whether the domain itself is
 * registered needs a DNS lookup, so that answer comes from the API and is shown
 * in the same place.
 */
test('the company website has to be a real domain', async ({ page, api }) => {
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
  await api.on(
    '**/api/v1/onboarding/company',
    {
      status: 422,
      body: {
        error: 'ValidationError',
        message: 'Request validation failed',
        details: [
          {
            type: 'value_error',
            loc: ['body', 'company_url'],
            msg: "We couldn't find that website. Check the address and try again.",
          },
        ],
      },
    },
    { method: 'POST' },
  )

  await signIn(page)
  await page.goto('/onboarding/company')
  await expect(page.getByRole('heading', { name: 'Company Information' })).toBeVisible({ timeout: 30_000 })

  const website = page.getByLabel(/Company URL/)
  await page.getByLabel('Company Name').fill('Acme Inc.')

  // An ending that is not a TLD is caught in the browser: nothing is sent.
  await website.fill('as.asdfdsf')
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByText('Enter a valid website, e.g. www.acme.com')).toBeVisible()
  expect(api.callsOf('POST', '/onboarding/company')).toHaveLength(0)

  // A well-formed domain nobody has registered is refused by the API, and the
  // reason lands under the field rather than in a toast.
  await website.fill('asdfqwe-not-registered.com')
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByText("We couldn't find that website. Check the address and try again.")).toBeVisible()
  await expect(website).toBeFocused()
  await expect(page).toHaveURL(/\/onboarding\/company/)
})
