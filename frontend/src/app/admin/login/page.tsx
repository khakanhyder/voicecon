'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { ShieldCheck } from 'lucide-react'
import { authService } from '@/lib/auth'
import { adminApi } from '@/lib/admin'
import { getErrorMessage } from '@/lib/api'
import { useAdminSession } from '@/hooks/useAdminSession'
import { PasswordInput } from '@/components/ui/password-input'

/**
 * Sign-in for Voicecon staff. Deliberately bare: no sign-up, social login or
 * password reset.
 *
 * This is its own sign-in, not the app's with an extra check: it posts to
 * `/auth/admin/login`, which issues an admin-scoped token the customer app's
 * endpoints refuse. Nothing here touches the app's session, so signing in as
 * staff does not sign the person into the product — and being signed into the
 * product does not get them in here.
 */

function redirectTarget(): string {
  if (typeof window === 'undefined') return '/admin'
  const r = new URLSearchParams(window.location.search).get('redirect')
  return r && r.startsWith('/admin') && r !== '/admin/login' ? r : '/admin'
}

const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-brand-500 focus:ring-3 focus:ring-brand-500/15 disabled:cursor-not-allowed disabled:opacity-60'

export default function AdminLoginPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { isAuthenticated, isLoading, sync } = useAdminSession()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [checking, setChecking] = useState(true)

  // Already holding a console session? Skip the form. A customer session in
  // this browser is irrelevant here and never counts as being signed in.
  useEffect(() => {
    if (isLoading) return
    if (!isAuthenticated) {
      setChecking(false)
      return
    }
    adminApi
      .me()
      .then(() => router.replace(redirectTarget()))
      .catch(() => {
        // A stored session the server no longer honours: drop it rather than
        // leaving the page bouncing between the form and a failing check.
        authService.clearSession('admin')
        setChecking(false)
      })
  }, [isAuthenticated, isLoading, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = email.trim()
    if (!trimmed || !password) {
      setError('Enter your email and password.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      // The endpoint itself refuses a non-admin account, so there is no window
      // in which a customer session exists and has to be cleaned up again.
      await authService.adminLogin({ email: trimmed, password })
      queryClient.clear()
      sync()
      router.replace(redirectTarget())
    } catch (err) {
      // One message for both "wrong password" and "not an admin". The server
      // answers both with the same 401 on purpose — which of the two it is is
      // not something an anonymous caller should be able to tell apart — and
      // the wording has to cover both without picking one.
      const status = axios.isAxiosError(err) ? err.response?.status : undefined
      setError(
        status === 401
          ? 'Incorrect email or password, or this account does not have admin access.'
          : getErrorMessage(err) || 'Sign-in failed.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading || checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-white/10 border-t-brand-400" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-white">Voicecon</p>
            <p className="text-[11px] uppercase tracking-wider text-slate-400">Admin Console</p>
          </div>
        </div>

        <div className="rounded-2xl bg-white p-6 shadow-2xl sm:p-8">
          <h1 className="text-xl font-semibold text-slate-900">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Restricted to Voicecon platform administrators.</p>

          <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={submitting}
                className={inputClass}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                Password
              </label>
              <PasswordInput
                id="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                className={`${inputClass} pr-11`}
              />
            </div>

            {error && (
              <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
