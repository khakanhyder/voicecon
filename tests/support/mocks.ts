/**
 * Mocked-backend test fixture.
 *
 * Intercepts every `/api/v1/**` call so UI tests run without a backend or a
 * database. A catch-all returns 200 `{}` so no page hard-fails on an
 * unstubbed call; tests stub the endpoints they actually care about.
 */
import { test as base, type Page, type Request } from '@playwright/test'
import { ROUTES } from './routes'
import {
  entitlementsResponse,
  TEST_USER,
  workspaceListResponse,
  workspaceResponse,
} from './data'

const API_GLOB = '**/api/v1/**'

export interface MockResponse {
  status?: number
  body?: unknown
  /**
   * Simulate a transport failure instead of a reply — the app sees a network
   * error with no status code, which is a different code path from a 500.
   */
  abort?: 'failed' | 'connectionrefused' | 'timedout' | 'internetdisconnected'
}

export interface RecordedCall {
  method: string
  url: string
  body: unknown
}

export class ApiMock {
  /** Every intercepted request, in order — assert on what the app actually sent. */
  readonly calls: RecordedCall[] = []

  constructor(private readonly page: Page) {}

  /**
   * Stub one endpoint. Playwright gives precedence to the most recently
   * registered route, so this always wins over the catch-all installed at
   * fixture setup — and over any earlier `on()` for the same path.
   *
   * Pass an array to script a sequence: each call consumes the next entry and
   * the final one repeats. That is how the 401 → refresh → retry path is
   * tested, where the same URL must answer differently the second time.
   */
  async on(
    matcher: string | RegExp,
    res: MockResponse | MockResponse[] = {},
    opts: { method?: string } = {},
  ) {
    const queue = Array.isArray(res) ? [...res] : null
    const single = Array.isArray(res) ? null : res

    await this.page.route(matcher, async (route) => {
      // Method-scoped stub: let anything else fall through to the handler
      // registered before this one. Needed whenever one URL must answer
      // differently per verb — a GET that loads a form and a PATCH that fails,
      // say — which a response *sequence* cannot express, because React's dev
      // StrictMode double-fires effects and silently eats the first entry.
      if (opts.method && route.request().method() !== opts.method.toUpperCase()) {
        await route.fallback()
        return
      }
      this.record(route.request())
      const reply = queue ? (queue.length > 1 ? queue.shift()! : queue[0]) : single!

      if (reply.abort) {
        await route.abort(reply.abort)
        return
      }
      await route.fulfill({
        status: reply.status ?? 200,
        contentType: 'application/json',
        body: JSON.stringify(reply.body ?? {}),
      })
    })
  }

  /**
   * Stub the chrome every `/dashboard/*` page loads before it renders anything
   * of its own: the profile, the workspace (whose `permissions` array gates
   * every button), and the plan entitlements that drive the billing banner.
   *
   * Without this a dashboard test is really testing the error path, because
   * `workspace.permissions.includes(...)` throws on the catch-all's `{}`.
   */
  async installAppShell(overrides: {
    user?: Record<string, unknown>
    workspace?: Record<string, unknown>
    entitlements?: Record<string, unknown>
  } = {}) {
    await this.on(ROUTES.me, { body: { ...TEST_USER, ...overrides.user } })
    await this.on(ROUTES.workspaces, { body: workspaceListResponse() })
    await this.on(ROUTES.workspaceCurrent, { body: workspaceResponse(overrides.workspace) })
    await this.on(ROUTES.entitlements, { body: entitlementsResponse(overrides.entitlements) })
    // These endpoints return bare arrays. The catch-all's `{}` is not just
    // wrong, it is a different *type* — and components that call `.filter` on
    // the result crash the page rather than degrade.
    await this.on(ROUTES.knowledgeBases, { body: [] })
    await this.on(ROUTES.phoneNumbers, { body: [] })
  }

  /** Requests sent to paths containing `fragment`. */
  callsTo(fragment: string): RecordedCall[] {
    return this.calls.filter((c) => c.url.includes(fragment))
  }

  /** Requests sent to paths containing `fragment` with the given HTTP method. */
  callsOf(method: string, fragment: string): RecordedCall[] {
    return this.callsTo(fragment).filter((c) => c.method === method.toUpperCase())
  }

  async installCatchAll() {
    await this.page.route(API_GLOB, async (route) => {
      this.record(route.request())
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    })
  }

  private record(request: Request) {
    let body: unknown = null
    try {
      body = request.postDataJSON()
    } catch {
      // Not JSON (form posts, empty bodies) — the raw text is enough.
      body = request.postData()
    }
    this.calls.push({ method: request.method(), url: request.url(), body })
  }
}

export const test = base.extend<{ api: ApiMock }>({
  api: async ({ page }, use) => {
    const api = new ApiMock(page)
    await api.installCatchAll()
    await use(api)
  },
})

export { expect } from '@playwright/test'
