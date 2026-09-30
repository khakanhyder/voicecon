'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Link2Off, Loader2 } from 'lucide-react'
import { affiliateAuth, type InviteInfo } from '@/lib/affiliate'
import { getErrorMessage } from '@/lib/api'
import { PasswordInput } from '@/components/ui/password-input'
import { AuthFrame, FormError, FullScreenSpinner } from '@/components/affiliate/AuthFrame'
import { inputClass, primaryButtonClass } from '@/components/affiliate/ui'

const INVALID_LINK = 'This invitation link is invalid or has expired. Ask us to send a new one.'

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={<FullScreenSpinner />}>
      <AcceptInvite />
    </Suspense>
  )
}

/**
 * `/affiliate/accept-invite?token=` — the link in a partner's invitation email.
 * A new account chooses a password here; an existing one just continues. Either
 * way the partner lands in the portal signed in.
 */
function AcceptInvite() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const token = useSearchParams().get('token') || ''
  const [invite, setInvite] = useState<InviteInfo | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!token) {
      setLoadError(INVALID_LINK)
      return
    }
    let cancelled = false
    affiliateAuth
      .inviteInfo(token)
      .then((info) => {
        if (!cancelled) setInvite(info)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(getErrorMessage(err, INVALID_LINK))
      })
    return () => {
      cancelled = true
    }
  }, [token])

  const accept = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!invite) return
    if (invite.needs_password) {
      if (!password) {
        setError('Choose a password.')
        return
      }
      if (password !== confirm) {
        setError('The passwords don’t match.')
        return
      }
    }
    setError(null)
    setBusy(true)
    try {
      await affiliateAuth.acceptInvite(token, invite.needs_password ? password : undefined)
      queryClient.clear()
      toast.success('Welcome to the VoiceCon partner program!')
      router.replace('/affiliate')
    } catch (err) {
      // The password policy is the server's; its 400 is a sentence for people.
      setError(getErrorMessage(err, 'We couldn’t finish setting up your account. Please try again.'))
      setBusy(false)
    }
  }

  if (loadError) {
    return (
      <AuthFrame>
        <div className="text-center">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
            <Link2Off className="h-6 w-6" />
          </span>
          <h1 className="mt-4 text-xl font-bold text-slate-900">This link can’t be used</h1>
          <p className="mt-2 text-sm text-slate-600">{loadError}</p>
          <p className="mt-4 text-sm text-slate-600">Already set up your account?</p>
          <Link href="/affiliate/login" className={`${primaryButtonClass} mt-3 w-full`}>
            Go to partner sign in
          </Link>
        </div>
      </AuthFrame>
    )
  }

  if (!invite) return <FullScreenSpinner />

  return (
    <AuthFrame>
      <h1 className="text-2xl font-bold text-slate-900">Welcome, {invite.name}</h1>
      <p className="mb-6 mt-1 text-sm text-slate-600">
        {invite.needs_password
          ? 'Choose a password to finish setting up your partner account.'
          : 'Your invitation is ready. Continue to open your partner portal.'}
      </p>
      <FormError message={error} />
      <form onSubmit={accept} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-sm font-semibold text-slate-800">
            Email address
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={invite.email}
            readOnly
            className={`${inputClass} bg-slate-50 text-slate-600`}
          />
        </div>

        {invite.needs_password && (
          <>
            <div className="space-y-1.5">
              <label htmlFor="password" className="block text-sm font-semibold text-slate-800">
                Password
              </label>
              <PasswordInput
                id="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Choose a password"
                disabled={busy}
                className={inputClass}
              />
              <p className="text-xs text-slate-500">At least 8 characters. Avoid common or easily guessed passwords.</p>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="confirm" className="block text-sm font-semibold text-slate-800">
                Confirm password
              </label>
              <PasswordInput
                id="confirm"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter your password"
                disabled={busy}
                className={inputClass}
              />
            </div>
          </>
        )}

        <button type="submit" disabled={busy} className={`${primaryButtonClass} w-full py-3 text-base`}>
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Opening your portal…
            </>
          ) : invite.needs_password ? (
            'Create account and continue'
          ) : (
            'Continue to portal'
          )}
        </button>
      </form>
    </AuthFrame>
  )
}
