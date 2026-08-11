/**
 * Vitest configuration for frontend unit tests.
 *
 * Deliberately scoped to `src/`: the Playwright suite lives in `<repo>/tests`
 * and owns `*.spec.ts`, so this matches only `*.test.ts(x)` under `src/` and the
 * two never collect each other's files.
 */
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  // `tsconfigPaths` resolves the `@/*` alias from tsconfig.json, so tests import
  // modules exactly the way the app does.
  plugins: [react(), tsconfigPaths()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // node_modules and .next are obvious; `tests/` is Playwright's and would
    // otherwise be picked up as if it were a unit test.
    exclude: ['node_modules/**', '.next/**', '../tests/**'],
    css: false,
    restoreMocks: true,
    clearMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/**/*.d.ts',
        'src/types/**',
        // Next.js route files — pages, layouts, templates and API handlers.
        // These are whole screens wired to the router and the network, and they
        // are already driven end-to-end by the Playwright suite in <repo>/tests
        // against a real browser. Counting them here would not measure anything
        // this suite is responsible for; everything else under src/ — lib,
        // store, hooks and components — stays in the denominator whether or not
        // it currently has tests, so the number stays honest about the gap.
        'src/app/**',
      ],
    },
  },
})
