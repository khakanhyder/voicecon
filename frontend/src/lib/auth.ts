import { apiClient } from './api'
import {
  clearScope,
  getAccessToken,
  getStoredUser,
  setStoredUser,
  storeSession,
  type SessionScope,
} from './session'

export interface User {
  id: string
  email: string
  full_name: string | null
  company_name: string | null
  phone_number: string | null
  bio: string | null
  avatar_url: string | null
  timezone: string
  language: string
  is_active: boolean
  is_verified: boolean
  /** Voicecon staff with access to /admin. Optional: older cached users lack it. */
  is_platform_admin?: boolean
  email_verified_at: string | null
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface ProfileUpdate {
  full_name?: string | null
  company_name?: string | null
  phone_number?: string | null
  bio?: string | null
  avatar_url?: string | null
  timezone?: string | null
  language?: string | null
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterData {
  email: string
  password: string
  full_name?: string
  phone_number?: string
  /** Proof from verifyEmailCode that the address was confirmed. */
  email_verification_token?: string
}

export interface SendCodeResult {
  message: string
  expires_in_minutes: number
  /** Present only in local dev with no mail transport configured. */
  debug_code?: string | null
}

export interface VerifyCodeResult {
  verified: boolean
  email: string
  email_verification_token: string
  expires_in_minutes: number
}

export const authService = {
  async login(credentials: LoginCredentials) {
    const { data } = await apiClient.post('/api/v1/auth/login', credentials)
    // Stored under the customer app's keys. The token the server issued is
    // app-scoped too, so it is refused by the admin API even for staff.
    storeSession(data, 'app')
    return data
  },

  /**
   * Sign in to the staff console.
   *
   * A separate endpoint, not `/auth/login` plus a permission check: the token
   * it returns carries an `admin` session scope, which is what keeps this
   * sign-in from also being a sign-in to the product. A non-admin account is
   * refused with the same 401 as a wrong password.
   */
  async adminLogin(credentials: LoginCredentials) {
    const { data } = await apiClient.post('/api/v1/auth/admin/login', credentials)
    storeSession(data, 'admin')
    return data
  },

  async register(data: RegisterData) {
    const { data: res } = await apiClient.post('/api/v1/auth/register', data)
    return res
  },

  // ── Email verification (sign-up) ──────────────────────────────────────────

  /** Email a one-time code to confirm an address before registering. */
  async sendEmailCode(email: string): Promise<SendCodeResult> {
    const { data } = await apiClient.post('/api/v1/auth/email/send-code', {
      email,
      purpose: 'signup',
    })
    return data
  },

  /** Exchange a correct code for the token that /register requires. */
  async verifyEmailCode(email: string, code: string): Promise<VerifyCodeResult> {
    const { data } = await apiClient.post('/api/v1/auth/email/verify-code', { email, code })
    return data
  },

  // ── Forgotten password ────────────────────────────────────────────────────

  /** Always resolves, whether or not the address has an account. */
  async forgotPassword(email: string): Promise<SendCodeResult> {
    const { data } = await apiClient.post('/api/v1/auth/password/forgot', { email })
    return data
  },

  /** Sets the new password and signs the user in with the returned session. */
  async resetPassword(params: { email: string; code: string; new_password: string }) {
    const { data } = await apiClient.post('/api/v1/auth/password/reset', params)
    return authService.persistSession(data)
  },

  // Persist the session returned by any auth endpoint (login / google / apple).
  // Social sign-in only exists in the customer app, so it is always app-scoped.
  persistSession(data: any) {
    storeSession(data, 'app')
    return data
  },

  async googleAuth(code: string, redirectUri = 'postmessage') {
    const { data } = await apiClient.post('/api/v1/auth/google', { code, redirect_uri: redirectUri })
    return authService.persistSession(data)
  },

  async appleAuth(params: { id_token: string; full_name?: string; nonce?: string }) {
    const { data } = await apiClient.post('/api/v1/auth/apple', params)
    return authService.persistSession(data)
  },

  // Fetch the live profile from the backend and cache it locally.
  async fetchMe(): Promise<User> {
    const { data } = await apiClient.get<User>('/api/v1/users/me')
    setStoredUser(data)
    return data
  },

  async updateProfile(update: ProfileUpdate): Promise<User> {
    const { data } = await apiClient.patch<User>('/api/v1/users/me', update)
    setStoredUser(data)
    return data
  },

  /**
   * Upload a new profile picture.
   *
   * The server validates and re-encodes the image, so the URL it returns is
   * the source of truth — never optimistically keep a local object URL.
   */
  async uploadAvatar(file: File): Promise<User> {
    const body = new FormData()
    body.append('file', file)
    const { data } = await apiClient.post<User>('/api/v1/users/me/avatar', body, {
      // The client defaults to application/json. Clearing it lets the browser
      // set multipart/form-data *with the boundary*, which the server needs to
      // parse the parts at all.
      headers: { 'Content-Type': undefined },
    })
    setStoredUser(data)
    return data
  },

  async removeAvatar(): Promise<User> {
    const { data } = await apiClient.delete<User>('/api/v1/users/me/avatar')
    setStoredUser(data)
    return data
  },

  async changePassword(params: { current_password?: string; new_password: string }) {
    await apiClient.post('/api/v1/users/me/change-password', params)
  },

  async deleteAccount() {
    await apiClient.delete('/api/v1/users/me')
    clearScope()
  },

  /**
   * Drop every trace of the session from this browser.
   *
   * Separate from `logout()` so the caller can run it *again* after cancelling
   * in-flight queries: `fetchMe` writes `user` back to localStorage whenever it
   * resolves, so a request already on the wire can otherwise repopulate the
   * profile microseconds after sign-out.
   */
  clearSession(scope?: SessionScope) {
    clearScope(scope)
  },

  async logout() {
    try {
      await apiClient.post('/api/v1/auth/logout')
    } catch {}
    authService.clearSession()
  },

  getCurrentUser(scope?: SessionScope): User | null {
    return getStoredUser<User>(scope)
  },

  isAuthenticated(scope?: SessionScope): boolean {
    return !!getAccessToken(scope)
  },
}
