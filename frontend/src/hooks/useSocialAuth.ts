/**
 * Social login hook — Google (auth-code popup) and Apple (Sign in with Apple JS).
 *
 * Both providers converge on the same session handling: persist tokens, hydrate
 * the auth store, then route on the account's
 * onboarding status — into onboarding when it is unfinished, to the dashboard
 * when it is done. Each provider is gated on its public config being present, so
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
import { resolvePostAuthPath } from '@/lib/postAuthRedirect'
import { getErrorMessage } from '@/lib/api'

export const GOOGLE_ENABLED = Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID)

export function useSocialAuth() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const setUser = useAuthStore((s) => s.setUser)

  const onAuthed = async (data: any) => {
    setUser(data.user)
    queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ME] })

    // Route on the server's onboarding status, not on `is_new`. Someone who
    // signed in with Apple or Google once and never finished onboarding is not
    // new, but still needs the rest of the flow before the dashboard means
    // anything — and someone who did finish must never be sent back into it.
    const path = await resolvePostAuthPath(queryClient, { isNew: data.user?.is_new })
    if (path === '/dashboard') {
      toast.success(data.user?.is_new ? 'Account created!' : 'Welcome back!')
    } else {
      toast.success(
        data.user?.is_new
          ? 'Account created! Let’s set up your workspace.'
          : 'Welcome back! Let’s finish setting up your workspace.',
      )
    }
    router.push(path)
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
      if (msg && !/popup|cancel|user_trigger/i.test(msg)) toast.error(msg)
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
