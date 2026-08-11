'use client'

/**
 * Compact usage meter for the sidebar.
 *
 * Shows what is left of the allowances that still exist, since running out
 * silently is the worst version of hitting a cap. Paid plans only see it once
 * they cross the warning threshold, so it stays out of the way when there is
 * nothing to act on.
 *
 * Minutes and calls are deliberately absent: no plan limits them any more, so a
 * meter for them would either read "0 / unlimited" or, worse, imply a ceiling
 * that is not enforced. Rows whose cap is unlimited are filtered out below, so
 * adding them back would render nothing regardless.
 */
import { useRouter } from 'next/navigation'

import { LIMITS, LIMIT_LABELS, isUnlimited } from '@/lib/entitlements'
import { useEntitlementStore } from '@/store/entitlementStore'

const WARN_AT = 0.8

// Only limits whose usage the entitlements payload actually carries. Resource
// caps (agents, phone numbers) are counted per-request on the backend and are
// not in `usage`, so listing one here would render a permanent "0 / n".
const TRACKED: string[] = [LIMITS.SMS, LIMITS.EMAILS]

export function UsageMeter({ collapsed = false }: { collapsed?: boolean }) {
  const router = useRouter()
  const entitlements = useEntitlementStore((s) => s.entitlements)

  if (!entitlements || !entitlements.is_live || collapsed) return null

  const rows = TRACKED.map((key) => {
    const cap = entitlements.limits?.[key] ?? 0
    const used = entitlements.usage?.[key] ?? 0
    return { key, cap, used, ratio: cap > 0 ? used / cap : 0 }
  }).filter((row) => !isUnlimited(row.cap) && row.cap > 0)

  if (rows.length === 0) return null

  const worst = Math.max(...rows.map((row) => row.ratio))
  // A paid plan only hears from us when it is close to the line; a trial always
  // sees where it stands, because 60 minutes goes quickly.
  if (!entitlements.is_trial && worst < WARN_AT) return null

  // Styled for the dark sidebar it lives in, not the light page body.
  return (
    <div className="mx-3 mb-2 rounded-xl border border-white/10 bg-white/5 p-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-white/50">
        {entitlements.is_trial ? 'Trial usage' : 'This month'}
      </p>

      <div className="space-y-2.5">
        {rows.map((row) => {
          const pct = Math.min(100, Math.round(row.ratio * 100))
          const bar =
            row.ratio >= 1
              ? 'bg-red-400'
              : row.ratio >= WARN_AT
                ? 'bg-amber-400'
                : 'bg-emerald-300'
          return (
            <div key={row.key}>
              <div className="mb-1 flex items-baseline justify-between text-xs">
                <span className="capitalize text-white/70">
                  {LIMIT_LABELS[row.key] ?? row.key}
                </span>
                <span className="tabular-nums text-white/50">
                  {row.used}/{row.cap}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/15">
                <div className={`h-full rounded-full ${bar}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>

      {worst >= WARN_AT && (
        <button
          onClick={() => router.push('/dashboard/settings/billing')}
          className="mt-3 w-full rounded-lg bg-white/90 px-3 py-1.5 text-xs font-semibold text-emerald-900 transition-colors hover:bg-white"
        >
          {worst >= 1 && !entitlements.overage_allowed
            ? 'Upgrade to keep going'
            : 'Upgrade plan'}
        </button>
      )}
    </div>
  )
}
