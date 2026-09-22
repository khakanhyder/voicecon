'use client'

import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  AlertTriangle,
  Bot,
  Building2,
  CheckCircle2,
  CircleDollarSign,
  Clock,
  CreditCard,
  Hash,
  Phone,
  Plug,
  RefreshCw,
  Users,
  Workflow,
  XCircle,
} from 'lucide-react'
import { adminApi } from '@/lib/admin'
import {
  AdminButton,
  Callout,
  PageHeader,
  Panel,
  StatCard,
  StatusBadge,
  formatMoney,
  formatNumber,
  parseDate,
  timeAgo,
} from '@/components/admin/ui'

const BRAND = '#0f7a63'

const SUBSCRIPTION_ORDER = ['active', 'trialing', 'past_due', 'grace', 'expired', 'canceled', 'none']

function shortDay(iso: string) {
  const d = parseDate(`${iso}T00:00:00`)
  return d ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' }) : iso
}

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-slate-900">{shortDay(label)}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} className="mt-0.5 text-slate-600">
          <span className="font-semibold tabular-nums text-slate-900">{formatNumber(p.value)}</span> {unit}
          {p.payload.minutes != null && unit === 'calls' && (
            <span className="text-slate-500"> · {formatNumber(p.payload.minutes)} min</span>
          )}
        </p>
      ))}
    </div>
  )
}

function DailyBars({ data, dataKey, unit }: { data: any[]; dataKey: string; unit: string }) {
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, left: -16, bottom: 0 }} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke="#eef2f6" />
          <XAxis
            dataKey="date"
            tickFormatter={shortDay}
            tick={{ fontSize: 11, fill: '#64748b' }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: 'rgba(15,122,99,0.06)' }} content={<ChartTooltip unit={unit} />} />
          <Bar dataKey={dataKey} fill={BRAND} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function AdminOverviewPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: adminApi.overview,
    refetchInterval: 60_000,
  })

  const k = data?.kpis
  // An unused payment provider (Stripe while Polar is active, or the reverse)
  // is allowed to have no keys.
  const unconfigured = data?.providers.filter((p) => !p.configured && !p.optional) ?? []
  const subscriptionTotal = data ? Object.values(data.subscriptions).reduce((a, b) => a + b, 0) : 0

  return (
    <>
      <PageHeader
        title="Overview"
        description="Platform-wide health, growth and anything that needs attention."
        actions={
          <AdminButton icon={RefreshCw} loading={isFetching && !isLoading} onClick={() => refetch()}>
            Refresh
          </AdminButton>
        }
      />

      {error ? (
        <Callout tone="danger" title="Could not load the overview">
          Check that the backend is running.
        </Callout>
      ) : null}

      {unconfigured.length > 0 && (
        <div className="mb-6">
          <Callout tone="warning" title={`${unconfigured.length} provider${unconfigured.length === 1 ? '' : 's'} not configured`}>
            {unconfigured.map((p) => p.label).join(', ')}.{' '}
            <Link href="/admin/api-keys" className="font-medium underline underline-offset-2">
              Add keys
            </Link>
          </Callout>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Monthly recurring revenue" icon={CircleDollarSign} tone="success"
          value={k ? formatMoney(k.mrr) : '—'} hint="Paying Stripe subscriptions" />
        <StatCard label="Organizations" icon={Building2}
          value={k ? formatNumber(k.organizations_total) : '—'}
          hint={k ? `${k.organizations_suspended} suspended` : undefined} />
        <StatCard label="Users" icon={Users}
          value={k ? formatNumber(k.users_total) : '—'}
          hint={k ? `+${k.users_new_7d} in the last 7 days` : undefined} />
        <StatCard label="Calls (30 days)" icon={Phone}
          value={k ? formatNumber(k.calls_30d) : '—'}
          hint={k ? `${formatNumber(k.minutes_30d)} minutes · ${k.calls_24h} today` : undefined} />
        <StatCard label="Agents" icon={Bot} value={k ? formatNumber(k.agents_total) : '—'} />
        <StatCard label="Active phone numbers" icon={Hash} value={k ? formatNumber(k.phone_numbers_active) : '—'} />
        <StatCard label="Failed calls (24h)" icon={XCircle}
          tone={k && k.failed_calls_24h > 0 ? 'warning' : 'default'}
          value={k ? formatNumber(k.failed_calls_24h) : '—'} />
        <StatCard label="Open payment failures" icon={CreditCard}
          tone={k && k.open_payment_failures > 0 ? 'danger' : 'default'}
          value={k ? formatNumber(k.open_payment_failures) : '—'} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Calls per day" description="Last 14 days, all organizations">
          {data ? <DailyBars data={data.calls_daily} dataKey="calls" unit="calls" /> : <div className="h-56 animate-pulse rounded-lg bg-slate-50" />}
        </Panel>
        <Panel title="New sign-ups per day" description="Last 14 days">
          {data ? <DailyBars data={data.signups_daily} dataKey="users" unit="users" /> : <div className="h-56 animate-pulse rounded-lg bg-slate-50" />}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Panel title="Subscriptions" description="Current status of every organization">
          <ul className="space-y-3">
            {SUBSCRIPTION_ORDER.filter((s) => data?.subscriptions[s]).map((s) => {
              const n = data!.subscriptions[s]
              const pct = subscriptionTotal ? Math.round((n / subscriptionTotal) * 100) : 0
              return (
                <li key={s}>
                  <Link href={`/admin/organizations?status=${s}`} className="group block">
                    <div className="flex items-center justify-between text-sm">
                      <StatusBadge status={s} />
                      <span className="tabular-nums text-slate-700 group-hover:text-slate-900">
                        {n} <span className="text-xs text-slate-400">({pct}%)</span>
                      </span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-slate-400" style={{ width: `${pct}%` }} />
                    </div>
                  </Link>
                </li>
              )
            })}
            {data && subscriptionTotal === 0 && <li className="text-sm text-slate-500">No organizations yet.</li>}
          </ul>
        </Panel>

        <Panel title="Needs attention" description="Issues across all tenants">
          <ul className="divide-y divide-slate-100 text-sm">
            {[
              { label: 'Open payment failures', value: k?.open_payment_failures, href: '/admin/billing', icon: CreditCard },
              { label: 'Broken integration connections', value: k?.broken_connections, href: '/admin/integrations', icon: Plug },
              { label: 'Failed workflow runs (24h)', value: k?.failed_workflow_runs_24h, href: '/admin/integrations?tab=runs', icon: Workflow },
              { label: 'Failed calls (24h)', value: k?.failed_calls_24h, href: '/admin/calls?status=failed', icon: Phone },
            ].map((row) => {
              const Icon = row.icon
              const bad = (row.value ?? 0) > 0
              return (
                <li key={row.label}>
                  <Link href={row.href} className="flex items-center gap-3 py-2.5 hover:text-slate-900">
                    <Icon className="h-4 w-4 text-slate-400" />
                    <span className="flex-1 text-slate-700">{row.label}</span>
                    {bad ? (
                      <span className="flex items-center gap-1 font-semibold tabular-nums text-amber-700">
                        <AlertTriangle className="h-3.5 w-3.5" /> {row.value}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-emerald-700">
                        <CheckCircle2 className="h-3.5 w-3.5" /> {row.value ?? '—'}
                      </span>
                    )}
                  </Link>
                </li>
              )
            })}
          </ul>
        </Panel>

        <Panel title="Providers" description="Platform credentials in effect"
          actions={<Link href="/admin/api-keys" className="text-xs font-medium text-brand-700 hover:underline">Manage</Link>}>
          <ul className="grid grid-cols-1 gap-2 text-sm">
            {data?.providers.map((p) => (
              <li key={p.id} className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-700">
                  {p.label}
                  {p.active_payment_provider && (
                    <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-700">Payments</span>
                  )}
                </span>
                {!p.configured && p.optional ? (
                  <span className="text-xs text-slate-400">Not in use</span>
                ) : p.configured ? (
                  <span className="flex items-center gap-1 text-xs font-medium text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Configured
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs font-medium text-amber-700">
                    <AlertTriangle className="h-3.5 w-3.5" /> Missing
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel
        className="mt-6"
        title="Newest organizations"
        actions={<Link href="/admin/organizations" className="text-xs font-medium text-brand-700 hover:underline">View all</Link>}
        bodyClassName="p-0"
      >
        <ul className="divide-y divide-slate-100">
          {data?.recent_organizations.map((org) => (
            <li key={org.id}>
              <Link href={`/admin/organizations/${org.id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-slate-50">
                <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-sm font-semibold text-slate-600">
                  {org.name.slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">
                    {org.name} {!org.is_active && <span className="ml-1 text-xs font-normal text-rose-600">(suspended)</span>}
                  </p>
                  <p className="truncate text-xs text-slate-500">{org.owner.email}</p>
                </div>
                <div className="hidden text-right sm:block">
                  <StatusBadge status={org.subscription?.status} />
                  <p className="mt-1 text-xs text-slate-400">{org.subscription?.plan?.name ?? 'No plan'}</p>
                </div>
                <span className="hidden w-20 text-right text-xs text-slate-400 md:block">
                  <Clock className="mr-1 inline h-3 w-3" />
                  {timeAgo(org.created_at)}
                </span>
              </Link>
            </li>
          ))}
          {data && data.recent_organizations.length === 0 && (
            <li className="px-5 py-8 text-center text-sm text-slate-500">No organizations yet.</li>
          )}
        </ul>
      </Panel>
    </>
  )
}
