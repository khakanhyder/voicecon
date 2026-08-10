import axios, { AxiosError } from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

// Attach the access token and the active workspace to every request.
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
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
      const orgId = localStorage.getItem('active_organization_id')
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
        const refresh = localStorage.getItem('refresh_token')
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
          localStorage.setItem('access_token', token)
          original.headers.Authorization = `Bearer ${token}`
          return apiClient(original)
        }
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('active_organization_id')
        window.location.href = '/login'
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
      localStorage.getItem('active_organization_id') &&
      /access to this workspace|no longer active/i.test(
        String((error.response?.data as any)?.detail ?? '')
      ) &&
      !original._workspaceRetry
    ) {
      original._workspaceRetry = true
      localStorage.removeItem('active_organization_id')
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

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    return (
      data?.detail ||
      firstValidationMessage(data) ||
      data?.message ||
      error.message ||
      'An unexpected error occurred'
    )
  }
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred'
}
