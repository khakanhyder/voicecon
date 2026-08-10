import { test, expect } from '../support/mocks'
import { signIn } from '../support/session'

/**
 * The landing page is the only thing an anonymous visitor sees, and both of its
 * conversion paths (Login, Get Started) are the entrance to every other flow in
 * the product. A broken link here costs every signup.
 *
 * It also doubles as a router: an authenticated visitor is bounced to the
 * analytics dashboard instead (app/page.tsx:15).
 */
test.describe('Landing page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('renders the hero, not an error boundary or an empty shell', async ({ page }) => {
    await expect(
      page.getByRole('heading', { name: /Voice AI meets/i, level: 1 }),
    ).toBeVisible()
    await expect(page.getByText(/Create, deploy, and manage AI voice agents/i)).toBeVisible()
  })

  test('offers both conversion paths and points them at real routes', async ({ page }) => {
    // Scoped to the header nav: "Login" and "Get Started" also appear in the
    // hero, and an unscoped locator would resolve to two elements in strict mode.
    const nav = page.getByRole('navigation')
    await expect(nav.getByRole('link', { name: 'Login' })).toHaveAttribute('href', '/login')
    await expect(nav.getByRole('link', { name: 'Get Started' })).toHaveAttribute(
      'href',
      '/register',
    )
  })

  test('the primary call to action reaches the register form', async ({ page }) => {
    const cta = page.getByRole('link', { name: 'Start Building Free' })
    await expect(cta).toBeVisible()
    await cta.click()

    await expect(page).toHaveURL(/\/register$/)
    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeVisible()
  })

  test('the secondary call to action reaches the login form', async ({ page }) => {
    const cta = page.getByRole('link', { name: 'View Demo' })
    await expect(cta).toBeVisible()
    await cta.click()

    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('button', { name: 'Login Now' })).toBeVisible()
  })

  test('lists what the product does', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Platform Features' })).toBeVisible()
    for (const feature of ['Voice AI Agents', '500+ Integrations', 'No-Code Workflows']) {
      await expect(page.getByRole('heading', { name: feature })).toBeVisible()
    }
  })

  test('never calls the API — the page must render for a logged-out stranger', async ({
    page,
    api,
  }) => {
    // A public page that needs a token renders blank for exactly the audience
    // it is meant to convert.
    expect(api.calls).toHaveLength(0)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })

  test('bounces an authenticated visitor to their dashboard', async ({ page, api }) => {
    await api.installAppShell()
    await signIn(page)

    await page.goto('/')

    await expect(page).toHaveURL(/\/dashboard\/analytics/)
  })
})
