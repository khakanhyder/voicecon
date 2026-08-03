import { apiClient } from './api'

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
    if (data.access_token) {
      localStorage.setItem('access_token', data.access_token)
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token)
      }
      if (data.user) {
        localStorage.setItem('user', JSON.stringify(data.user))
      }
    }
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
  persistSession(data: any) {
    if (typeof window === 'undefined' || !data?.access_token) return data
    localStorage.setItem('access_token', data.access_token)
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
    if (data.user) localStorage.setItem('user', JSON.stringify(data.user))
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
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(data))
    }
    return data
  },

  async updateProfile(update: ProfileUpdate): Promise<User> {
    const { data } = await apiClient.patch<User>('/api/v1/users/me', update)
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(data))
    }
    return data
  },

  async changePassword(params: { current_password?: string; new_password: string }) {
    await apiClient.post('/api/v1/users/me/change-password', params)
  },

  async deleteAccount() {
    await apiClient.delete('/api/v1/users/me')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  },

  async logout() {
    try {
      await apiClient.post('/api/v1/auth/logout')
    } catch {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  },

  getCurrentUser(): User | null {
    if (typeof window === 'undefined') return null
    const raw = localStorage.getItem('user')
    if (!raw) return null
    try {
      return JSON.parse(raw)
    } catch {
      return null
    }
  },

  isAuthenticated(): boolean {
    if (typeof window === 'undefined') return false
    return !!localStorage.getItem('access_token')
  },
}
