'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { toast } from 'sonner'
import { ArrowLeft, Loader2, Lock, Mail } from 'lucide-react'
import { affiliateApi, affiliateAuth } from '@/lib/affiliate'
import { getErrorMessage } from '@/lib/api'
import { clearScope } from '@/lib/session'
import { PasswordInput } from '@/components/ui/password-input'
import { OtpInput } from '@/components/auth/OtpInput'
import { AuthFrame, FormError, FullScreenSpinner } from '@/components/affiliate/AuthFrame'
import { SignedOutNotice } from '@/components/auth/SignedOutNotice'
import { inputClass, primaryButtonClass } from '@/components/affiliate/ui'

/** Where to go after signing in: `?redirect=` when it points inside the portal. */
function redirectTarget(): string {
  if (typeof window === 'undefined') return '/affiliate'
  const r = new URLSearchParams(window.location.search).get('redirect')
  const ok =
    !!r &&
    (r === '/affiliate' || r.startsWith('/affiliate/') || r.startsWith('/affiliate?')) &&
    !r.startsWith('/affiliate/login') &&
    !r.startsWith('/affiliate/accept-invite')
  return ok ? r! : '/affiliate'
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

type Mode = 'login' | 'forgot' | 'reset'

/**
 * Sign-in for affiliate partners. Its own session: it posts to
 * `/auth/affiliate/login`, which issues a portal-scoped token the customer app
 * refuses, and signing in here does not sign anyone into the product.
 */
export default function AffiliateLoginPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [checking, setChecking] = useState(true)
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [resendIn, setResendIn] = useState(0)

  // Already holding a portal session the server still honours? Skip the form.
  useEffect(() => {
    if (!affiliateAuth.isSignedIn()) {
      setChecking(false)
      return
    }
    affiliateApi
      .me()
      .then(() => router.replace(redirectTarget()))
      .catch(() => {
        // A stored session that no longer works: drop it instead of bouncing.
        clearScope('affiliate')
        setChecking(false)
      })
  }, [router])

  useEffect(() => {
    if (resendIn <= 0) return
    const t = setTimeout(() => setResendIn((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [resendIn])

  const finishSignIn = () => {
    queryClient.clear()
    router.replace(redirectTarget())
  }

  const checkEmail = (): string | null => {
    const trimmed = email.trim()
    if (!trimmed) return 'Enter your email address.'
    if (!EMAIL_RE.test(trimmed)) return 'Enter a valid email address, like you@example.com.'
    return null
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    const bad = checkEmail() || (!password ? 'Enter your password.' : null)
    if (bad) {
      setError(bad)
      return
    }
    setError(null)
    setBusy(true)
    try {
      await affiliateAuth.login(email.trim(), password)
      finishSignIn()
    } catch (err) {
      // The server answers "wrong password" and "not a partner" with the same
      // 401 on purpose, so the wording covers both.
      const status = axios.isAxiosError(err) ? err.response?.status : undefined
      setError(
        status === 401
          ? 'Incorrect email or password, or this account isn’t set up as a partner.'
          : getErrorMessage(err, 'We couldn’t sign you in. Please try again.')
      )
    } finally {
      setBusy(false)
    }
  }

  const sendCode = async () => {
    const bad = checkEmail()
    if (bad) {
      setError(bad)
      return
    }
    setError(null)
    setBusy(true)
    try {
      const res = await affiliateAuth.forgotPassword(email.trim())
      setMode('reset')
      setResendIn(60)
      toast.success(res.message || 'If that email has an account, we’ve sent a reset code to it.')
      if (res.debug_code) {
        setCode(res.debug_code)
        toast.info(`Dev mode — your code is ${res.debug_code}`)
      }
    } catch (err) {
      setError(getErrorMessage(err, 'We couldn’t send the reset code. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault()
    if (code.length < 6) {
      setError('Enter the 6-digit code from your email.')
      return
    }
    if (newPassword.length < 8) {
      setError('Your new password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('The passwords don’t match.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await affiliateAuth.resetPassword(email.trim(), code, newPassword)
    } catch (err) {
      setCode('')
      setError(getErrorMessage(err, 'We couldn’t reset your password. Please try again.'))
      setBusy(false)
      return
    }
    // The password is changed now; a failure from here on must not ask for a new code.
    try {
      await affiliateAuth.login(email.trim(), newPassword)
      toast.success('Password updated — you’re signed in.')
      finishSignIn()
    } catch (err) {
      setMode('login')
      setPassword('')
      setCode('')
      const status = axios.isAxiosError(err) ? err.response?.status : undefined
      setError(
        status === 401
          ? 'Your password was updated, but this account isn’t set up as a partner.'
          : 'Your password was updated. Sign in with your new password.'
      )
    } finally {
      setBusy(false)
    }
  }

  if (checking) return <FullScreenSpinner />

  const labelClass = 'block text-sm font-semibold text-slate-800'
  const spinner = <Loader2 className="h-4 w-4 animate-spin" />

  return (
    <AuthFrame>
      {mode === 'login' && (
        <>
          <h1 className="text-2xl font-bold text-slate-900">Partner sign in</h1>
          <p className="mb-6 mt-1 text-sm text-slate-600">Track your referrals, earnings and payouts.</p>
          <FormError message={error} />
          <SignedOutNotice className="mb-4" />
          <form onSubmit={handleLogin} noValidate className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className={labelClass}>
                Email address
              </label>
              <div className="relative">
                <input
                  id="email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  disabled={busy}
                  className={`${inputClass} pr-10`}
                />
                <Mail className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              </div>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="password" className={labelClass}>
                Password
              </label>
              <PasswordInput
                id="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                disabled={busy}
                className={inputClass}
              />
              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setMode('forgot')
                    setError(null)
                  }}
                  className="text-sm font-medium text-slate-700 underline hover:text-slate-900"
                >
                  Forgot password?
                </button>
              </div>
            </div>
            <button type="submit" disabled={busy} className={`${primaryButtonClass} w-full py-3 text-base`}>
              {busy ? (
                <>
                  {spinner}
                  Signing in…
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
          <p className="mt-6 text-sm text-slate-500">
            New partner? Use the invitation link we emailed you to set up your account.
          </p>
        </>
      )}

      {mode === 'forgot' && (
        <>
          <h1 className="text-2xl font-bold text-slate-900">Forgot your password?</h1>
          <p className="mb-6 mt-1 text-sm text-slate-600">Enter your email and we’ll send you a code to reset it.</p>
          <FormError message={error} />
          <form
            noValidate
            onSubmit={(e) => {
              e.preventDefault()
              sendCode()
            }}
            className="space-y-4"
          >
            <div className="space-y-1.5">
              <label htmlFor="reset-email" className={labelClass}>
                Email address
              </label>
              <input
                id="reset-email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={busy}
                className={inputClass}
              />
            </div>
            <button type="submit" disabled={busy} className={`${primaryButtonClass} w-full py-3 text-base`}>
              {busy ? (
                <>
                  {spinner}
                  Sending code…
                </>
              ) : (
                'Send reset code'
              )}
            </button>
          </form>
        </>
      )}

      {mode === 'reset' && (
        <>
          <h1 className="text-2xl font-bold text-slate-900">Choose a new password</h1>
          <p className="mb-6 mt-1 text-sm text-slate-600">
            Enter the 6-digit code we sent to {email.trim()} and pick a new password.
          </p>
          <FormError message={error} />
          <form onSubmit={handleReset} noValidate className="space-y-4">
            <div className="space-y-1.5">
              <p className={labelClass}>Verification code</p>
              <OtpInput value={code} onChange={setCode} disabled={busy} autoFocus />
              <button
                type="button"
                onClick={sendCode}
                disabled={resendIn > 0 || busy}
                className="pt-1 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {resendIn > 0 ? `Resend in ${resendIn}s` : 'Send a new code'}
              </button>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="new-password" className={labelClass}>
                New password
              </label>
              <PasswordInput
                id="new-password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Choose a new password"
                disabled={busy}
                leftIcon={
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                }
                className={`${inputClass} pl-10`}
              />
              <p className="text-xs text-slate-500">At least 8 characters.</p>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="confirm-password" className={labelClass}>
                Confirm new password
              </label>
              <PasswordInput
                id="confirm-password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your new password"
                disabled={busy}
                leftIcon={
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                }
                className={`${inputClass} pl-10`}
              />
            </div>
            <button type="submit" disabled={busy} className={`${primaryButtonClass} w-full py-3 text-base`}>
              {busy ? (
                <>
                  {spinner}
                  Updating password…
                </>
              ) : (
                'Reset password and sign in'
              )}
            </button>
          </form>
        </>
      )}

      {mode !== 'login' && (
        <button
          type="button"
          onClick={() => {
            setMode('login')
            setError(null)
            setCode('')
          }}
          className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-[#243275] hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to sign in
        </button>
      )}
    </AuthFrame>
  )
}
