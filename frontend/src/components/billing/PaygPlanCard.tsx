'use client'

/**
 * The Pay As You Go card, shown beside the subscription cards wherever plans
 * are listed inside the app.
 *
 * It is a card of its own rather than a fifth column: it has no monthly price
 * to line up with the others, and what its button does depends on where the
 * workspace is coming from —
 *
 *   on Pay As You Go already        → Current plan, and Add credit
 *   a move to it is queued          → says when, and offers to stay
 *   on a paid subscription          → Switch when the paid period ends
 *   a trial, a lapsed or new plan   → Get started (the first top-up starts it)
 */
import { CheckCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/datetime'
import { paygBullets, perMinute, toPricingPlan, type ApiPlan } from '@/lib/pricing'
import type { PaygAction } from '@/lib/planActions'

interface Props {
  plan: ApiPlan & { id: string }
  action: PaygAction
  /** When the queued move takes effect, or when the paid period ends. */
  periodEnd?: string | null
  /** Name of the plan being paid for now, for "Stay on Growth". */
  currentPlanName?: string | null
  canManage: boolean
  busy?: boolean
  /** Open the top-up dialog; `activate` when the top-up also starts the plan. */
  onTopUp: (activate: boolean) => void
  /** Queue the move for the end of the paid period. */
  onSwitch: () => void
  /** Drop a queued move and keep the current subscription. */
  onStay: () => void
  className?: string
}

export function PaygPlanCard({
  plan,
  action,
  periodEnd,
  currentPlanName,
  canManage,
  busy = false,
  onTopUp,
  onSwitch,
  onStay,
  className = '',
}: Props) {
  const pricing = toPricingPlan(plan)
  const bullets = paygBullets(pricing)
  const rate = pricing.prepaid?.per_minute ?? 0
  const current = action === 'current'

  return (
    <div
      data-testid="payg-plan-card"
      className={`flex flex-col gap-5 rounded-[10px] border p-6 lg:flex-row lg:items-center lg:justify-between ${
        current ? 'border-[#106959] bg-[#0F6A590A]' : 'border-slate-200 bg-white'
      } ${className}`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="text-[20px] font-bold font-poppins text-[#000000]">{plan.name}</h3>
          <p className="font-poppins text-black/60">
            <span className="text-[26px] font-bold text-[#000000]">{perMinute(rate)}</span>
            <span className="ml-1 text-sm">/ minute</span>
            <span className="ml-3 rounded bg-green-50 px-2 py-0.5 text-[12px] font-medium text-[#106959]">
              No monthly fee
            </span>
          </p>
        </div>
        {plan.description && (
          <p className="mt-1.5 text-[13px] font-poppins text-black/60">{plan.description}</p>
        )}
        <ul className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {bullets.map((line) => (
            <li key={line} className="flex items-start gap-2.5 text-[14px] font-poppins text-gray-700">
              <CheckCircle className="mt-0.5 h-[18px] w-[18px] flex-shrink-0 text-[#106959]" aria-hidden="true" />
              <span className="leading-tight">{line}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex shrink-0 flex-col gap-2 lg:w-[230px]">
        {action === 'current' ? (
          <>
            <Button disabled className="h-[45px] w-full font-poppins text-sm rounded-[8px]">
              Current Plan
            </Button>
            {canManage && (
              <Button
                variant="outline"
                className="h-[45px] w-full font-poppins text-sm rounded-[8px]"
                onClick={() => onTopUp(false)}
                disabled={busy}
              >
                Add credit
              </Button>
            )}
          </>
        ) : action === 'scheduled' ? (
          <>
            <p className="text-center text-[13px] font-poppins text-amber-700">
              Starts {periodEnd ? `on ${formatDate(periodEnd)}` : 'when your paid period ends'}
            </p>
            {canManage && (
              <>
                <Button
                  className="h-[45px] w-full font-poppins text-sm rounded-[8px] bg-[#106959] hover:bg-[#0c5044] text-white"
                  onClick={() => onTopUp(false)}
                  disabled={busy}
                >
                  Add credit
                </Button>
                <Button
                  variant="outline"
                  className="h-[45px] w-full font-poppins text-sm rounded-[8px]"
                  onClick={onStay}
                  disabled={busy}
                >
                  Stay on {currentPlanName ?? 'my plan'}
                </Button>
              </>
            )}
          </>
        ) : !canManage ? (
          // The API would refuse it (403); say why before a card is typed.
          <Button disabled variant="outline" className="h-[45px] w-full font-poppins text-sm rounded-[8px]">
            Owner only
          </Button>
        ) : action === 'switch' ? (
          <>
            <Button
              variant="outline"
              className="h-[45px] w-full font-poppins text-sm rounded-[8px]"
              onClick={onSwitch}
              disabled={busy}
            >
              Switch to {plan.name}
            </Button>
            <p className="text-center text-[12px] font-poppins text-black/50">
              Takes effect when your paid period ends{periodEnd ? `, on ${formatDate(periodEnd)}` : ''}.
            </p>
          </>
        ) : (
          <Button
            className="h-[45px] w-full font-poppins text-sm rounded-[8px] bg-[#106959] hover:bg-[#0c5044] text-white shadow-sm"
            onClick={() => onTopUp(true)}
            disabled={busy}
          >
            Get Started
          </Button>
        )}
      </div>
    </div>
  )
}
