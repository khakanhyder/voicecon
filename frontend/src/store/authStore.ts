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

  logout: async () => {
    await authService.logout()
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
