'use client'

/**
 * Components for showing what a plan does *not* include.
 *
 * The rule everywhere: **never hide a gated feature — show it locked.** A
 * hidden feature cannot be sold; a greyed-out row with "Available on Voice AI"
 * is an advertisement, and an absent one is a lost sale.
 */
import { ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { Lock } from 'lucide-react'

import { FEATURE_LABELS, PLAN_LABELS } from '@/lib/entitlements'
import { useEntitlementStore } from '@/store/entitlementStore'

interface GatedProps {
  /** Feature key from `FEATURES`. */
  feature: string
  /** Plan that unlocks it, for the tooltip and the CTA. */
  requiredPlan?: string
  children: ReactNode
  /** Rendered instead of the lock overlay when the feature is unavailable. */
  fallback?: ReactNode
}

/**
 * Renders `children` when the plan includes `feature`; otherwise dims them and
 * lays a lock over the top, so the feature stays visible and clickable-looking
 * but leads to the upgrade page.
 */
export function Gated({ feature, requiredPlan, children, fallback }: GatedProps) {
  const router = useRouter()
  const has = useEntitlementStore((s) => s.has)
  const isLoading = useEntitlementStore((s) => s.isLoading)

  // Don't flash a lock while entitlements are still loading — a paying customer
  // seeing "upgrade" for half a second is worse than a brief unstyled render.
  if (isLoading || has(feature)) return <>{children}</>
  if (fallback) return <>{fallback}</>

  const label = FEATURE_LABELS[feature] ?? feature
  const planName = requiredPlan ? (PLAN_LABELS[requiredPlan] ?? requiredPlan) : null

  return (
    <div className="group relative">
      <div className="pointer-events-none select-none opacity-40 grayscale" aria-hidden>
        {children}
      </div>
      <button
        onClick={() => router.push('/dashboard/settings/billing')}
        className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 rounded-lg bg-white/60 backdrop-blur-[1px] transition-colors hover:bg-white/75"
        title={
          planName
            ? `${label} is available on ${planName}`
            : `${label} is not included in your plan`
        }
      >
        <span className="flex items-center gap-1.5 rounded-full bg-slate-900/85 px-3 py-1.5 text-xs font-semibold text-white">
          <Lock className="h-3 w-3" />
          {planName ? `Available on ${planName}` : 'Upgrade to unlock'}
        </span>
      </button>
    </div>
  )
}

/** Inline lock chip, for a menu item or list row that must stay compact. */
export function LockedChip({
  feature,
  requiredPlan,
}: {
  feature: string
  requiredPlan?: string
}) {
  const has = useEntitlementStore((s) => s.has)
  if (has(feature)) return null

  const planName = requiredPlan ? (PLAN_LABELS[requiredPlan] ?? requiredPlan) : null
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500"
      title={planName ? `Available on ${planName}` : 'Not included in your plan'}
    >
      <Lock className="h-2.5 w-2.5" />
      {planName ?? 'Locked'}
    </span>
  )
}

/**
 * Disables an action while the workspace is read-only (expired or cancelled),
 * keeping it visible with an explanatory tooltip rather than removing it.
 */
export function ReadOnlyGuard({
  children,
  message = 'Your subscription has ended — this workspace is read-only.',
}: {
  children: ReactNode
  message?: string
}) {
  const isReadOnly = useEntitlementStore((s) => s.entitlements?.is_read_only ?? false)
  if (!isReadOnly) return <>{children}</>

  return (
    <div
      className="pointer-events-none cursor-not-allowed opacity-50"
      title={message}
      aria-disabled
    >
      {children}
    </div>
  )
}
