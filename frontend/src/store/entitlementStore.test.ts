/**
 * Unit tests for the entitlement store.
 *
 * `has` and `within` decide whether a feature renders as available or locked.
 * The subtle rule is in `within`: a *usage* allowance on a plan that bills
 * overage must never block — going past it costs money rather than stopping —
 * whereas a trial has no card on file, so for a trial it does block. Getting
 * that backwards either bills a trial it cannot charge, or blocks a paying
 * customer mid-month.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Entitlements } from '@/lib/entitlements'

vi.mock('@/lib/entitlements', async () => {
  const actual = await vi.importActual<typeof import('@/lib/entitlements')>(
    '@/lib/entitlements'
  )
  return { ...actual, entitlementService: { get: vi.fn() } }
})

const { entitlementService } = await import('@/lib/entitlements')
const { useEntitlementStore } = await import('./entitlementStore')

function entitlements(overrides: Partial<Entitlements> = {}): Entitlements {
  return {
    status: 'active',
    plan_id: 'p1',
    plan_slug: 'voice-ai',
    plan_name: 'Voice AI',
    plan_tier: 2,
    source: 'stripe',
    billing_period: 'monthly',
    is_live: true,
    is_read_only: false,
    is_trial: false,
    in_grace: false,
    has_subscription: true,
    trial_end: null,
    days_remaining: null,
    trial_expiring_soon: false,
    grace_period_end: null,
    grace_days_remaining: null,
    current_period_end: null,
    cancel_at_period_end: false,
    features: ['workflows'],
    limits: { agents: 3, minutes_per_month: 1000 },
    usage: { agents: 1, minutes_per_month: 500 },
    overage_allowed: false,
    trial_available: false,
    trial_used: true,
    ...overrides,
  }
}

const store = () => useEntitlementStore.getState()

beforeEach(() => {
  useEntitlementStore.setState({ entitlements: null, isLoading: true, error: null })
  vi.clearAllMocks()
})

describe('load', () => {
  it('fetches and stores the plan', async () => {
    vi.mocked(entitlementService.get).mockResolvedValue(entitlements())

    await store().load()

    expect(store().entitlements?.plan_slug).toBe('voice-ai')
    expect(store().isLoading).toBe(false)
  })

  it('does not refetch once loaded', async () => {
    // Every gated component calls load() on mount; without this guard one page
    // render is a burst of identical requests.
    useEntitlementStore.setState({ entitlements: entitlements() })

    await store().load()

    expect(entitlementService.get).not.toHaveBeenCalled()
    expect(store().isLoading).toBe(false)
  })

  it('surfaces a failure instead of loading forever', async () => {
    vi.mocked(entitlementService.get).mockRejectedValue({
      response: { data: { detail: 'Billing is unavailable' } },
    })

    await store().load()

    expect(store().isLoading).toBe(false)
    expect(store().error).toBe('Billing is unavailable')
  })
})

describe('refresh', () => {
  it('bypasses the server cache', async () => {
    // Called right after checkout, when the cached entitlements are stale by
    // definition.
    vi.mocked(entitlementService.get).mockResolvedValue(entitlements())

    await store().refresh()

    expect(entitlementService.get).toHaveBeenCalledWith(true)
  })

  it('keeps the previous plan when the refresh fails', async () => {
    useEntitlementStore.setState({ entitlements: entitlements({ plan_name: 'Voice AI' }) })
    vi.mocked(entitlementService.get).mockRejectedValue(new Error('offline'))

    await store().refresh()

    expect(store().entitlements?.plan_name).toBe('Voice AI')
  })
})

describe('has', () => {
  it('allows a feature the live plan includes', () => {
    useEntitlementStore.setState({ entitlements: entitlements({ features: ['workflows'] }) })

    expect(store().has('workflows')).toBe(true)
  })

  it('denies a feature the plan does not include', () => {
    useEntitlementStore.setState({ entitlements: entitlements({ features: ['workflows'] }) })

    expect(store().has('white_label')).toBe(false)
  })

  it('denies every feature once the account is not live', () => {
    // An expired account keeps its plan's feature list; `is_live` is what
    // actually gates it, so checking the list alone would leave it unlocked.
    useEntitlementStore.setState({
      entitlements: entitlements({ is_live: false, features: ['workflows'] }),
    })

    expect(store().has('workflows')).toBe(false)
  })

  it('denies everything before the plan has loaded', () => {
    expect(store().has('workflows')).toBe(false)
  })
})

describe('cap, used and remaining', () => {
  it('reports the configured cap and usage', () => {
    useEntitlementStore.setState({ entitlements: entitlements() })

    expect(store().cap('agents')).toBe(3)
    expect(store().used('agents')).toBe(1)
    expect(store().remaining('agents')).toBe(2)
  })

  it('reports zero for a limit the plan does not mention', () => {
    useEntitlementStore.setState({ entitlements: entitlements({ limits: {}, usage: {} }) })

    expect(store().cap('agents')).toBe(0)
    expect(store().used('agents')).toBe(0)
  })

  it('reports null remaining for an unlimited allowance', () => {
    // `null` means "no number to show", which the UI renders as "Unlimited"
    // rather than a progress bar.
    useEntitlementStore.setState({ entitlements: entitlements({ limits: { agents: -1 } }) })

    expect(store().remaining('agents')).toBeNull()
  })

  it('never reports negative headroom', () => {
    // Usage can exceed the cap after an overage month; "-4 left" is not a thing
    // to show a user.
    useEntitlementStore.setState({
      entitlements: entitlements({ limits: { agents: 1 }, usage: { agents: 5 } }),
    })

    expect(store().remaining('agents')).toBe(0)
  })
})

describe('ratio', () => {
  it('reports the fraction consumed', () => {
    useEntitlementStore.setState({
      entitlements: entitlements({ limits: { agents: 4 }, usage: { agents: 1 } }),
    })

    expect(store().ratio('agents')).toBe(0.25)
  })

  it('reports null for an unlimited or unmetered allowance', () => {
    // Guards the divide: a cap of 0 or -1 would give Infinity or a negative.
    useEntitlementStore.setState({ entitlements: entitlements({ limits: { agents: -1 } }) })
    expect(store().ratio('agents')).toBeNull()

    useEntitlementStore.setState({ entitlements: entitlements({ limits: { agents: 0 } }) })
    expect(store().ratio('agents')).toBeNull()
  })
})

describe('within', () => {
  it('allows creating one more below the cap', () => {
    useEntitlementStore.setState({
      entitlements: entitlements({ limits: { agents: 3 }, usage: { agents: 1 } }),
    })

    expect(store().within('agents')).toBe(true)
  })

  it('allows the one that exactly reaches the cap', () => {
    // Off-by-one: with 2 of 3 used, a third agent is allowed.
    useEntitlementStore.setState({
      entitlements: entitlements({ limits: { agents: 3 }, usage: { agents: 2 } }),
    })

    expect(store().within('agents')).toBe(true)
  })

  it('blocks the one that would exceed the cap', () => {
    useEntitlementStore.setState({
      entitlements: entitlements({ limits: { agents: 3 }, usage: { agents: 3 } }),
    })

    expect(store().within('agents')).toBe(false)
  })

  it('accounts for creating several at once', () => {
    useEntitlementStore.setState({
      entitlements: entitlements({ limits: { agents: 3 }, usage: { agents: 1 } }),
    })

    expect(store().within('agents', 2)).toBe(true)
    expect(store().within('agents', 3)).toBe(false)
  })

  it('always allows an unlimited allowance', () => {
    useEntitlementStore.setState({
      entitlements: entitlements({ limits: { agents: -1 }, usage: { agents: 9999 } }),
    })

    expect(store().within('agents')).toBe(true)
  })

  it('does not block a metered allowance when the plan bills overage', () => {
    // Going past the included minutes costs money rather than stopping work.
    useEntitlementStore.setState({
      entitlements: entitlements({
        overage_allowed: true,
        limits: { minutes_per_month: 100 },
        usage: { minutes_per_month: 500 },
      }),
    })

    expect(store().within('minutes_per_month')).toBe(true)
  })

  it('still blocks a metered allowance when overage is not allowed', () => {
    // A trial has no card on file, so there is nothing to bill the overage to.
    useEntitlementStore.setState({
      entitlements: entitlements({
        overage_allowed: false,
        limits: { minutes_per_month: 100 },
        usage: { minutes_per_month: 100 },
      }),
    })

    expect(store().within('minutes_per_month')).toBe(false)
  })

  it('does not extend the overage exemption to structural limits', () => {
    // Overage covers usage (minutes, calls, SMS, email) — not how many agents
    // you may create. A plan that bills overage still caps agents.
    useEntitlementStore.setState({
      entitlements: entitlements({
        overage_allowed: true,
        limits: { agents: 3 },
        usage: { agents: 3 },
      }),
    })

    expect(store().within('agents')).toBe(false)
  })

  it('blocks everything once the account is not live', () => {
    useEntitlementStore.setState({
      entitlements: entitlements({ is_live: false, limits: { agents: 10 }, usage: { agents: 0 } }),
    })

    expect(store().within('agents')).toBe(false)
  })

  it('blocks everything before the plan has loaded', () => {
    expect(store().within('agents')).toBe(false)
  })
})

describe('account state', () => {
  it('reports read-only and live flags', () => {
    useEntitlementStore.setState({
      entitlements: entitlements({ is_read_only: true, is_live: false }),
    })

    expect(store().isReadOnly()).toBe(true)
    expect(store().isLive()).toBe(false)
  })

  it('defaults to not-read-only and not-live before loading', () => {
    // Defaulting isLive to true would briefly render every gated feature as
    // available during the initial load.
    expect(store().isReadOnly()).toBe(false)
    expect(store().isLive()).toBe(false)
  })
})

describe('reset', () => {
  it('clears the plan on sign-out', () => {
    // The next user must not inherit the previous user's entitlements.
    useEntitlementStore.setState({ entitlements: entitlements(), isLoading: false })

    store().reset()

    expect(store().entitlements).toBeNull()
    expect(store().isLoading).toBe(true)
  })
})
