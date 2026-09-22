'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Ban,
  CalendarPlus,
  Gift,
  PlayCircle,
  RotateCcw,
  SlidersHorizontal,
  XCircle,
} from 'lucide-react'
import { adminApi, type Catalog, type OrgDetail } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Callout,
  Detail,
  Dialog,
  Field,
  Panel,
  StatusBadge,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  errorText,
  formatDate,
  formatDuration,
  formatLimit,
  formatNumber,
  humanize,
  inputClass,
  timeAgo,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'

type Action = 'suspend' | 'activate' | 'extend' | 'grant' | 'end' | 'reset' | null

function ReasonInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field label="Reason (recorded in the audit log)">
      <input value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} placeholder="e.g. Sales pilot, support ticket #123" />
    </Field>
  )
}

function OverrideEditor({ org, catalog, onSaved }: { org: OrgDetail; catalog: Catalog; onSaved: () => void }) {
  const current = org.override?.overrides ?? {}
  const [features, setFeatures] = useState<Record<string, boolean>>(current.features ?? {})
  const [limits, setLimits] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(current.limits ?? {}).map(([k, v]) => [k, String(v)]))
  )
  const [reason, setReason] = useState(org.override?.reason ?? '')
  const [expires, setExpires] = useState(org.override?.expires_at?.slice(0, 10) ?? '')

  const save = useMutation({
    mutationFn: () =>
      adminApi.setOverride(org.id, {
        features,
        limits: Object.fromEntries(
          Object.entries(limits)
            .filter(([, v]) => v.trim() !== '')
            .map(([k, v]) => [k, Number(v)])
        ),
        reason: reason || undefined,
        expires_at: expires ? `${expires}T23:59:59` : null,
      }),
    onSuccess: () => {
      toast.success('Entitlement override saved')
      onSaved()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const planFeatures = new Set(org.entitlements?.features ?? [])

  const cycle = (key: string) =>
    setFeatures((f) => {
      const next = { ...f }
      if (!(key in next)) next[key] = true
      else if (next[key]) next[key] = false
      else delete next[key]
      return next
    })

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-500">
        Grant or withhold individual features and limits on top of the organization&apos;s plan. Click a feature to
        cycle <em>inherit → on → off</em>. Leave a limit empty to inherit it; use -1 for unlimited.
      </p>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Features</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {catalog.features.map((f) => {
            const state = f.key in features ? (features[f.key] ? 'on' : 'off') : 'inherit'
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => cycle(f.key)}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                  state === 'on' && 'border-emerald-300 bg-emerald-50',
                  state === 'off' && 'border-rose-300 bg-rose-50',
                  state === 'inherit' && 'border-slate-200 hover:bg-slate-50'
                )}
              >
                <span className="text-slate-700">{f.label}</span>
                {state === 'inherit' ? (
                  <span className="text-xs text-slate-400">Plan: {planFeatures.has(f.key) ? 'on' : 'off'}</span>
                ) : (
                  <Badge tone={state === 'on' ? 'success' : 'danger'}>{state === 'on' ? 'Forced on' : 'Forced off'}</Badge>
                )}
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Limits</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {catalog.limits.map((l) => (
            <Field key={l.key} label={humanize(l.label)} hint={`Plan: ${formatLimit(org.entitlements?.limits?.[l.key])}`}>
              <input
                type="number"
                min={-1}
                value={limits[l.key] ?? ''}
                onChange={(e) => setLimits((s) => ({ ...s, [l.key]: e.target.value }))}
                placeholder="Inherit"
                className={inputClass}
              />
            </Field>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Reason">
          <input value={reason} onChange={(e) => setReason(e.target.value)} className={inputClass} placeholder="e.g. Enterprise pilot" />
        </Field>
        <Field label="Expires on" hint="Leave empty to keep it until removed.">
          <input type="date" value={expires} onChange={(e) => setExpires(e.target.value)} className={inputClass} />
        </Field>
      </div>

      <div className="flex justify-end gap-2">
        {org.override && (
          <AdminButton
            variant="ghost"
            onClick={() => {
              setFeatures({})
              setLimits({})
            }}
          >
            Clear all
          </AdminButton>
        )}
        <AdminButton variant="primary" loading={save.isPending} onClick={() => save.mutate()}>
          Save override
        </AdminButton>
      </div>
    </div>
  )
}

export default function OrganizationDetailPage({ params }: { params: { id: string } }) {
  const qc = useQueryClient()
  const { data: org, isLoading, error } = useQuery({
    queryKey: ['admin', 'organization', params.id],
    queryFn: () => adminApi.organization(params.id),
  })
  const catalog = useQuery({ queryKey: ['admin', 'catalog'], queryFn: adminApi.catalog, staleTime: Infinity })
  const plans = useQuery({ queryKey: ['admin', 'plans'], queryFn: adminApi.plans })

  const [action, setAction] = useState<Action>(null)
  const [reason, setReason] = useState('')
  const [days, setDays] = useState('14')
  const [planId, setPlanId] = useState('')
  const [showOverride, setShowOverride] = useState(false)

  useEffect(() => {
    setReason('')
  }, [action])

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['admin', 'organization', params.id] })
    qc.invalidateQueries({ queryKey: ['admin', 'organizations'] })
    qc.invalidateQueries({ queryKey: ['admin', 'overview'] })
  }

  const run = useMutation({
    mutationFn: async (a: Exclude<Action, null>) => {
      const r = reason || undefined
      switch (a) {
        case 'suspend': return adminApi.suspendOrg(params.id, r)
        case 'activate': return adminApi.activateOrg(params.id, r)
        case 'extend': return adminApi.extendTrial(params.id, Number(days), r)
        case 'grant': return adminApi.grantPlan(params.id, planId, r)
        case 'end': return adminApi.endManualPlan(params.id, r)
        case 'reset': return adminApi.resetUsage(params.id, r)
      }
    },
    onSuccess: () => {
      toast.success('Done')
      setAction(null)
      refresh()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  if (isLoading) return <div className="h-64 animate-pulse rounded-xl bg-white" />
  if (error || !org) return <Callout tone="danger" title="Could not load this organization">{errorText(error)}</Callout>

  const sub = org.subscription
  const isTrial = sub?.source === 'trial'
  const isManual = sub?.source === 'manual' && ['active', 'past_due', 'grace'].includes(sub.status)
  const isStripeLive = sub?.source === 'stripe' && ['active', 'past_due', 'grace', 'trialing'].includes(sub.status)

  const dialogs: Record<Exclude<Action, null>, { title: string; description: string; confirm: string; danger?: boolean; body?: React.ReactNode }> = {
    suspend: {
      title: `Suspend ${org.name}?`,
      description: 'Every member loses access to this workspace immediately and its API keys stop working. Nothing is deleted; you can reactivate it at any time.',
      confirm: 'Suspend',
      danger: true,
    },
    activate: { title: `Reactivate ${org.name}?`, description: 'Members regain access immediately.', confirm: 'Reactivate' },
    extend: {
      title: 'Extend free trial',
      description: 'Adds days to the trial end, counting from today if it already lapsed. An expired trial is revived; workflows paused at expiry stay paused.',
      confirm: 'Extend trial',
      body: (
        <Field label="Days to add">
          <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} className={inputClass} />
        </Field>
      ),
    },
    grant: {
      title: 'Grant a plan at no charge',
      description: 'Puts the organization on the chosen plan as a complimentary subscription that renews monthly until you end it. Not available while they pay through Stripe.',
      confirm: 'Grant plan',
      body: (
        <Field label="Plan">
          <select value={planId} onChange={(e) => setPlanId(e.target.value)} className={inputClass}>
            <option value="">Select a plan…</option>
            {plans.data?.plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} {p.is_active ? '' : '(inactive)'}
              </option>
            ))}
          </select>
        </Field>
      ),
    },
    end: {
      title: 'End complimentary plan?',
      description: 'The subscription expires now and the organization loses paid features until it subscribes.',
      confirm: 'End plan',
      danger: true,
    },
    reset: {
      title: 'Reset usage counters?',
      description: "Sets this period's minutes, calls, SMS and email counters back to zero.",
      confirm: 'Reset usage',
    },
  }
  const active = action ? dialogs[action] : null

  return (
    <>
      <Link href="/admin/organizations" className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="h-4 w-4" /> Organizations
      </Link>

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{org.name}</h1>
            <StatusBadge status={sub?.status} />
            {!org.is_active && <StatusBadge status="failed" label="Suspended" />}
            {org.override?.active && <Badge tone="brand">Custom entitlements</Badge>}
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {org.slug} · created {formatDate(org.created_at)} · owner {org.owner?.email ?? '—'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {isTrial && <AdminButton icon={CalendarPlus} onClick={() => setAction('extend')}>Extend trial</AdminButton>}
          {!isStripeLive && <AdminButton icon={Gift} onClick={() => setAction('grant')}>Grant plan</AdminButton>}
          {isManual && <AdminButton icon={XCircle} onClick={() => setAction('end')}>End comp</AdminButton>}
          <AdminButton icon={SlidersHorizontal} onClick={() => setShowOverride((s) => !s)}>Entitlements</AdminButton>
          {sub && <AdminButton icon={RotateCcw} onClick={() => setAction('reset')}>Reset usage</AdminButton>}
          {org.is_active ? (
            <AdminButton icon={Ban} variant="danger" onClick={() => setAction('suspend')}>Suspend</AdminButton>
          ) : (
            <AdminButton icon={PlayCircle} variant="primary" onClick={() => setAction('activate')}>Reactivate</AdminButton>
          )}
        </div>
      </div>

      {showOverride && catalog.data && (
        <Panel className="mb-6" title="Entitlement override" description="Applied on top of the plan for this organization only.">
          <OverrideEditor
            key={org.override?.updated_at ?? 'none'}
            org={org}
            catalog={catalog.data}
            onSaved={() => {
              setShowOverride(false)
              refresh()
            }}
          />
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Subscription" className="lg:col-span-2">
          {sub ? (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
              <Detail label="Plan">{sub.plan?.name ?? '—'}</Detail>
              <Detail label="Source">
                {sub.source === 'manual' ? 'Complimentary (manual)' : sub.source === 'polar' ? 'Polar' : humanize(sub.source)}
              </Detail>
              <Detail label="Billing period">{humanize(sub.billing_period)}</Detail>
              {sub.trial_end && <Detail label="Trial ends">{formatDate(sub.trial_end, true)}</Detail>}
              <Detail label="Period ends">{formatDate(sub.current_period_end)}</Detail>
              {sub.grace_period_end && <Detail label="Grace ends">{formatDate(sub.grace_period_end)}</Detail>}
              {sub.cancel_at_period_end && <Detail label="Cancels">At period end</Detail>}
              {sub.stripe_customer_id && (
                <Detail label="Stripe customer">
                  <a className="text-brand-700 hover:underline" target="_blank" rel="noreferrer" href={`https://dashboard.stripe.com/customers/${sub.stripe_customer_id}`}>
                    {sub.stripe_customer_id}
                  </a>
                </Detail>
              )}
              {sub.polar_customer_id && (
                <Detail label="Polar customer">
                  <span className="font-mono text-xs">{sub.polar_customer_id}</span>
                </Detail>
              )}
              {sub.polar_subscription_id && (
                <Detail label="Polar subscription">
                  <span className="font-mono text-xs">{sub.polar_subscription_id}</span>
                </Detail>
              )}
              <Detail label="Minutes this period">{formatNumber(sub.usage.minutes)}</Detail>
              <Detail label="Calls this period">{formatNumber(sub.usage.calls)}</Detail>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">This organization has never had a subscription or trial.</p>
          )}
          {org.override && (
            <div className="mt-5 rounded-lg border border-brand-100 bg-brand-50/50 px-4 py-3 text-sm">
              <p className="font-medium text-brand-800">
                Entitlement override {org.override.active ? 'active' : 'expired'}
                {org.override.expires_at && ` · until ${formatDate(org.override.expires_at)}`}
              </p>
              {org.override.reason && <p className="mt-0.5 text-brand-700">{org.override.reason}</p>}
            </div>
          )}
        </Panel>

        <Panel title="Resources">
          <dl className="grid grid-cols-2 gap-4">
            <Detail label="Agents">{formatNumber(org.usage.agents)} <span className="text-xs text-slate-400">/ {formatLimit(org.entitlements?.limits?.agents)}</span></Detail>
            <Detail label="Phone numbers">{formatNumber(org.usage.phone_numbers)} <span className="text-xs text-slate-400">/ {formatLimit(org.entitlements?.limits?.phone_numbers)}</span></Detail>
            <Detail label="Workflows">{formatNumber(org.usage.workflows)}</Detail>
            <Detail label="Knowledge bases">{formatNumber(org.usage.knowledge_bases)}</Detail>
            <Detail label="Members">{formatNumber(org.members.length)} <span className="text-xs text-slate-400">/ {formatLimit(org.entitlements?.limits?.team_members)}</span></Detail>
            <Detail label="Calls (30d)">{formatNumber(org.usage.calls_30d)}</Detail>
          </dl>
        </Panel>
      </div>

      <Panel className="mt-6" title="Members" bodyClassName="p-0">
        <Table>
          <thead>
            <tr><Th>User</Th><Th>Role</Th><Th>Status</Th><Th>Joined</Th><Th>Last sign-in</Th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {org.members.map((m) => (
              <Tr key={m.user_id}>
                <Td>
                  <Link href={`/admin/users?focus=${m.user_id}`} className="font-medium text-slate-900 hover:underline">{m.full_name || m.email}</Link>
                  <p className="text-xs text-slate-400">{m.email}</p>
                </Td>
                <Td><Badge>{humanize(m.role)}</Badge></Td>
                <Td>{m.is_active ? <StatusBadge status="active" /> : <StatusBadge status="failed" label="Disabled" />}</Td>
                <Td className="text-slate-500">{formatDate(m.joined_at)}</Td>
                <Td className="text-slate-500">{timeAgo(m.last_login_at)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </Panel>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel
          title="Recent calls"
          bodyClassName="p-0"
          actions={<Link href={`/admin/calls?organization_id=${org.id}`} className="text-xs font-medium text-brand-700 hover:underline">All calls</Link>}
        >
          <Table>
            <thead><tr><Th>When</Th><Th>Agent</Th><Th>Status</Th><Th className="text-right">Duration</Th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              <TableState colSpan={4} empty={org.recent_calls.length === 0} emptyText="No calls yet." />
              {org.recent_calls.map((c) => (
                <Tr key={c.id}>
                  <Td className="text-slate-500">{timeAgo(c.created_at)}</Td>
                  <Td>{c.agent_name ?? '—'} <span className="text-xs text-slate-400">({c.direction})</span></Td>
                  <Td><StatusBadge status={c.status} /></Td>
                  <Td className="text-right tabular-nums">{formatDuration(c.duration_seconds)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </Panel>

        <Panel title="Billing history" bodyClassName="p-0">
          <Table>
            <thead><tr><Th>When</Th><Th>Event</Th><Th>Change</Th><Th>By</Th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              <TableState colSpan={4} empty={org.events.length === 0} emptyText="No billing events." />
              {org.events.map((e) => (
                <Tr key={e.id}>
                  <Td className="text-slate-500">{formatDate(e.created_at, true)}</Td>
                  <Td>{humanize(e.event_type)}</Td>
                  <Td className="text-xs text-slate-500">{e.from_status || e.to_status ? `${e.from_status ?? '—'} → ${e.to_status ?? '—'}` : '—'}</Td>
                  <Td><Badge tone={e.actor_type === 'admin' ? 'brand' : 'neutral'}>{humanize(e.actor_type)}</Badge></Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </Panel>
      </div>

      <Dialog
        open={!!active}
        onClose={() => setAction(null)}
        title={active?.title}
        description={active?.description}
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setAction(null)}>Cancel</AdminButton>
            <AdminButton
              variant={active?.danger ? 'danger' : 'primary'}
              loading={run.isPending}
              disabled={(action === 'grant' && !planId) || (action === 'extend' && !(Number(days) >= 1))}
              onClick={() => action && run.mutate(action)}
            >
              {active?.confirm}
            </AdminButton>
          </>
        }
      >
        <div className="space-y-4">
          {active?.body}
          <ReasonInput value={reason} onChange={setReason} />
        </div>
      </Dialog>
    </>
  )
}
