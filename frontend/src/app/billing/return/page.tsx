'use client'

/**
 * Where Polar's hosted checkout sends the customer after paying.
 *
 * Payment and activation are separate: Polar charges the card, then tells the
 * backend by webhook, usually within a few seconds. This page waits for that
 * webhook to land (polling the checkout status) before moving on, so the
 * customer arrives on a dashboard that already shows the paid plan.
 */
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { CheckCircle2, Clock, XCircle } from 'lucide-react'
import { authService } from '@/lib/auth'
import { billingService, type CheckoutStatus } from '@/lib/billing'
import { VoiceconLogo } from '@/lib/icons'
import { useEntitlementStore } from '@/store/entitlementStore'
import { useOnboardingStore } from '@/store/onboardingStore'

const POLL_MS = 2000
const GIVE_UP_AFTER_MS = 90_000
/** A checkout can read `open` for a moment after paying, before it settles. */
const OPEN_GRACE_MS = 10_000

type View = 'waiting' | 'active' | 'slow' | 'failed' | 'unpaid' | 'error'

function safeNext(value: string | null): string {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : '/dashboard'
}

export default function BillingReturnPage() {
  const router = useRouter()
  const [view, setView] = useState<View>('waiting')
  const [next, setNext] = useState('/dashboard')

  // Re-running (React strict mode mounts twice in development) is safe: the
  // cleanup cancels the earlier poll loop.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const checkoutId = params.get('checkout_id')
    const target = safeNext(params.get('next'))
    setNext(target)

    if (!authService.isAuthenticated()) {
      router.replace(`/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`)
      return
    }
    if (!checkoutId) {
      setView('error')
      return
    }

    let cancelled = false
    const startedAt = Date.now()

    const finishUp = async () => {
      await useEntitlementStore.getState().refresh().catch(() => undefined)
      // Leaving onboarding through a hosted checkout: close the flow here, as
      // the in-app card path does after a successful payment.
      const onboarding = useOnboardingStore.getState()
      if (onboarding.selectedPlan) onboarding.finish()
      setView('active')
      setTimeout(() => router.replace(target), 1200)
    }

    const tick = async () => {
      if (cancelled) return
      let status: CheckoutStatus | null = null
      try {
        status = await billingService.checkoutStatus(checkoutId)
      } catch {
        status = null // transient; keep waiting until the deadline
      }
      if (cancelled) return
      if (status === 'active') return void finishUp()
      if (status === 'failed' || status === 'expired') return setView('failed')
      const waited = Date.now() - startedAt
      // Still open after a grace moment: the customer came back without paying.
      if (status === 'open' && waited > OPEN_GRACE_MS) return setView('unpaid')
      if (waited > GIVE_UP_AFTER_MS) return setView('slow')
      setTimeout(tick, POLL_MS)
    }
    tick()

    return () => {
      cancelled = true
    }
  }, [router])

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-xl shadow-slate-200/60">
        <div className="mb-6 flex items-center justify-center gap-2">
          <VoiceconLogo className="h-7 w-7" />
          <span className="text-lg font-bold text-slate-900">Voicecon</span>
        </div>

        {view === 'waiting' && (
          <>
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
            <h1 className="mt-5 text-xl font-semibold text-slate-900">Confirming your payment…</h1>
            <p className="mt-2 text-sm text-slate-500">This usually takes a few seconds. Please keep this page open.</p>
          </>
        )}

        {view === 'active' && (
          <>
            <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
            <h1 className="mt-5 text-xl font-semibold text-slate-900">You&apos;re all set</h1>
            <p className="mt-2 text-sm text-slate-500">Your subscription is active. Taking you back…</p>
          </>
        )}

        {view === 'slow' && (
          <>
            <Clock className="mx-auto h-12 w-12 text-amber-500" />
            <h1 className="mt-5 text-xl font-semibold text-slate-900">Payment received</h1>
            <p className="mt-2 text-sm text-slate-500">
              Activating your plan is taking longer than usual. It will switch on automatically within a
              few minutes. You don&apos;t need to pay again.
            </p>
            <Link href={next} className="mt-6 inline-flex h-10 items-center rounded-lg bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700">
              Continue
            </Link>
          </>
        )}

        {(view === 'failed' || view === 'unpaid' || view === 'error') && (
          <>
            <XCircle className="mx-auto h-12 w-12 text-rose-500" />
            <h1 className="mt-5 text-xl font-semibold text-slate-900">
              {view === 'unpaid' ? 'Payment not completed' : view === 'failed' ? 'Payment failed' : 'Something went wrong'}
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              {view === 'error'
                ? 'We could not find this checkout. If you were charged, your plan will still activate automatically.'
                : 'You have not been charged. You can try again whenever you are ready.'}
            </p>
            <Link
              href="/dashboard/settings/billing"
              className="mt-6 inline-flex h-10 items-center rounded-lg bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700"
            >
              Back to billing
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
