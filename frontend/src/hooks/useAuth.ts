/**
 * Authentication hook using React Query
 */
'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { authService, LoginCredentials, RegisterData } from '@/lib/auth'
import { useAuthStore } from '@/store/authStore'
import { QUERY_KEYS } from '@/lib/constants'
import { toast } from 'sonner'

export function useAuth() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { user, isAuthenticated, setUser, logout: storeLogout } = useAuthStore()

  // Fetch current user
  const { data: currentUser, isLoading } = useQuery({
    queryKey: [QUERY_KEYS.ME],
    queryFn: authService.fetchMe,
    enabled: isAuthenticated,
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: (credentials: LoginCredentials) => authService.login(credentials),
    onSuccess: (data) => {
      setUser(data.user)
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ME] })
      toast.success('Welcome back!')
      router.push('/dashboard')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Login failed')
    },
  })

  // Register mutation
  const registerMutation = useMutation({
    mutationFn: (data: RegisterData) => authService.register(data),
    onSuccess: () => {
      toast.success('Account created successfully! Please login.')
      router.push('/login')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Registration failed')
    },
  })

  // Logout mutation
  const logoutMutation = useMutation({
    mutationFn: authService.logout,
    onSuccess: () => {
      storeLogout()
      queryClient.clear()
      toast.success('Logged out successfully')
      router.push('/login')
    },
  })

  return {
    user: currentUser || user,
    isAuthenticated,
    isLoading: isLoading || loginMutation.isPending,
    login: loginMutation.mutate,
    register: registerMutation.mutate,
    logout: logoutMutation.mutate,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
  }
}
