/**
 * Subscription entitlement store.
 *
 * Holds what the current workspace's plan allows, so components can render a
 * feature as locked instead of letting the user click it into a 402. The server
 * enforces the same rules independently — this is presentation only, never the
 * security boundary, exactly like `useWorkspaceStore().can(...)`.
 */
import { create } from 'zustand'

import {
  Entitlements,
  LIMITS,
  entitlementService,
  isUnlimited,
} from '@/lib/entitlements'

interface EntitlementState {
  entitlements: Entitlements | null
  isLoading: boolean
  error: string | null

  /** Load once per session. Safe to call repeatedly. */
  load: () => Promise<void>
  /** Re-read, bypassing the server-side cache. Use right after a checkout. */
  refresh: () => Promise<void>
  reset: () => void

  /** Does the plan include this feature *and* is the account live? */
  has: (feature: string) => boolean
  /** Is there room for `count` more of this limit? */
  within: (limit: string, count?: number) => boolean
  /** Headroom left, or `null` when unlimited. */
  remaining: (limit: string) => number | null
  used: (limit: string) => number
  cap: (limit: string) => number
  /** Fraction of an allowance consumed, or `null` when unlimited/unmetered. */
  ratio: (limit: string) => number | null

  /** Everything the account built stays visible, but nothing runs or changes. */
  isReadOnly: () => boolean
  isLive: () => boolean
}

export const useEntitlementStore = create<EntitlementState>((set, get) => ({
  entitlements: null,
  isLoading: true,
  error: null,

  load: async () => {
    if (get().entitlements) {
      set({ isLoading: false })
      return
    }
    set({ isLoading: true, error: null })
    try {
      const entitlements = await entitlementService.get()
      set({ entitlements, isLoading: false })
    } catch (e: any) {
      set({
        isLoading: false,
        error: e?.response?.data?.detail ?? 'Could not load your plan',
      })
    }
  },

  refresh: async () => {
    try {
      const entitlements = await entitlementService.get(true)
      set({ entitlements, error: null })
    } catch (e: any) {
      set({ error: e?.response?.data?.detail ?? 'Could not load your plan' })
    }
  },

  reset: () => set({ entitlements: null, isLoading: true, error: null }),

  has: (feature: string) => {
    const ent = get().entitlements
    if (!ent) return false
    return ent.is_live && ent.features.includes(feature)
  },

  cap: (limit: string) => get().entitlements?.limits?.[limit] ?? 0,

  used: (limit: string) => get().entitlements?.usage?.[limit] ?? 0,

  remaining: (limit: string) => {
    const { cap, used } = get()
    const capValue = cap(limit)
    if (isUnlimited(capValue)) return null
    return Math.max(0, capValue - used(limit))
  },

  within: (limit: string, count = 1) => {
    const ent = get().entitlements
    if (!ent || !ent.is_live) return false
    const capValue = ent.limits?.[limit] ?? 0
    if (isUnlimited(capValue)) return true
    // A usage allowance on a plan that bills overage never blocks — going past
    // it costs money rather than stopping. A trial has no card, so it does.
    const isUsageLimit = (
      [LIMITS.MINUTES, LIMITS.CALLS, LIMITS.SMS, LIMITS.EMAILS] as string[]
    ).includes(limit)
    if (isUsageLimit && ent.overage_allowed) return true
    return (ent.usage?.[limit] ?? 0) + count <= capValue
  },

  ratio: (limit: string) => {
    const { cap, used } = get()
    const capValue = cap(limit)
    if (capValue <= 0) return null
    return used(limit) / capValue
  },

  isReadOnly: () => get().entitlements?.is_read_only ?? false,
  isLive: () => get().entitlements?.is_live ?? false,
}))

/** Hook-shaped accessor mirroring `useWorkspaceStore().can(...)`. */
export function useEntitlements() {
  const entitlements = useEntitlementStore((s) => s.entitlements)
  const isLoading = useEntitlementStore((s) => s.isLoading)
  const has = useEntitlementStore((s) => s.has)
  const within = useEntitlementStore((s) => s.within)
  const remaining = useEntitlementStore((s) => s.remaining)
  const used = useEntitlementStore((s) => s.used)
  const cap = useEntitlementStore((s) => s.cap)
  const ratio = useEntitlementStore((s) => s.ratio)
  const refresh = useEntitlementStore((s) => s.refresh)

  return {
    entitlements,
    isLoading,
    has,
    within,
    remaining,
    used,
    cap,
    ratio,
    refresh,
    status: entitlements?.status ?? null,
    isTrial: entitlements?.is_trial ?? false,
    isLive: entitlements?.is_live ?? false,
    isReadOnly: entitlements?.is_read_only ?? false,
    daysRemaining: entitlements?.days_remaining ?? null,
    planName: entitlements?.plan_name ?? null,
    planSlug: entitlements?.plan_slug ?? null,
  }
}
