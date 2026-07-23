/**
 * Social login hook — Google (auth-code popup) and Apple (Sign in with Apple JS).
 *
 * Both providers converge on the same session handling: persist tokens, hydrate
 * the auth store, then route new users into onboarding and returning users to
 * the dashboard. Each provider is gated on its public config being present, so
 * an unconfigured button degrades to a friendly "coming soon" toast rather than
 * a hard failure.
 */
'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { authService } from '@/lib/auth'
import { signInWithApple, isAppleConfigured } from '@/lib/appleAuth'
import { useAuthStore } from '@/store/authStore'
import { QUERY_KEYS } from '@/lib/constants'
import { getErrorMessage } from '@/lib/api'

export const GOOGLE_ENABLED = Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID)

export function useSocialAuth() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const setUser = useAuthStore((s) => s.setUser)

  const onAuthed = (data: any) => {
    setUser(data.user)
    queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ME] })
    if (data.user?.is_new) {
      toast.success('Account created! Let’s set up your workspace.')
      router.push('/onboarding/company')
    } else {
      toast.success('Welcome back!')
      router.push('/dashboard')
    }
  }

  const googleMutation = useMutation({
    mutationFn: (code: string) => authService.googleAuth(code),
    onSuccess: onAuthed,
    onError: (e: any) => toast.error(getErrorMessage(e) || 'Google sign-in failed'),
  })

  const appleMutation = useMutation({
    mutationFn: async () => {
      const { id_token, full_name } = await signInWithApple()
      return authService.appleAuth({ id_token, full_name })
    },
    onSuccess: onAuthed,
    onError: (e: any) => {
      // A user closing the Apple popup shows up as a benign error — don't shout.
      const msg = getErrorMessage(e)
      if (msg && !/popup|cancel/i.test(msg)) toast.error(msg)
    },
  })

  const startAppleSignIn = () => {
    if (!isAppleConfigured()) {
      toast.info('Apple sign-in is coming soon.')
      return
    }
    appleMutation.mutate()
  }

  return {
    // Google's useGoogleLogin() lives in <GoogleButton>, which is only mounted
    // when configured — so this hook never touches GIS when it's unconfigured.
    onGoogleCode: (code: string) => googleMutation.mutate(code),
    onGoogleError: () => toast.error('Google sign-in was cancelled'),
    signInWithApple: startAppleSignIn,
    googleEnabled: GOOGLE_ENABLED,
    appleEnabled: isAppleConfigured(),
    isGoogleLoading: googleMutation.isPending,
    isAppleLoading: appleMutation.isPending,
  }
}
