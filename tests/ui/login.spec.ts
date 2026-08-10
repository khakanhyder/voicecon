import { test, expect } from '../support/mocks'
import { apiError, loginResponse, TEST_PASSWORD, TEST_USER } from '../support/data'

test.describe('Login', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('signs in and lands on the dashboard', async ({ page, api }) => {
    await api.on('**/api/v1/auth/login', { body: loginResponse() })

    await page.getByLabel('Email Id :').fill(TEST_USER.email)
    await page.getByLabel('Password:', { exact: true }).fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Login Now' }).click()

    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('sends the typed credentials to the API', async ({ page, api }) => {
    await api.on('**/api/v1/auth/login', { body: loginResponse() })

    await page.getByLabel('Email Id :').fill(TEST_USER.email)
    await page.getByLabel('Password:', { exact: true }).fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Login Now' }).click()
    await expect(page).toHaveURL(/\/dashboard/)

    // Guards against the form posting stale state or the wrong field order.
    expect(api.callsTo('/auth/login')[0].body).toEqual({
      email: TEST_USER.email,
      password: TEST_PASSWORD,
    })
  })

  test('persists the tokens that authorise every later request', async ({ page, api }) => {
    await api.on('**/api/v1/auth/login', { body: loginResponse() })
    // The dashboard refetches the profile on arrival and rewrites the cached
    // `user` entry, so this has to return the real shape (frontend/src/lib/auth.ts:135).
    await api.on('**/api/v1/users/me', { body: TEST_USER })

    await page.getByLabel('Email Id :').fill(TEST_USER.email)
    await page.getByLabel('Password:', { exact: true }).fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Login Now' }).click()
    await expect(page).toHaveURL(/\/dashboard/)

    // The app reads these back from localStorage on every request and on reload
    // (frontend/src/lib/auth.ts) — losing them silently logs the user out.
    const stored = await page.evaluate(() => ({
      access: localStorage.getItem('access_token'),
      refresh: localStorage.getItem('refresh_token'),
      user: localStorage.getItem('user'),
    }))
    expect(stored.access).toBe('test-access-token')
    expect(stored.refresh).toBe('test-refresh-token')
    expect(JSON.parse(stored.user!)).toMatchObject({ email: TEST_USER.email })
  })

  test('surfaces the server message on bad credentials and stays put', async ({ page, api }) => {
    await api.on('**/api/v1/auth/login', {
      status: 401,
      body: apiError('Incorrect email or password'),
    })

    await page.getByLabel('Email Id :').fill(TEST_USER.email)
    await page.getByLabel('Password:', { exact: true }).fill('wrong-password')
    await page.getByRole('button', { name: 'Login Now' }).click()

    await expect(page.getByText('Incorrect email or password')).toBeVisible()
    await expect(page).toHaveURL(/\/login/)
    expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
  })

  test('does not call the API when the form is empty', async ({ page, api }) => {
    await page.getByRole('button', { name: 'Login Now' }).click()

    // Native `required` should block submission — no request, no navigation.
    await expect(page).toHaveURL(/\/login/)
    expect(api.callsTo('/auth/login')).toHaveLength(0)
  })

  test('offers a route to registration and password recovery', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Sign up here.' })).toHaveAttribute(
      'href',
      '/register',
    )
    await expect(page.getByRole('link', { name: 'Forgot password?' })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })
})
