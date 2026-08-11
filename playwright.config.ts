import { defineConfig, devices } from '@playwright/test'

/* Frontend dev server. Override with PORT=3002 npx playwright test if 3000 is taken. */
const PORT = process.env.PORT ?? '3000'
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`

/**
 * The `api` and `e2e` projects need a real FastAPI backend and Postgres, so they
 * are opt-in:
 *   E2E=1 npx playwright test
 * Without E2E set, only the mocked `ui-*` projects run — no infra required, so a
 * fresh clone and CI both go green with nothing but `npm ci`.
 */
const E2E = !!process.env.E2E

const STORAGE_STATE = 'playwright/.auth/user.json'

export default defineConfig({
  testDir: './tests',
  /* Runs after webServer is up: compiles every route once so no test is the
     one that pays for `next dev`'s first build of a page. See the file. */
  globalSetup: './tests/support/warmup.ts',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* HTML for humans, JUnit for CI test reporting, list for the terminal. */
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
  ],
  /* Screenshots, videos and traces land here and are uploaded by CI. */
  outputDir: 'test-results',
  /**
   * Generous, because the suite runs against `next dev`, which compiles each
   * route the first time it is requested. With several workers hitting
   * different routes at once that first paint routinely passes 5s — the
   * default — and produced failures that vanished at --workers=1. Running
   * against a production build instead would let these drop back down.
   */
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: BASE_URL,
    /* Full trace for anything that fails, including on the first attempt —
       a local run has no retry to fall back on. */
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  projects: [
    /* Mocked-backend UI tests — every /api/v1/* call is intercepted. */
    {
      name: 'ui-chromium',
      testDir: './tests/ui',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'ui-firefox',
      testDir: './tests/ui',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'ui-webkit',
      testDir: './tests/ui',
      use: { ...devices['Desktop Safari'] },
    },

    ...(E2E
      ? [
          /* Backend contract tests. No browser involved — these drive the API
             directly, so they pin the request/response shapes the mocked UI
             tests above assume. When these fail, the mocks are lying. */
          {
            name: 'api',
            testDir: './tests/api',
            use: { ...devices['Desktop Chrome'] },
          },
          /* Real-backend critical paths through the UI. One browser is enough —
             these assert on API behaviour, not rendering, and each writes to
             the database. */
          {
            name: 'e2e-setup',
            testMatch: /auth\.setup\.ts/,
            use: { ...devices['Desktop Chrome'] },
          },
          {
            name: 'e2e',
            testDir: './tests/e2e',
            dependencies: ['e2e-setup'],
            use: { ...devices['Desktop Chrome'], storageState: STORAGE_STATE },
          },
        ]
      : []),
  ],

  webServer: {
    command: `npm run dev --prefix frontend -- --port ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    /* Next's first compile on a cold CI runner routinely exceeds the 60s default. */
    timeout: 120 * 1000,
  },
})
