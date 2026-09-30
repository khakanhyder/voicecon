'use client'

import Link from 'next/link'
import {
  BadgePercent,
  CheckCircle2,
  Clock,
  DollarSign,
  Info,
  MousePointerClick,
  PauseCircle,
  TrendingUp,
  UserPlus,
  Wallet,
} from 'lucide-react'
import { earnsOnPhrase, money, type AffiliateMe, type Rules } from '@/lib/affiliate'
import { useAffiliateMe } from '@/components/affiliate/useAffiliateMe'
import {
  CopyField,
  Notice,
  PageHeader,
  SectionTitle,
  Skeleton,
  StatCard,
  cardClass,
  primaryButtonClass,
  copyText,
} from '@/components/affiliate/ui'

const iconClass = 'h-4 w-4 text-[#106959]'

function plural(n: number, one: string, many = `${one}s`) {
  return `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`
}

function paymentsLine(max: number | null, kind: 'annual' | 'monthly'): string {
  if (max === null || max === undefined) return `on every ${kind} payment they make, renewals included`
  if (max <= 1) return `on their first ${kind} payment`
  return `on their first ${max} ${kind} payments`
}

function earnLines(rules: Rules): React.ReactNode[] {
  const annual = (
    <>
      You earn <strong>{rules.commission_percent}%</strong> of what the customers you refer pay for{' '}
      <strong>annual plans</strong>, {paymentsLine(rules.max_commission_payments, 'annual')}.
    </>
  )
  const monthly = (
    <>
      You earn <strong>{rules.commission_percent_monthly}%</strong> of what the customers you refer pay for{' '}
      <strong>monthly plans</strong>, {paymentsLine(rules.max_monthly_commission_payments, 'monthly')}.
    </>
  )
  if (rules.billing_periods === 'monthly') return [<>{monthly} Annual plans don’t earn a commission.</>]
  if (rules.billing_periods === 'both') return [annual, monthly]
  return [<>{annual} Monthly plans don’t earn a commission.</>]
}

function HowYouEarn({ rules }: { rules: Rules }) {
  const points: React.ReactNode[] = [
    ...earnLines(rules),
    rules.eligible_plans.length > 0 ? (
      <>Eligible plans: {rules.eligible_plans.join(', ')}.</>
    ) : (
      <>Every plan qualifies when it’s billed {rules.billing_periods === 'monthly' ? 'monthly' : rules.billing_periods === 'both' ? 'monthly or annually' : 'annually'}.</>
    ),
    rules.hold_days > 0 ? (
      <>
        A commission becomes payable <strong>{plural(rules.hold_days, 'day')}</strong> after the customer pays — that’s
        the refund window. If the payment is refunded in that time, the commission is reversed.
      </>
    ) : (
      <>A commission becomes payable as soon as the customer’s payment clears.</>
    ),
    rules.referral_window_days ? (
      <>
        A referred customer needs to make their first commissioned payment within{' '}
        {plural(rules.referral_window_days, 'day')} of signing up for it to count.
      </>
    ) : null,
    rules.cookie_days > 0 ? (
      <>Your link is remembered for {plural(rules.cookie_days, 'day')} after someone clicks it.</>
    ) : null,
    <>
      Payouts are sent once your available balance reaches <strong>{money(rules.min_payout_amount)}</strong>.
    </>,
  ].filter(Boolean)

  return (
    <div className={cardClass}>
      <SectionTitle title="How you earn" />
      <ul className="space-y-3">
        {points.map((p, i) => (
          <li key={i} className="flex gap-3 text-sm text-slate-700">
            <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#106959]" />
            <span>{p}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function CouponCard({ me }: { me: AffiliateMe }) {
  const coupon = me.coupon
  return (
    <div className={cardClass}>
      <SectionTitle title="Your coupon" description="Customers enter it at checkout." />
      {coupon ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => copyText(coupon.code, 'Coupon code copied')}
              title="Copy code"
              className="rounded-lg border-2 border-dashed border-[#106959]/50 bg-[#0F6A590A] px-4 py-2 font-mono text-lg font-bold tracking-wider text-[#106959] transition-colors hover:bg-[#0F6A5914]"
            >
              {coupon.code}
            </button>
          </div>
          <p className="text-sm text-slate-700">
            {coupon.description}
            {coupon.percent_off > 0 && (
              <span className="text-slate-500">
                {' '}
                · {coupon.applies_to === 'all' ? 'All plans' : 'Annual plans only'}
              </span>
            )}
          </p>
          {coupon.percent_off > 0 && !coupon.active && (
            <p className="text-xs text-amber-700">This coupon’s discount isn’t active right now.</p>
          )}
          <p className="text-xs text-slate-500">
            New customers who use your coupon are credited to you, even if they didn’t click your link.
          </p>
        </div>
      ) : (
        <p className="text-sm text-slate-600">No coupon yet — contact us if you’d like one for your audience.</p>
      )}
    </div>
  )
}

function OverviewSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-40" />
    </div>
  )
}

export default function AffiliateOverviewPage() {
  const { data: me } = useAffiliateMe()
  // The shell only renders pages once /me has loaded; this covers a refetch race.
  if (!me) return <OverviewSkeleton />

  const firstName = (me.name || '').split(' ')[0]

  return (
    <div className="space-y-6">
      <PageHeader
        title={firstName ? `Welcome back, ${firstName}` : 'Overview'}
        description="Your referrals, earnings and links at a glance."
      />

      {!me.program_enabled && (
        <Notice tone="warning" icon={<PauseCircle className="h-5 w-5" />} title="The partner program is paused">
          New referrals and commissions aren’t being recorded right now. Everything you’ve already earned is kept, and
          we’ll email you when the program resumes.
        </Notice>
      )}

      {me.stripe.state !== 'ready' && me.stripe.connect_available && (
        <Notice
          tone="info"
          icon={<Wallet className="h-5 w-5" />}
          title={me.stripe.state === 'incomplete' ? 'Finish your payout setup' : 'Set up payouts'}
          action={
            <Link href="/affiliate/payouts" className={primaryButtonClass}>
              {me.stripe.state === 'incomplete' ? 'Finish setup' : 'Set up payouts'}
            </Link>
          }
        >
          Connect a Stripe account so we can send your commissions straight to your bank.
        </Notice>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={<MousePointerClick className={iconClass} />}
          label="Link clicks (30 days)"
          value={me.stats.clicks_30d.toLocaleString('en-US')}
          sub={`${me.stats.clicks.toLocaleString('en-US')} all time`}
        />
        <StatCard
          icon={<UserPlus className={iconClass} />}
          label="Referrals"
          value={me.stats.referrals.toLocaleString('en-US')}
          sub="Sign-ups credited to you"
        />
        <StatCard
          icon={<TrendingUp className={iconClass} />}
          label="Conversions"
          value={me.stats.conversions.toLocaleString('en-US')}
          sub="Referrals that earned you a commission"
        />
        <StatCard
          icon={<Clock className={iconClass} />}
          label="Pending"
          value={money(me.balance.pending)}
          sub="In the refund window"
        />
        <StatCard
          tone="accent"
          icon={<Wallet className={iconClass} />}
          label="Available"
          value={money(me.balance.available)}
          sub={
            me.balance.in_payout > 0
              ? `${money(me.balance.in_payout)} on its way to you`
              : 'Ready for your next payout'
          }
        />
        <StatCard
          icon={<DollarSign className={iconClass} />}
          label="Paid"
          value={money(me.balance.paid)}
          sub="Sent to you so far"
        />
        <StatCard
          icon={<BadgePercent className={iconClass} />}
          label="Commission rate"
          value={
            me.rules.billing_periods === 'monthly'
              ? `${me.rules.commission_percent_monthly}%`
              : me.rules.billing_periods === 'both' && me.rules.commission_percent_monthly !== me.rules.commission_percent
                ? `${me.rules.commission_percent}% / ${me.rules.commission_percent_monthly}%`
                : `${me.rules.commission_percent}%`
          }
          sub={
            me.rules.billing_periods === 'both' && me.rules.commission_percent_monthly !== me.rules.commission_percent
              ? 'Annual / monthly plan payments'
              : `Of ${earnsOnPhrase(me.rules.billing_periods)} payments`
          }
        />
        <StatCard
          icon={<TrendingUp className={iconClass} />}
          label="Lifetime earnings"
          value={money(me.balance.lifetime)}
          sub="Pending, available and paid"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className={cardClass}>
          <SectionTitle title="Your referral link" description="Share it anywhere. Sign-ups through it are credited to you." />
          <div className="space-y-4">
            <CopyField label="Website link" value={me.links.landing} hint="Sends people to the VoiceCon home page." />
            <CopyField label="Direct sign-up link" value={me.links.signup} hint="Skips straight to creating an account." />
            <p className="flex items-center gap-1.5 text-xs text-slate-500">
              <Info className="h-3.5 w-3.5" />
              Your referral code is <span className="font-mono font-semibold text-slate-700">{me.referral_code}</span>
            </p>
          </div>
        </div>
        <CouponCard me={me} />
      </div>

      <HowYouEarn rules={me.rules} />
    </div>
  )
}
