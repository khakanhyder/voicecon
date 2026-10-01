import { describe, expect, it } from 'vitest'
import { isUpgradeTarget, planActionFor, type PlanActionInput } from './planActions'

const PLANS = [
  { id: 'starter', tier: 1 },
  { id: 'growth', tier: 2 },
  { id: 'scale', tier: 3 },
  { id: 'agency', tier: 4 },
]

const on = (currentId: string | null, extra: Partial<PlanActionInput> = {}) => {
  const current = PLANS.find((p) => p.id === currentId)
  return PLANS.map((p) =>
    planActionFor({
      planId: p.id,
      planTier: p.tier,
      currentPlanId: currentId,
      currentTier: current?.tier ?? 0,
      isLive: currentId !== null,
      isTrial: false,
      ...extra,
    }),
  )
}

describe('planActionFor — a paying workspace', () => {
  it('Starter: Current Plan, then only upgrades', () => {
    expect(on('starter')).toEqual(['current', 'upgrade', 'upgrade', 'upgrade'])
  })

  it('Growth: Starter is not offered, Scale and Agency are upgrades', () => {
    expect(on('growth')).toEqual(['included', 'current', 'upgrade', 'upgrade'])
  })

  it('Scale: only Agency is an upgrade', () => {
    expect(on('scale')).toEqual(['included', 'included', 'current', 'upgrade'])
  })

  it('Agency: Current Plan and no upgrade anywhere', () => {
    expect(on('agency')).toEqual(['included', 'included', 'included', 'current'])
  })

  it('no paying workspace is ever told "Get Started"', () => {
    for (const id of ['starter', 'growth', 'scale', 'agency']) {
      expect(on(id)).not.toContain('get_started')
    }
  })

  it('a queued downgrade offers to keep the current plan', () => {
    expect(on('scale', { hasScheduledChange: true })[2]).toBe('keep')
  })

  it('a retired plan on the same tier as a current one is a sideways move, not a dead end', () => {
    const action = planActionFor({
      planId: 'growth', planTier: 2, currentPlanId: 'voice-ai', currentTier: 2, isLive: true, isTrial: false,
    })
    expect(action).toBe('upgrade')
  })
})

describe('planActionFor — everyone else', () => {
  it('a trial can subscribe to its own plan or move to any other', () => {
    expect(on('growth', { isTrial: true })).toEqual(['trial_upgrade', 'subscribe', 'trial_upgrade', 'trial_upgrade'])
  })

  it('no live plan (new, expired, cancelled) gets Get Started everywhere', () => {
    expect(on(null)).toEqual(['get_started', 'get_started', 'get_started', 'get_started'])
    expect(on('scale', { isLive: false })).toEqual(['get_started', 'get_started', 'get_started', 'get_started'])
  })
})

describe('isUpgradeTarget', () => {
  it('keeps only the plans worth offering to a paying workspace', () => {
    const offered = PLANS.filter((p) =>
      isUpgradeTarget({ planId: p.id, planTier: p.tier, currentPlanId: 'growth', currentTier: 2, isLive: true, isTrial: false }),
    ).map((p) => p.id)
    expect(offered).toEqual(['scale', 'agency'])
  })
})
