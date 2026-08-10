/**
 * Authentication Zustand Store
 */
import { create } from 'zustand'
import { User, authService } from '@/lib/auth'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  setUser: (user: User | null) => void
  setLoading: (loading: boolean) => void
  logout: () => Promise<void>
  initialize: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  setUser: (user) =>
    set({
      user,
      isAuthenticated: !!user,
      isLoading: false,
    }),

  setLoading: (loading) => set({ isLoading: loading }),

  /**
   * Reset the in-memory session only.
   *
   * Deliberately does no network call: the caller that owns the sign-out flow
   * (hooks/useAuth.ts) already posts /auth/logout, and having the store post it
   * too sent the request twice on every sign-out.
   */
  logout: async () => {
    set({
      user: null,
      isAuthenticated: false,
    })
  },

  initialize: () => {
    const user = authService.getCurrentUser()
    const isAuthenticated = authService.isAuthenticated()

    set({
      user,
      isAuthenticated,
      isLoading: false,
    })
  },
}))
