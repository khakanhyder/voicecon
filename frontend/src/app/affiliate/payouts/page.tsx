'use client'

import { Suspense, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Banknote, CheckCircle2, Clock, ExternalLink, Loader2, RefreshCw, Wallet } from 'lucide-react'
import { affiliateApi, formatDate, money, type AffiliateMe } from '@/lib/affiliate'
import { getErrorMessage } from '@/lib/api'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { AFFILIATE_ME_KEY, useAffiliateMe } from '@/components/affiliate/useAffiliateMe'
import {
  Badge,
  EmptyState,
  LoadError,
  PageHeader,
  Pagination,
  SectionTitle,
  Skeleton,
  StatCard,
  Table,
  TableSkeleton,
  cardClass,
  primaryButtonClass,
  secondaryButtonClass,
  tdClass,
  type BadgeTone,
} from '@/components/affiliate/ui'

/** Countries where Stripe Connect Express accounts can receive payouts (common ones first). */
const COUNTRIES: [string, string][] = [
  ['US', 'United States'],
  ['GB', 'United Kingdom'],
  ['CA', 'Canada'],
  ['AU', 'Australia'],
  ['NZ', 'New Zealand'],
  ['IE', 'Ireland'],
  ['DE', 'Germany'],
  ['FR', 'France'],
  ['ES', 'Spain'],
  ['IT', 'Italy'],
  ['NL', 'Netherlands'],
  ['BE', 'Belgium'],
  ['AT', 'Austria'],
  ['CH', 'Switzerland'],
  ['SE', 'Sweden'],
  ['NO', 'Norway'],
  ['DK', 'Denmark'],
  ['FI', 'Finland'],
  ['PT', 'Portugal'],
  ['PL', 'Poland'],
  ['CZ', 'Czech Republic'],
  ['GR', 'Greece'],
  ['LU', 'Luxembourg'],
  ['RO', 'Romania'],
  ['BG', 'Bulgaria'],
  ['HU', 'Hungary'],
  ['HR', 'Croatia'],
  ['SI', 'Slovenia'],
  ['SK', 'Slovakia'],
  ['LT', 'Lithuania'],
  ['LV', 'Latvia'],
  ['EE', 'Estonia'],
  ['CY', 'Cyprus'],
  ['MT', 'Malta'],
  ['SG', 'Singapore'],
  ['HK', 'Hong Kong'],
  ['JP', 'Japan'],
  ['AE', 'United Arab Emirates'],
  ['IN', 'India'],
  ['MY', 'Malaysia'],
  ['TH', 'Thailand'],
  ['PH', 'Philippines'],
  ['ID', 'Indonesia'],
  ['IL', 'Israel'],
  ['TR', 'Turkey'],
  ['MX', 'Mexico'],
  ['BR', 'Brazil'],
  ['AR', 'Argentina'],
  ['CL', 'Chile'],
  ['CO', 'Colombia'],
  ['PE', 'Peru'],
  ['ZA', 'South Africa'],
  ['NG', 'Nigeria'],
  ['KE', 'Kenya'],
  ['PK', 'Pakistan'],
]

const PAYOUT_STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  paid: { label: 'Paid', tone: 'green' },
  processing: { label: 'Processing', tone: 'blue' },
  failed: { label: 'Delayed — we’ll retry', tone: 'amber' },
}

const METHOD_LABELS: Record<string, string> = { stripe: 'Stripe', manual: 'Manual' }

export default function AffiliatePayoutsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64" />}>
      <Payouts />
    </Suspense>
  )
}

function Payouts() {
  const { data: me } = useAffiliateMe()
  const [page, setPage] = useState(1)
  const history = useQuery({
    queryKey: ['affiliate', 'payouts', page],
    queryFn: () => affiliateApi.payouts(page),
    placeholderData: keepPreviousData,
  })

  useStripeReturn()

  if (!me) return <Skeleton className="h-64" />

  return (
    <div className="space-y-6">
      <PageHeader title="Payouts" description="Where your commissions are sent, and what you’ve been paid." />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          tone="accent"
          icon={<Wallet className="h-4 w-4 text-[#106959]" />}
          label="Available"
          value={money(me.balance.available)}
          sub={
            me.balance.in_payout > 0
              ? `${money(me.balance.in_payout)} more on its way to you`
              : 'Ready for your next payout'
          }
        />
        <StatCard
          icon={<Clock className="h-4 w-4 text-[#106959]" />}
          label="Pending"
          value={money(me.balance.pending)}
          sub="Still in the refund window"
        />
        <StatCard
          icon={<Banknote className="h-4 w-4 text-[#106959]" />}
          label="Paid to date"
          value={money(me.balance.paid)}
        />
      </div>
      <p className="-mt-2 text-sm text-slate-600">
        Payouts are sent by our team once your available balance reaches{' '}
        <strong>{money(me.rules.min_payout_amount)}</strong>.
      </p>

      <StripeCard me={me} />

      <div className={cardClass}>
        <SectionTitle title="Payout history" />
        {history.isLoading ? (
          <TableSkeleton cols={6} rows={3} />
        ) : history.isError ? (
          <LoadError
            message={getErrorMessage(history.error, 'We couldn’t load your payouts.')}
            onRetry={() => history.refetch()}
          />
        ) : !history.data || history.data.items.length === 0 ? (
          <EmptyState icon={<Banknote className="h-6 w-6" />} title="No payouts yet">
            Your first payout will show up here once it’s sent.
          </EmptyState>
        ) : (
          <>
            <Table head={['Date', 'Amount', 'Method', 'Status', 'Paid on', 'Reference']}>
              {history.data.items.map((p) => {
                const s = PAYOUT_STATUS[p.status] ?? { label: p.status, tone: 'slate' as BadgeTone }
                return (
                  <tr key={p.id} className="hover:bg-slate-50/60">
                    <td className={tdClass}>{formatDate(p.created_at)}</td>
                    <td className={`${tdClass} font-semibold text-slate-900`}>
                      {money(p.amount)}
                      {p.commission_count > 0 && (
                        <p className="text-xs font-normal text-slate-500">
                          {p.commission_count} commission{p.commission_count === 1 ? '' : 's'}
                        </p>
                      )}
                    </td>
                    <td className={tdClass}>{METHOD_LABELS[p.method] ?? p.method}</td>
                    <td className={tdClass}>
                      <Badge tone={s.tone}>{s.label}</Badge>
                    </td>
                    <td className={tdClass}>{formatDate(p.paid_at)}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{p.reference || '—'}</td>
                  </tr>
                )
              })}
            </Table>
            <Pagination
              page={history.data.page}
              pages={history.data.pages}
              total={history.data.total}
              onChange={setPage}
              disabled={history.isFetching}
            />
          </>
        )}
      </div>
    </div>
  )
}

/**
 * Stripe sends the partner back to `?stripe=return` (finished or left) or
 * `?stripe=refresh` (the onboarding link expired). Either way re-read the
 * account from Stripe, then drop the parameter so a reload doesn't repeat it.
 */
function useStripeReturn() {
  const params = useSearchParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const flag = params.get('stripe')
  const handled = useRef(false)

  useEffect(() => {
    if (!flag || handled.current) return
    handled.current = true
    ;(async () => {
      try {
        const stripe = await affiliateApi.stripeRefresh()
        await queryClient.invalidateQueries({ queryKey: AFFILIATE_ME_KEY })
        if (flag === 'refresh') {
          toast.info('Your Stripe setup link expired. Choose “Finish Stripe setup” to continue.')
        } else if (stripe.state === 'ready') {
          toast.success('Payouts are enabled — you’re all set.')
        } else {
          toast.info('Stripe still needs a few details before payouts can be sent.')
        }
      } catch (err) {
        toast.error(getErrorMessage(err, 'We couldn’t check your Stripe account. Please try again.'))
      } finally {
        router.replace('/affiliate/payouts')
      }
    })()
  }, [flag, queryClient, router])
}

function StripeCard({ me }: { me: AffiliateMe }) {
  const queryClient = useQueryClient()
  const stripe = me.stripe
  const [country, setCountry] = useState(stripe.country || 'US')
  const [busy, setBusy] = useState<null | 'connect' | 'refresh' | 'dashboard'>(null)

  const connect = async () => {
    setBusy('connect')
    try {
      const { url } = await affiliateApi.stripeConnect(country)
      window.location.assign(url)
      // Leave the button busy: the page is navigating away.
    } catch (err) {
      toast.error(getErrorMessage(err, 'We couldn’t start Stripe setup. Please try again.'))
      setBusy(null)
    }
  }

  const refresh = async () => {
    setBusy('refresh')
    try {
      const next = await affiliateApi.stripeRefresh()
      await queryClient.invalidateQueries({ queryKey: AFFILIATE_ME_KEY })
      toast[next.state === 'ready' ? 'success' : 'info'](
        next.state === 'ready' ? 'Payouts are enabled.' : 'Stripe still needs a few details from you.'
      )
    } catch (err) {
      toast.error(getErrorMessage(err, 'We couldn’t check your Stripe account. Please try again.'))
    } finally {
      setBusy(null)
    }
  }

  const openDashboard = async () => {
    // Open the tab synchronously so pop-up blockers allow it, then point it at the link.
    const tab = window.open('', '_blank')
    setBusy('dashboard')
    try {
      const { url } = await affiliateApi.stripeDashboard()
      if (tab) {
        tab.opener = null
        tab.location.href = url
      } else {
        window.location.assign(url)
      }
    } catch (err) {
      tab?.close()
      toast.error(getErrorMessage(err, 'We couldn’t open your Stripe dashboard. Please try again.'))
    } finally {
      setBusy(null)
    }
  }

  const spin = <Loader2 className="h-4 w-4 animate-spin" />

  let body: React.ReactNode
  if (!stripe.connect_available && stripe.state !== 'ready') {
    body = (
      <p className="text-sm text-slate-600">
        Payouts setup isn’t available yet — we’ll email you as soon as you can connect your bank account.
      </p>
    )
  } else if (stripe.state === 'ready') {
    body = (
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#106959]" />
          <div>
            <p className="font-semibold text-slate-900">Payouts enabled</p>
            <p className="text-sm text-slate-600">
              Your Stripe account is connected{stripe.country ? ` (${stripe.country})` : ''}. Manage your bank details
              and see transfers in your Stripe dashboard.
            </p>
          </div>
        </div>
        {stripe.connect_available && (
          <button type="button" onClick={openDashboard} disabled={!!busy} className={secondaryButtonClass}>
            {busy === 'dashboard' ? spin : <ExternalLink className="h-4 w-4" />}
            Open Stripe dashboard
          </button>
        )}
      </div>
    )
  } else if (stripe.state === 'incomplete') {
    body = (
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          You’ve started connecting Stripe, but it still needs a few details before we can send payouts.
        </p>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={connect} disabled={!!busy} className={primaryButtonClass}>
            {busy === 'connect' && spin}
            Finish Stripe setup
          </button>
          <button type="button" onClick={refresh} disabled={!!busy} className={secondaryButtonClass}>
            {busy === 'refresh' ? spin : <RefreshCw className="h-4 w-4" />}
            Refresh status
          </button>
        </div>
      </div>
    )
  } else {
    body = (
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          We send commissions through Stripe. Connect a free Stripe account to receive them straight to your bank —
          it takes a few minutes.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="w-full space-y-1.5 sm:w-72">
            <label className="block text-sm font-semibold text-slate-800" id="country-label">
              Country of your bank account
            </label>
            <Select value={country} onValueChange={setCountry} disabled={!!busy}>
              <SelectTrigger aria-labelledby="country-label" className="h-11 rounded-lg border-slate-300 bg-white">
                <SelectValue placeholder="Choose a country" />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                {COUNTRIES.map(([code, name]) => (
                  <SelectItem key={code} value={code}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <button type="button" onClick={connect} disabled={!!busy} className={`${primaryButtonClass} h-11`}>
            {busy === 'connect' && spin}
            Connect with Stripe
          </button>
        </div>
        <p className="text-xs text-slate-500">
          You can’t change the country after connecting. Not listed? Contact us and we’ll sort out another way to pay
          you.
        </p>
      </div>
    )
  }

  return (
    <div className={cardClass}>
      <SectionTitle title="Payout method" />
      {body}
    </div>
  )
}
