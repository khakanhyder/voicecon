import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'

/**
 * The Phone Numbers empty state has two shapes. Before a provider is connected
 * it offers the two ways to get a number; once one is, it offers that account
 * instead — and connecting a provider from here has to come back here, or the
 * user is left on Integrations wondering where their numbers went.
 */

const SUPPORTED = [
  { slug: 'twilio', name: 'Twilio', description: 'Use numbers and calling on your own Twilio account.' },
  { slug: 'telnyx', name: 'Telnyx', description: 'Use numbers and calling on your own Telnyx account.' },
]

const TWILIO_ACCOUNT = {
  slug: 'twilio', name: 'Twilio', source: 'connection',
  connection_id: 'conn-1', connection_name: 'Twilio Connection', is_default: true,
}

const purchaseOptions = (connected: boolean) => ({
  voicecon_available: true,
  own_providers: connected ? [TWILIO_ACCOUNT] : [],
  supported_providers: SUPPORTED.map((p) => ({ ...p, connected: connected && p.slug === 'twilio' })),
})

test('offers both ways to get a number before a provider is connected', async ({ page, api }) => {
  await api.on(ROUTES.phoneNumberPurchaseOptions, { body: purchaseOptions(false) })
  await enterDashboard(page, api, '/dashboard/phone-numbers')

  await expect(page.getByRole('heading', { name: 'Buy a Voicecon number' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Use your own provider' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Use my numbers' })).toHaveCount(0)
})

test('offers the connected account instead of the two starting cards', async ({ page, api }) => {
  await api.on(ROUTES.phoneNumberPurchaseOptions, { body: purchaseOptions(true) })
  await enterDashboard(page, api, '/dashboard/phone-numbers')

  await expect(page.getByRole('heading', { name: 'Your provider is connected' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Use my numbers' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Buy new' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Buy a Voicecon number' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Use your own provider' })).toHaveCount(0)
  // The other routes stay reachable, just no longer the headline.
  await expect(page.getByRole('button', { name: 'Connect another provider' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Buy a Voicecon number instead' })).toBeVisible()
})

test('connecting a provider from Phone Numbers returns there with the account offered', async ({ page, api }) => {
  await api.on(ROUTES.phoneNumberPurchaseOptions, { body: purchaseOptions(false) })
  await api.on(ROUTES.integrationConnectors, {
    body: { connectors: [{ id: 'connector-1', slug: 'twilio', name: 'Twilio', auth_type: 'api_key' }], total: 1 },
  })
  await api.on(ROUTES.integrationConnections, { body: { connections: [] } })
  await api.on(ROUTES.integrationConnections, { body: { id: 'conn-1' } }, { method: 'POST' })
  await enterDashboard(page, api, '/dashboard/phone-numbers')

  await page.getByRole('button', { name: 'Connect a provider' }).click()
  await page.getByRole('link', { name: /Twilio/ }).click()
  await expect(page).toHaveURL(/\/dashboard\/integrations\/twilio\?from=phone-numbers$/, { timeout: 30_000 })
  await expect(page.getByRole('button', { name: 'Back to Phone Numbers' })).toBeVisible()

  await page.getByLabel(/Account SID/).fill('ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
  await page.getByLabel(/Auth Token/).fill('secret-token')
  // From here on the account exists, so the page must be told so on reload.
  await api.on(ROUTES.phoneNumberPurchaseOptions, { body: purchaseOptions(true) })
  await page.getByRole('button', { name: 'Connect Integration' }).click()

  await expect(page).toHaveURL(/\/dashboard\/phone-numbers$/, { timeout: 30_000 })
  await expect(page.getByRole('heading', { name: 'Your provider is connected' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Use my numbers' })).toBeVisible()
})

test('connecting a provider from Integrations stays on Integrations', async ({ page, api }) => {
  await api.on(ROUTES.integrationConnectors, {
    body: { connectors: [{ id: 'connector-1', slug: 'twilio', name: 'Twilio', auth_type: 'api_key' }], total: 1 },
  })
  await api.on(ROUTES.integrationConnections, { body: { connections: [] } })
  await api.on(ROUTES.integrationConnections, { body: { id: 'conn-1' } }, { method: 'POST' })
  // Staying put mounts the connection's defaults panel, which needs a real shape.
  await api.on(/\/api\/v1\/integrations\/connections\/conn-1\/defaults/, {
    body: { connector_name: 'Twilio', defaults: {}, asks: [], kinds: [] },
  })
  await enterDashboard(page, api, '/dashboard/integrations/twilio')

  await expect(page.getByRole('button', { name: 'Back to Integrations' })).toBeVisible()
  await page.getByLabel(/Account SID/).fill('ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
  await page.getByLabel(/Auth Token/).fill('secret-token')
  await page.getByRole('button', { name: 'Connect Integration' }).click()

  await expect(page.getByRole('heading', { name: 'Connection successful!' })).toBeVisible()
  await expect(page).toHaveURL(/\/dashboard\/integrations\/twilio$/)
})
