'use client'

/**
 * The single billing banner at the top of the dashboard.
 *
 * Exactly one banner is ever shown, chosen by severity in
 * `billingBanner()` — expired beats past-due beats expiring beats trial.
 * Stacked billing banners get ignored wholesale, so the rule is one or none.
 *
 * The banners that mean "your product has stopped working" are deliberately not
 * dismissible; the softer ones can be dismissed for the session.
 */
import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AlertTriangle, Clock, Info, X } from 'lucide-react'

import { billingBanner, BannerTone } from '@/lib/entitlements'
import { useEntitlementStore } from '@/store/entitlementStore'

const TONES: Record<
  BannerTone,
  { wrapper: string; icon: string; button: string; Icon: typeof Info }
> = {
  info: {
    wrapper: 'bg-brand-50 border-brand-100 text-brand-900',
    icon: 'text-brand',
    button: 'bg-brand text-white hover:bg-brand-600',
    Icon: Clock,
  },
  warning: {
    wrapper: 'bg-amber-50 border-amber-200 text-amber-900',
    icon: 'text-amber-600',
    button: 'bg-amber-600 text-white hover:bg-amber-700',
    Icon: AlertTriangle,
  },
  danger: {
    wrapper: 'bg-red-50 border-red-200 text-red-900',
    icon: 'text-red-600',
    button: 'bg-red-600 text-white hover:bg-red-700',
    Icon: AlertTriangle,
  },
}

const DISMISS_KEY = 'voicecon:dismissed-billing-banner'

export function BillingBanner() {
  const router = useRouter()
  const entitlements = useEntitlementStore((s) => s.entitlements)
  const [dismissed, setDismissed] = useState<string | null>(null)

  useEffect(() => {
    setDismissed(sessionStorage.getItem(DISMISS_KEY))
  }, [])

  const banner = useMemo(() => billingBanner(entitlements), [entitlements])

  if (!banner) return null
  if (banner.dismissible && dismissed === banner.key) return null

  const tone = TONES[banner.tone]
  const { Icon } = tone

  const dismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, banner.key)
    setDismissed(banner.key)
  }

  return (
    // The outer padding mirrors the dashboard content container's `p-4 md:p-5`
    // so the banner lines up with the cards below it rather than running
    // edge-to-edge. It stays outside the scroll area, so it remains visible
    // while the page scrolls.
    <div className="px-4 pt-4 md:px-5 md:pt-5">
      {/* `rounded-xl border p-4` matches the System Status card on Analytics,
          so the two read as the same kind of object rather than one being
          page chrome and the other a card. */}
      <div
        className={`flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border p-4 ${tone.wrapper}`}
      >
        <Icon className={`h-4 w-4 shrink-0 ${tone.icon}`} aria-hidden />
        <p className="min-w-0 flex-1 text-sm">
          <span className="font-semibold">{banner.title}</span>
          <span className="ml-2 opacity-90">{banner.body}</span>
        </p>
        <button
          onClick={() => router.push('/dashboard/settings/billing')}
          className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${tone.button}`}
        >
          {banner.cta}
        </button>
        {banner.dismissible && (
          <button
            onClick={dismiss}
            className="shrink-0 rounded p-1 opacity-60 transition-opacity hover:opacity-100"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )
}
