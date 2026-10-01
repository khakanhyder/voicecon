/**
 * What a plan card's button should do, given the plan the workspace is on.
 *
 * One rule for every place plans are listed, so a card never says "Get Started"
 * to a workspace that is already paying:
 *
 *   on a paid plan   same plan          → Current Plan (disabled)
 *                    a higher plan      → Upgrade
 *                    a lower plan       → Included in your plan (disabled)
 *   on a trial       every plan         → Subscribe / Upgrade (the trial is free;
 *                                         nothing is owned yet)
 *   no live plan     every plan         → Get Started (expired, cancelled, new)
 *
 * "Lower" is by `tier`, which the admin console sets, so a new top plan or a
 * re-ordered catalog needs no change here. Two different plans on the same tier
 * (a retired launch plan beside a current one) count as a sideways move, offered
 * as an upgrade rather than hidden.
 */
export type PlanAction =
  | 'current'
  | 'keep'
  | 'upgrade'
  | 'included'
  | 'subscribe'
  | 'trial_upgrade'
  | 'get_started'

export interface PlanActionInput {
  planId: string
  planTier: number | null | undefined
  /** The plan the workspace is on, if any. */
  currentPlanId: string | null | undefined
  currentTier: number | null | undefined
  isLive: boolean
  isTrial: boolean
  /** A downgrade is queued for the end of the period. */
  hasScheduledChange?: boolean
}

export function planActionFor(input: PlanActionInput): PlanAction {
  const { planId, planTier, currentPlanId, currentTier, isLive, isTrial, hasScheduledChange } = input

  if (!isLive) return 'get_started'

  const isCurrent = planId === currentPlanId
  if (isTrial) return isCurrent ? 'subscribe' : 'trial_upgrade'

  if (isCurrent) return hasScheduledChange ? 'keep' : 'current'
  return (planTier ?? 0) >= (currentTier ?? 0) ? 'upgrade' : 'included'
}

/** Whether buying this plan would move a paying workspace up. For lists that only offer upgrades. */
export function isUpgradeTarget(input: PlanActionInput): boolean {
  const action = planActionFor(input)
  return action === 'upgrade' || action === 'get_started' || action === 'trial_upgrade' || action === 'subscribe'
}
