/**
 * Phone numbers: API calls, display helpers and user-facing error text.
 *
 * There are two ways to get a number, and only the second is about carriers:
 *  - **Voicecon numbers** (`source: 'voicecon'`) — search, pick, buy. Which
 *    carrier runs them is infrastructure; the API never names it and neither
 *    does the UI.
 *  - **Your own provider** (`source: 'own'`) — numbers on a Twilio/Telnyx
 *    account the workspace connected itself, so its name is shown.
 */
import axios from 'axios'
import { apiClient, looksTechnical } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

export type NumberSource = 'voicecon' | 'own'

export interface PhoneNumber {
  id: string
  phone_number: string
  country_code: string | null
  area_code: string | null
  /** The carrier for an own-provider number; 'voicecon' for a Voicecon number. */
  provider: string
  source: NumberSource
  agent_id: string | null
  capabilities: Record<string, boolean>
  status: string
  monthly_cost: number | null
  created_at: string
  /** Brought in from the user's own account; removing it only disconnects it. */
  imported?: boolean
  /**
   * Set when `status` is 'suspended': the workspace has no active plan, and the
   * number is released on this date unless it subscribes again.
   */
  release_after?: string | null
}

/** A number already on one of the workspace's own carrier accounts. */
export interface OwnAccountNumber {
  phone_number: string
  friendly_name: string | null
  capabilities: Record<string, boolean>
  /** Set when the number is already in this workspace. */
  phone_number_id: string | null
  /** False when it's already in this or another workspace. */
  available: boolean
}

export interface AvailableNumber {
  phone_number: string
  friendly_name: string
  provider: string
  locality: string | null
  region: string | null
  capabilities: Record<string, boolean>
  monthly_cost: number | null
  setup_cost: number | null
  currency: string | null
}

/** A carrier account the workspace connected itself. */
export interface OwnProvider {
  slug: string
  name: string
  source: string
  connection_id: string | null
  connection_name: string | null
  is_default?: boolean
}

export interface SupportedProvider {
  slug: string
  name: string
  description: string
  connected: boolean
}

export interface PurchaseOptions {
  voicecon_available: boolean
  own_providers: OwnProvider[]
  supported_providers: SupportedProvider[]
}

export const COUNTRIES: { code: string; name: string; flag: string }[] = [
  { code: 'US', name: 'United States', flag: '🇺🇸' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'AU', name: 'Australia', flag: '🇦🇺' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: 'FR', name: 'France', flag: '🇫🇷' },
]

export interface SearchParams {
  source: NumberSource
  country_code: string
  area_code?: string
  contains?: string
  connection_id?: string | null
  limit?: number
}

export const phoneNumberService = {
  async purchaseOptions(): Promise<PurchaseOptions> {
    const { data } = await apiClient.get<PurchaseOptions>(API_ENDPOINTS.PHONE_NUMBERS_PURCHASE_OPTIONS)
    return data
  },

  async search(params: SearchParams): Promise<AvailableNumber[]> {
    const query = new URLSearchParams({
      source: params.source,
      country_code: params.country_code,
      limit: String(params.limit ?? 12),
    })
    if (params.area_code) query.set('area_code', params.area_code)
    if (params.contains) query.set('contains', params.contains)
    if (params.source === 'own' && params.connection_id) query.set('connection_id', params.connection_id)
    const { data } = await apiClient.get<AvailableNumber[]>(`${API_ENDPOINTS.PHONE_NUMBERS_SEARCH}?${query}`)
    return Array.isArray(data) ? data : []
  },

  async purchase(payload: {
    source: NumberSource
    number: AvailableNumber
    agent_id: string
    country_code: string
    area_code?: string
    connection_id?: string | null
  }): Promise<PhoneNumber> {
    const { data } = await apiClient.post<PhoneNumber>(API_ENDPOINTS.PHONE_NUMBERS_PROVISION, {
      source: payload.source,
      phone_number: payload.number.phone_number,
      agent_id: payload.agent_id,
      connection_id: payload.source === 'own' ? payload.connection_id : undefined,
      country_code: payload.country_code,
      area_code: payload.area_code || null,
      monthly_cost: payload.number.monthly_cost,
    })
    return data
  },

  /** Numbers already on a connected account, including ones bought directly there. */
  async ownAccountNumbers(connectionId: string): Promise<OwnAccountNumber[]> {
    const { data } = await apiClient.get<OwnAccountNumber[]>(API_ENDPOINTS.PHONE_NUMBERS_OWN, {
      params: { connection_id: connectionId },
    })
    return Array.isArray(data) ? data : []
  },

  /** Bring a number from the user's own account into Voicecon. */
  async importNumber(payload: {
    connection_id: string
    phone_number: string
    agent_id?: string | null
  }): Promise<PhoneNumber> {
    const { data } = await apiClient.post<PhoneNumber>(API_ENDPOINTS.PHONE_NUMBERS_IMPORT, {
      ...payload,
      agent_id: payload.agent_id || null,
    })
    return data
  },

  /**
   * Point a number at a different agent, or detach it with `null`. The
   * backend re-points the carrier too, and inbound calls follow the saved
   * assignment from the next call on — a detached number stops answering.
   */
  async assignAgent(phoneNumberId: string, agentId: string | null): Promise<PhoneNumber> {
    const { data } = await apiClient.patch<PhoneNumber>(API_ENDPOINTS.PHONE_NUMBER(phoneNumberId), {
      agent_id: agentId,
    })
    return data
  },
}

// ---- Display ----------------------------------------------------------------

/** "+14155550100" → "+1 (415) 555-0100"; other countries keep E.164 with spacing. */
export function formatPhoneNumber(e164: string): string {
  const digits = e164.replace(/[^\d]/g, '')
  if (digits.length === 11 && digits.startsWith('1')) {
    return `+1 (${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`
  }
  if (e164.startsWith('+') && digits.length > 6) {
    return `+${digits.slice(0, 2)} ${digits.slice(2).replace(/(\d{3,4})(?=\d)/g, '$1 ')}`.trim()
  }
  return e164
}

export function formatMonthly(cost: number | null | undefined, currency?: string | null): string | null {
  if (cost == null) return null
  const code = (currency || 'USD').toUpperCase()
  try {
    return `${new Intl.NumberFormat('en-US', { style: 'currency', currency: code }).format(cost)}/mo`
  } catch {
    return `${cost.toFixed(2)} ${code}/mo`
  }
}

export function locationLabel(n: Pick<AvailableNumber, 'locality' | 'region'>): string | null {
  const parts = [n.locality, n.region].filter(Boolean)
  return parts.length ? parts.join(', ') : null
}

export const hasSms = (caps: Record<string, boolean> | undefined) => !!(caps?.sms || caps?.SMS)
export const hasVoice = (caps: Record<string, boolean> | undefined) => caps?.voice !== false

// ---- Validation ---------------------------------------------------------------

export function validateSearch(country: string, areaCode: string, contains: string): string | null {
  const area = areaCode.trim()
  if (area && (country === 'US' || country === 'CA') && !/^\d{3}$/.test(area)) {
    return 'US and Canadian area codes are 3 digits, for example 415.'
  }
  if (area && !/^\d+$/.test(area)) return 'Area codes contain digits only.'
  if (contains.trim() && !/^[\d*]+$/.test(contains.trim())) {
    return '“Contains” should be digits only, for example 555.'
  }
  return null
}

// ---- Errors --------------------------------------------------------------------

export type PhoneAction = 'search' | 'purchase' | 'options' | 'list' | 'release' | 'assign' | 'own_list' | 'import'

const FALLBACK: Record<PhoneAction, string> = {
  search: 'We couldn’t load available numbers right now. Please try again.',
  purchase: 'Unable to complete the purchase. Please try again or contact support.',
  options: 'We couldn’t load phone number options right now. Please try again.',
  list: 'We couldn’t load your phone numbers right now. Please try again.',
  release: 'We couldn’t release this number right now. Please try again or contact support.',
  assign: 'We couldn’t change the assistant for this number right now. Please try again.',
  own_list: 'We couldn’t load the numbers on your account right now. Please try again.',
  import: 'We couldn’t add this number right now. Please try again.',
}

/**
 * A message that is safe to show for a failed phone-number request.
 *
 * Only a plain-string `detail` from an expected status is shown: the backend
 * writes those for users. Anything else — a network failure, a 500, a
 * validation payload, an HTML error page from a proxy — becomes the plain
 * sentence for the action. The raw error is logged to the console for
 * debugging, never rendered.
 */
export function friendlyPhoneError(error: unknown, action: PhoneAction): string {
  if (process.env.NODE_ENV !== 'production' && typeof console !== 'undefined') {
    console.error(`[phone-numbers] ${action} failed`, error)
  }
  if (!axios.isAxiosError(error)) return FALLBACK[action]
  const status = error.response?.status
  if (!error.response) {
    return 'We couldn’t reach Voicecon. Check your internet connection and try again.'
  }
  if (status === 402) {
    // The upgrade dialog opens globally for this; keep the inline text calm.
    return 'Buying phone numbers isn’t included in your current plan.'
  }
  if (status === 403) return 'You don’t have permission to do that in this workspace.'
  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail
  const shown = status && [400, 404, 409, 429, 503].includes(status)
  if (shown && typeof detail === 'string' && !looksTechnical(detail)) {
    return detail
  }
  return FALLBACK[action]
}
