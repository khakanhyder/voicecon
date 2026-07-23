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
