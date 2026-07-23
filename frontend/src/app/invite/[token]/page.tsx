'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams, useParams } from 'next/navigation'
import Link from 'next/link'
import { toast } from 'sonner'
import { Check, X, Mail, ShieldAlert, PartyPopper } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { authService } from '@/lib/auth'
import { VoiceconLogo } from '@/lib/icons'

interface PublicInvitation {
  email: string
  role: string
  status: string
  organization_name: string
  inviter_name: string | null
  expired: boolean
  account_exists: boolean
}

function InviteContent() {
  const params = useParams()
  const token = params.token as string
  const router = useRouter()
  const searchParams = useSearchParams()

  const [invite, setInvite] = useState<PublicInvitation | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<'accepted' | 'rejected' | null>(null)

  const redirectTarget = `/invite/${token}`
  const loggedIn = typeof window !== 'undefined' && authService.isAuthenticated()

  const load = async () => {
    try {
      const { data } = await apiClient.get<PublicInvitation>(API_ENDPOINTS.INVITATION(token))
      setInvite(data)
      return data
    } catch (e) {
      toast.error(getErrorMessage(e))
      return null
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().then((data) => {
      // Email "Decline" link lands here with ?action=reject → auto-decline.
      if (data && data.status === 'pending' && !data.expired && searchParams.get('action') === 'reject') {
        handleReject()
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const handleAccept = async () => {
    if (!loggedIn) {
      // New invitees register; existing accounts sign in. Both return here after.
      const base = invite?.account_exists ? '/login' : '/register'
      router.push(`${base}?redirect=${encodeURIComponent(redirectTarget)}&email=${encodeURIComponent(invite?.email || '')}`)
      return
    }
    setBusy(true)
    try {
      const { data } = await apiClient.post(API_ENDPOINTS.INVITATION_ACCEPT(token))
      setDone('accepted')
      toast.success(data?.message || 'Invitation accepted')
      setTimeout(() => router.push('/dashboard'), 1200)
    } catch (e) {
      toast.error(getErrorMessage(e))
      setBusy(false)
    }
  }

  const handleReject = async () => {
    setBusy(true)
    try {
      await apiClient.post(API_ENDPOINTS.INVITATION_REJECT(token))
      setDone('rejected')
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const Shell = ({ children }: { children: React.ReactNode }) => (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex items-center gap-2">
          <VoiceconLogo className="h-7 w-7" />
          <span className="text-xl font-bold text-slate-900">Voicecon</span>
        </div>
        {children}
      </div>
    </div>
  )

  if (loading) {
    return (
      <Shell>
        <div className="space-y-3">
          <div className="h-6 w-3/4 animate-pulse rounded bg-slate-100" />
          <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
        </div>
      </Shell>
    )
  }

  if (!invite) {
    return (
      <Shell>
        <ShieldAlert className="mb-3 h-10 w-10 text-slate-300" />
        <h1 className="text-xl font-bold text-slate-900">Invitation not found</h1>
        <p className="mt-1 text-sm text-slate-500">This invitation link is invalid or has been removed.</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm font-medium text-blue-600">
          Go to dashboard
        </Link>
      </Shell>
    )
  }

  // Terminal states (post-action or already-resolved / expired).
  const terminalStatus = done ?? (invite.status !== 'pending' || invite.expired ? invite.status : null)
  if (terminalStatus) {
    const map: Record<string, { icon: React.ReactNode; title: string; sub: string }> = {
      accepted: {
        icon: <PartyPopper className="mb-3 h-10 w-10 text-green-500" />,
        title: `Welcome to ${invite.organization_name}!`,
        sub: 'You now have access. Redirecting you to the dashboard…',
      },
      rejected: {
        icon: <X className="mb-3 h-10 w-10 text-slate-400" />,
        title: 'Invitation declined',
        sub: `You've declined the invitation to ${invite.organization_name}.`,
      },
      canceled: {
        icon: <ShieldAlert className="mb-3 h-10 w-10 text-slate-400" />,
        title: 'Invitation canceled',
        sub: 'This invitation was canceled by the organization.',
      },
      expired: {
        icon: <ShieldAlert className="mb-3 h-10 w-10 text-amber-500" />,
        title: 'Invitation expired',
        sub: 'This invitation is no longer valid. Ask an admin to send a new one.',
      },
    }
    const view = map[terminalStatus] ?? map.expired
    return (
      <Shell>
        {view.icon}
        <h1 className="text-xl font-bold text-slate-900">{view.title}</h1>
        <p className="mt-1 text-sm text-slate-500">{view.sub}</p>
        {terminalStatus !== 'accepted' && (
          <Link href="/dashboard" className="mt-4 inline-block text-sm font-medium text-blue-600">
            Go to dashboard
          </Link>
        )}
      </Shell>
    )
  }

  // Pending → show details + actions.
  const inviter = invite.inviter_name || 'Someone'
  return (
    <Shell>
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-50">
        <Mail className="h-6 w-6 text-blue-600" />
      </div>
      <h1 className="text-2xl font-bold text-slate-900">
        Join {invite.organization_name}
      </h1>
      <p className="mt-2 text-sm text-slate-600 leading-relaxed">
        <strong>{inviter}</strong> invited you to join{' '}
        <strong>{invite.organization_name}</strong> as a{' '}
        <span className="font-semibold capitalize">{invite.role}</span>.
      </p>
      <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
        Invitation sent to <span className="font-medium text-slate-700">{invite.email}</span>
      </p>

      {!loggedIn && (
        <p className="mt-4 text-xs text-slate-500">
          {invite.account_exists
            ? `Sign in as ${invite.email} to accept.`
            : `Create an account with ${invite.email} to accept.`}
        </p>
      )}

      <div className="mt-5 flex gap-3">
        <button
          onClick={handleAccept}
          disabled={busy}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          <Check className="h-4 w-4" />
          {loggedIn ? 'Accept invitation' : invite.account_exists ? 'Sign in to accept' : 'Create account to accept'}
        </button>
        <button
          onClick={handleReject}
          disabled={busy}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
        >
          <X className="h-4 w-4" />
          Decline
        </button>
      </div>

      {!loggedIn && !invite.account_exists && (
        <p className="mt-4 text-center text-xs text-slate-400">
          Already have an account?{' '}
          <Link
            href={`/login?redirect=${encodeURIComponent(redirectTarget)}`}
            className="font-medium text-blue-600"
          >
            Sign in
          </Link>
        </p>
      )}
    </Shell>
  )
}

export default function InvitePage() {
  return (
    <Suspense fallback={null}>
      <InviteContent />
    </Suspense>
  )
}
