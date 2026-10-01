import type { Metadata } from 'next'
import { BadgePercent, ClipboardCheck, Link2, Wallet } from 'lucide-react'
import { MarketingShell } from '@/components/landing/MarketingShell'
import { AffiliateApplicationForm } from '@/components/landing/AffiliateApplicationForm'
import { Accent, Eyebrow, GlassCard, IconWell } from '@/components/landing/primitives'
import { LEGAL } from '@/lib/legal'

export const metadata: Metadata = {
  metadataBase: new URL(LEGAL.website),
  title: 'Affiliate Program | Voicecon',
  description:
    'Refer businesses to Voicecon and earn a commission on the plans they buy. Apply to become an affiliate partner.',
  alternates: { canonical: '/affiliate-program' },
}

// Only what the program really does: terms are set per affiliate, so no rate is promised here.
const STEPS = [
  {
    icon: ClipboardCheck,
    title: 'Apply',
    body: 'Send the form. Our team reviews every request and emails you when your account is ready.',
  },
  {
    icon: Link2,
    title: 'Share your link',
    body: 'Your partner portal gives you a personal referral link, and a coupon code where your terms include one.',
  },
  {
    icon: BadgePercent,
    title: 'Earn commission',
    body: 'You earn a commission when a business you referred pays for a Voicecon plan. Your rate and terms are agreed with you when you are approved.',
  },
  {
    icon: Wallet,
    title: 'Get paid',
    body: 'Track referrals and earnings in the portal, and connect a Stripe account there to receive payouts.',
  },
]

/**
 * Public "Affiliate Program" page, linked from the footer: what the program is
 * and the form that sends a request to the admin console.
 */
export default function AffiliateProgramPage() {
  return (
    <MarketingShell>
      <div className="px-4 pb-20 pt-32 sm:px-6 md:pb-28 md:pt-40">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-12 lg:grid-cols-[1fr_1.05fr] lg:gap-16">
          <div className="min-w-0">
            <Eyebrow>Affiliate program</Eyebrow>
            <h1 className="mt-5 text-balance text-[clamp(2.25rem,5.5vw,3.5rem)] font-bold leading-[1.08] tracking-[-0.025em] text-white">
              Refer businesses to Voicecon and <Accent>earn commission</Accent>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-white/65 sm:text-lg">
              If your audience runs on phone calls, introduce them to AI voice agents and get paid when they
              subscribe. Tell us about yourself and we&apos;ll review your request.
            </p>

            <ol className="mt-10 space-y-6">
              {STEPS.map((step) => (
                <li key={step.title} className="flex gap-4">
                  <IconWell>
                    <step.icon className="h-5 w-5" aria-hidden="true" />
                  </IconWell>
                  <div className="min-w-0">
                    <h2 className="text-base font-semibold text-white">{step.title}</h2>
                    <p className="mt-1 text-[15px] leading-relaxed text-white/60">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>

            <p className="mt-10 text-sm text-white/55">
              Already a partner?{' '}
              <a
                href="/affiliate/login"
                className="font-medium text-brand-200 underline decoration-brand-300/40 underline-offset-4 hover:decoration-brand-200"
              >
                Sign in to the affiliate portal
              </a>
            </p>
          </div>

          <div className="min-w-0 lg:pt-2">
            <GlassCard interactive={false} className="p-6 sm:p-8">
              <h2 className="text-xl font-semibold text-white">Apply to join</h2>
              <p className="mb-6 mt-1.5 text-sm leading-relaxed text-white/60">
                It takes about a minute. We reply by email.
              </p>
              <AffiliateApplicationForm />
            </GlassCard>
          </div>
        </div>
      </div>
    </MarketingShell>
  )
}
