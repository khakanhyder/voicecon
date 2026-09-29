import axios, { AxiosError } from 'axios'
import {
  LOGIN_PATH,
  clearOrganizationId,
  clearScope,
  currentScope,
  getAccessToken,
  getOrganizationId,
  getRefreshToken,
  setAccessToken,
} from './session'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

// Attach the access token and the active workspace to every request.
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    // Scoped to the console this page belongs to, so an admin tab can never
    // pick up the customer session's token, or the reverse (lib/session.ts).
    const token = getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Which workspace this request acts inside. Sending it explicitly keeps two
    // tabs in two different workspaces from stealing each other's context, and
    // makes a switch take effect immediately rather than on the next reload.
    // `X-Skip-Workspace` opts a request out (used by the switch call itself,
    // whose target is in the path and whose stored id may be stale).
    if (config.headers['X-Skip-Workspace']) {
      delete config.headers['X-Skip-Workspace']
    } else {
      const orgId = getOrganizationId()
      if (orgId) {
        config.headers['X-Organization-Id'] = orgId
      }
    }
  }
  return config
})

// Auto-refresh on 401
apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as any
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const scope = currentScope()
        const refresh = getRefreshToken(scope)
        if (refresh) {
          const { data } = await axios.post(`${API_BASE}/api/v1/auth/refresh`, {
            refresh_token: refresh,
          })
          // A 2xx is not proof of a token. A proxy answering 200 with an empty
          // body, or a half-deployed backend, used to land here and store the
          // *string* "undefined" — after which every request carried
          // `Authorization: Bearer undefined`, so the user looked signed in
          // while the API rejected them forever. Treat a tokenless response as
          // a failed refresh and fall through to the sign-out path below.
          const token = data?.access_token
          if (typeof token !== 'string' || !token) {
            throw new Error('Refresh succeeded but returned no access token')
          }
          // The server mints the replacement in the same scope it received,
          // so this stays inside the console the request came from.
          setAccessToken(token, scope)
          original.headers.Authorization = `Bearer ${token}`
          return apiClient(original)
        }
      } catch {
        // Only this console's session is dropped — the other one, if the
        // person has it, is a separate sign-in and none of our business here.
        const scope = currentScope()
        clearScope(scope)
        window.location.href = LOGIN_PATH[scope]
      }
    }

    // 402 Payment Required — the org's plan doesn't cover this action. Hand it
    // to the upgrade dialog rather than letting a raw error toast surface, and
    // keep rejecting so the calling component still knows the request failed.
    //
    // This is distinct from a 403: 403 means "ask your admin", 402 means
    // "upgrade your plan", and the two need different UI.
    if (error.response?.status === 402 && typeof window !== 'undefined') {
      const body = error.response.data as any
      if (body?.code === 'entitlement_required') {
        window.dispatchEvent(
          new CustomEvent('voicecon:entitlement-required', { detail: body })
        )
      }
    }

    // The stored workspace no longer exists, or access to it was revoked while
    // this tab was open. Drop the pin and retry once so the server picks a
    // workspace the user still belongs to, instead of leaving the tab stuck
    // on a permanent 403.
    if (
      error.response?.status === 403 &&
      typeof window !== 'undefined' &&
      getOrganizationId() &&
      /access to this workspace|no longer active/i.test(
        String((error.response?.data as any)?.detail ?? '')
      ) &&
      !original._workspaceRetry
    ) {
      original._workspaceRetry = true
      clearOrganizationId()
      delete original.headers['X-Organization-Id']
      return apiClient(original)
    }

    return Promise.reject(error)
  }
)

/**
 * The first validation failure in a 422 body, phrased for a person.
 *
 * The API answers a rejected field with
 * `{error, message: "Request validation failed", details: [{loc, msg}]}`.
 * Reading only `detail`/`message` — as this used to — showed every one of them
 * as "Request validation failed", so a user told to pick a different password
 * saw nothing about passwords. `details[0].msg` carries the real sentence.
 *
 * Pydantic prefixes a message raised from a custom validator with
 * "Value error, ", which is an implementation detail of the server and not
 * something to put in front of a user.
 */
function firstValidationMessage(data: any): string | null {
  const details = data?.details
  if (!Array.isArray(details) || details.length === 0) return null
  const raw = details[0]?.msg
  if (typeof raw !== 'string' || !raw) return null
  return raw.replace(/^Value error,\s*/, '')
}

/** What a customer sees when there is nothing more specific to say. */
export const GENERIC_ERROR = 'Something went wrong. Please try again.'

const NETWORK_ERROR = 'We couldn’t reach Voicecon. Check your internet connection and try again.'
const TIMEOUT_ERROR = 'That took longer than expected. Please try again.'
const SERVER_ERROR = 'Something went wrong on our side. Please try again in a moment.'

/**
 * Friendly defaults for a status the server gave no usable sentence for.
 * 500 and anything else in the 5xx range are always ours, so they never show
 * the server's text; 503 is the one 5xx the API words for people (payment
 * provider down, carrier unreachable).
 */
const STATUS_MESSAGES: Record<number, string> = {
  401: 'Your session has expired. Please sign in again.',
  403: 'You don’t have permission to do that in this workspace.',
  404: 'We couldn’t find that. It may have been moved or deleted.',
  408: TIMEOUT_ERROR,
  413: 'That file is too large.',
  429: 'Too many attempts. Please wait a moment and try again.',
}

// Mirrors backend app/core/public_errors.py. Text that matches came out of a
// library, a database or a provider rather than being written for a person.
const TECHNICAL =
  /traceback|exception|errno|stack ?trace|\b[A-Z][A-Za-z]+(Error|Exception)\b|nonetype|object has no attribute|not subscriptable|unexpected keyword|undefined is not|cannot read propert|is not a function|sqlalchemy|psycopg|asyncpg|integrityerror|duplicate key|violates|httpx|aiohttp|urllib|connectionpool|max retries|ssl|certificate|\bstatus code \d{3}\b|\bfor url\b|https?:\/\/|failed to fetch|load failed|object at 0x|<[a-z!/]|^\s*[[{]|\[object Object\]/i

/** True when `text` is not a short, plain sentence written for a person. */
export function looksTechnical(text: unknown): boolean {
  if (typeof text !== 'string' || !text.trim()) return true
  // A sentence for a person has more than one word; "network", "HTTP 500" or
  // "Unauthorized" on their own are codes, not explanations.
  if (!/\s/.test(text.trim()) || /^HTTP \d{3}$/i.test(text.trim())) return true
  return text.length > 240 || TECHNICAL.test(text)
}

function logForDevelopers(error: unknown) {
  // The server logs every failure it answers; this is for whoever is working
  // on the frontend. Production consoles stay quiet — customers can open them.
  if (process.env.NODE_ENV !== 'production' && typeof console !== 'undefined') {
    console.error('[voicecon] request failed', error)
  }
}

/**
 * The message to show a customer for a failed request.
 *
 * Only a short, human sentence from a 4xx (or a 503, which the API words for
 * people) is shown as is. A 500, a network failure, a timeout, or any text that
 * reads like an exception, a stack trace or a provider's raw response becomes
 * `fallback` or a friendly status message — those details belong in the logs,
 * not in front of the customer.
 */
export function getErrorMessage(error: unknown, fallback: string = GENERIC_ERROR): string {
  const safe = (text: unknown) => (looksTechnical(text) ? null : (text as string))

  // Anything shaped like an HTTP failure counts, not only a real AxiosError:
  // services and tests reject with `{response: {status, data}}` too.
  const http = axios.isAxiosError(error)
    ? error
    : error && typeof error === 'object' && 'response' in error
      ? (error as { response?: { status?: number; data?: unknown }; code?: string })
      : null
  if (http) {
    logForDevelopers(error)
    if (!http.response) {
      return http.code === 'ECONNABORTED' || http.code === 'ETIMEDOUT' ? TIMEOUT_ERROR : NETWORK_ERROR
    }
    const status = http.response.status ?? 0
    if (status >= 500 && status !== 503) return fallback === GENERIC_ERROR ? SERVER_ERROR : fallback

    const data = http.response.data as any
    // Some endpoints answer with a structured detail — `{message, errors}` or
    // `{detail, code}` — which rendered as "[object Object]" when returned as is.
    const detail = data?.detail
    const detailText =
      typeof detail === 'string'
        ? detail
        : typeof detail?.message === 'string'
          ? detail.message
          : typeof detail?.detail === 'string'
            ? detail.detail
            : null
    return (
      safe(detailText) ||
      safe(firstValidationMessage(data)) ||
      safe(data?.message) ||
      (fallback !== GENERIC_ERROR ? fallback : null) ||
      STATUS_MESSAGES[status] ||
      (status === 503 ? SERVER_ERROR : fallback)
    )
  }
  logForDevelopers(error)
  if (error instanceof Error) return safe(error.message) || fallback
  return fallback
}

/**
 * `text` from a stored failure (a workflow step, a call's integration change)
 * if it reads as a sentence for a person, otherwise `fallback`.
 */
export function publicErrorText(text: unknown, fallback: string): string {
  return looksTechnical(text) ? fallback : (text as string)
}
