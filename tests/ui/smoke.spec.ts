import { test, expect } from '../support/mocks'

/**
 * Cheapest possible regression net: the public pages render their own content
 * rather than a Next error overlay or a blank shell.
 */
test.describe('Public pages', () => {
  test('the homepage renders', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL('/')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('the login page renders its form', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Login into your account' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Login Now' })).toBeVisible()
  })

  test('the register page renders its form', async ({ page }) => {
    await page.goto('/register')
    await expect(page.getByRole('button', { name: 'Sign up Now' })).toBeVisible()
  })
})
