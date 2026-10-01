/**
 * Getting someone to the plan cards on the billing page.
 *
 * Every "Choose a plan" button means "let me buy one", so they all land on the
 * cards themselves (where the Subscribe buttons are), not on the section
 * heading above them. The dashboard scrolls inside <main>, not the window, so
 * the browser's own #hash scrolling does not reach it — the billing page reads
 * the hash itself, and this does the scrolling.
 */
export const BILLING_PATH = '/dashboard/settings/billing'
export const PLANS_HASH = '#plans'
export const PLAN_CARDS_ID = 'plan-cards'

/** Scroll to the plan cards. Returns false when they are not on this page. */
export function scrollToPlanCards(): boolean {
  const el = document.getElementById(PLAN_CARDS_ID)
  if (!el) return false
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  return true
}
