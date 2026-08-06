'use client'

/**
 * The upgrade dialog every blocked action funnels into.
 *
 * Mounted once in the dashboard layout. It listens for the
 * `voicecon:entitlement-required` event the API client emits on a 402, so no
 * calling component has to handle billing errors itself — a blocked action
 * anywhere in the product opens this instead of surfacing a raw error toast.
 */
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Lock, X, ArrowRight } from 'lucide-react'

import { EntitlementErrorBody, PLAN_LABELS } from '@/lib/entitlements'

function planLabel(slug: string): string {
  return PLAN_LABELS[slug] ?? slug
}

/** Headline and body tuned to *why* it was blocked, not one generic paywall. */
function copyFor(body: EntitlementErrorBody): { title: string; message: string } {
  switch (body.reason) {
    case 'feature_not_in_plan':
      return {
        title: `${body.feature_label ?? 'This feature'} needs an upgrade`,
        message: body.detail,
      }
    case 'limit_exceeded':
      return {
        title: `You've reached your ${body.limit_label ?? 'plan'} limit`,
        message: body.detail,
      }
    case 'subscription_inactive':
      return {
        title:
          body.status === 'expired'
            ? 'Your access has ended'
            : 'Your subscription needs attention',
        message: body.detail,
      }
    default:
      return { title: 'Upgrade required', message: body.detail }
  }
}

export function UpgradeDialog() {
  const router = useRouter()
  const [blocked, setBlocked] = useState<EntitlementErrorBody | null>(null)

  useEffect(() => {
    const onBlocked = (event: Event) => {
      const detail = (event as CustomEvent<EntitlementErrorBody>).detail
      if (detail?.code === 'entitlement_required') {
        setBlocked(detail)
      }
    }
    window.addEventListener('voicecon:entitlement-required', onBlocked)
    return () =>
      window.removeEventListener('voicecon:entitlement-required', onBlocked)
  }, [])

  if (!blocked) return null

  const { title, message } = copyFor(blocked)
  const suggested = blocked.required_plans?.[0]

  const goToBilling = () => {
    setBlocked(null)
    router.push(blocked.upgrade_url || '/dashboard/settings/billing')
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upgrade-dialog-title"
      onClick={() => setBlocked(null)}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50">
            <Lock className="h-5 w-5 text-brand" />
          </div>
          <button
            onClick={() => setBlocked(null)}
            className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <h2
          id="upgrade-dialog-title"
          className="mt-4 text-lg font-semibold text-slate-900"
        >
          {title}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-600">{message}</p>

        {blocked.limit && blocked.cap !== undefined && (
          <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
            Using <strong>{blocked.used}</strong> of{' '}
            <strong>{blocked.cap === -1 ? 'unlimited' : blocked.cap}</strong>{' '}
            {blocked.limit_label ?? blocked.limit}
            {blocked.current_plan_name ? ` on ${blocked.current_plan_name}` : ''}.
          </p>
        )}

        {suggested && (
          <p className="mt-3 text-sm text-slate-600">
            Available on <strong>{planLabel(suggested)}</strong>.
          </p>
        )}

        <div className="mt-6 flex gap-3">
          <button
            onClick={goToBilling}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
          >
            {suggested ? `Upgrade to ${planLabel(suggested)}` : 'View plans'}
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            onClick={() => setBlocked(null)}
            className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  )
}
