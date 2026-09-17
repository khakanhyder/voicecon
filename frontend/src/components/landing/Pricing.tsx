'use client'

import { useState } from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Accent, ROUTES, Section, SectionHeading, buttonClass } from './primitives'
import { Reveal } from './Reveal'

/**
 * Mirrors the plans seeded in backend/app/services/billing/seed_plans.py and
 * the 30-day trial. Keep these in step when plan prices or limits change.
 */
const PLANS = [
  {
    name: 'Free trial',
    monthly: 0,
    yearly: 0,
    blurb: 'Build and test a working agent before you pay.',
    cta: 'Start free trial',
    features: [
      '30 days, no credit card required',
      '1 agent, 1 knowledge base, 2 workflows',
      'Up to 2 team members',
      'Unlimited test calls and minutes',
      'Every agent and workflow template',
    ],
  },
  {
    name: 'Sales Chatbot',
    monthly: 119,
    yearly: 1071,
    blurb: 'For a team putting its first agents on the phone.',
    cta: 'Get started',
    featured: false,
    features: [
      'Up to 10 agents, phone numbers and workflows',
      '10 knowledge bases and 10 team members',
      'Inbound and outbound calls',
      'Unlimited calls & minutes, 600 texts and 2,500 emails a month',
      'CRM integrations, workflows and webhooks',
      'Call recordings and analytics',
    ],
  },
  {
    name: 'Voice AI',
    monthly: 359,
    yearly: 3231,
    blurb: 'For businesses running many agents across several teams.',
    cta: 'Get started',
    featured: true,
    features: [
      'Everything in Sales Chatbot',
      'Up to 30 agents, phone numbers and workflows',
      '30 knowledge bases and 30 team members',
      'Scheduled workflows (hourly, daily, cron)',
      'Unlimited calls & minutes, 1,000 texts and 5,000 emails a month',
      'Up to 200 API keys',
    ],
  },
]

const usd = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 })

export function Pricing() {
  const [yearly, setYearly] = useState(false)

  return (
    <Section id="pricing" labelledBy="pricing-title">
      <SectionHeading
        id="pricing-title"
        eyebrow="Pricing"
        title={
          <>
            Simple plans that <Accent>grow with you</Accent>
          </>
        }
        description="Start free for 30 days. Choose a plan when you are ready to go live."
      />

      <Reveal className="mt-10 flex justify-center">
        <div role="radiogroup" aria-label="Billing period" className="inline-flex rounded-full border border-white/10 bg-white/[0.04] p-1">
          {[
            { value: false, label: 'Monthly' },
            { value: true, label: 'Yearly' },
          ].map((opt) => (
            <button
              key={opt.label}
              type="button"
              role="radio"
              aria-checked={yearly === opt.value}
              onClick={() => setYearly(opt.value)}
              className={cn(
                'flex items-center gap-2 rounded-full px-5 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200',
                yearly === opt.value ? 'bg-white text-[#10302f]' : 'text-white/70 hover:text-white'
              )}
            >
              {opt.label}
              {opt.value && (
                <span
                  className={cn(
                    'rounded-full px-2 py-0.5 text-[11px] font-bold',
                    yearly ? 'bg-brand-500 text-white' : 'bg-brand-500/20 text-brand-200'
                  )}
                >
                  Save 25%
                </span>
              )}
            </button>
          ))}
        </div>
      </Reveal>

      <div className="mt-10 grid items-stretch gap-5 lg:grid-cols-3">
        {PLANS.map((plan, i) => {
          const perMonth = yearly ? plan.yearly / 12 : plan.monthly
          return (
            <Reveal key={plan.name} delay={i * 90}>
              <div
                className={cn(
                  'relative flex h-full flex-col rounded-3xl border p-7 sm:p-8',
                  plan.featured
                    ? 'border-brand-300/50 bg-gradient-to-b from-brand-500/25 to-white/[0.03] shadow-[0_30px_80px_-30px_rgba(47,155,126,0.55)]'
                    : 'border-white/[0.08] bg-gradient-to-b from-white/[0.06] to-white/[0.02]'
                )}
              >
                {plan.featured && (
                  <span className="absolute -top-3 left-7 rounded-full bg-gradient-to-r from-brand-400 to-brand-600 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.08em] text-white">
                    Most complete
                  </span>
                )}
                <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-white/60">{plan.blurb}</p>
                <p className="mt-6 flex items-end gap-1.5">
                  <span className="text-[2.75rem] font-bold leading-none tracking-[-0.02em] text-white">
                    ${usd(perMonth)}
                  </span>
                  <span className="pb-1 text-sm text-white/55">{plan.monthly ? '/ month' : 'for 30 days'}</span>
                </p>
                <p className="mt-2 h-5 text-xs text-white/50" aria-live="polite">
                  {plan.monthly ? (yearly ? `$${usd(plan.yearly)} billed yearly` : 'Billed monthly') : ''}
                </p>
                <a
                  href={ROUTES.register}
                  className={buttonClass(plan.featured ? 'primary' : 'ghost', 'md', 'mt-6 w-full')}
                >
                  {plan.cta}
                </a>
                <ul className="mt-7 space-y-3 border-t border-white/[0.08] pt-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-[15px] leading-snug text-white/75">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          )
        })}
      </div>
      <p className="mt-8 text-center text-sm text-white/50">
        Prices in USD. Secure checkout by Stripe, and promo codes are applied at checkout.
      </p>
    </Section>
  )
}
