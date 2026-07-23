'use client'

import { useGoogleLogin } from '@react-oauth/google'
import { toast } from 'sonner'
import { GoogleIcon, AppleIcon } from '@/lib/icons'
import { useSocialAuth } from '@/hooks/useSocialAuth'

const BTN =
  'flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-2 md:px-4 py-2.5 text-sm md:text-base font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60'

const Spinner = () => (
  <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
)

/**
 * Google button. Isolated into its own component so useGoogleLogin() — which
 * initializes Google's GIS code client — only ever runs when a client id is
 * configured (this component is rendered conditionally by SocialAuthButtons).
 */
function GoogleButton({
  label, onCode, onError, disabled, loading,
}: {
  label: string
  onCode: (code: string) => void
  onError: () => void
  disabled: boolean
  loading: boolean
}) {
  const login = useGoogleLogin({
    flow: 'auth-code',
    onSuccess: ({ code }) => onCode(code),
    onError,
  })
  return (
    <button type="button" onClick={() => login()} disabled={disabled} className={BTN}>
      {loading ? <Spinner /> : <GoogleIcon className="h-5 w-5" />}
      {label}
    </button>
  )
}

/**
 * Google + Apple sign-in buttons, shared by the login and register pages.
 * `verb` controls the label ("Login" or "Sign up"). Providers that aren't
 * configured degrade to a friendly "coming soon" toast — never an error.
 */
export function SocialAuthButtons({ verb }: { verb: 'Login' | 'Sign up' }) {
  const {
    onGoogleCode, onGoogleError, signInWithApple,
    googleEnabled, isGoogleLoading, isAppleLoading,
  } = useSocialAuth()
  const busy = isGoogleLoading || isAppleLoading

  return (
    <div className="grid grid-cols-2 gap-3">
      {googleEnabled ? (
        <GoogleButton
          label={`${verb} With Google`}
          onCode={onGoogleCode}
          onError={onGoogleError}
          disabled={busy}
          loading={isGoogleLoading}
        />
      ) : (
        <button
          type="button"
          onClick={() => toast.info('Google sign-in is coming soon.')}
          className={BTN}
        >
          <GoogleIcon className="h-5 w-5" />
          {verb} With Google
        </button>
      )}

      <button type="button" onClick={signInWithApple} disabled={busy} className={BTN}>
        {isAppleLoading ? <Spinner /> : <AppleIcon className="h-5 w-5 text-slate-900" />}
        {verb} With Apple
      </button>
    </div>
  )
}
