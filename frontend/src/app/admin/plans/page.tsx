'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Check, Clock, Pencil, RefreshCw, Users, X } from 'lucide-react'
import { adminApi, type Catalog, type Plan } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Callout,
  Dialog,
  Field,
  PageHeader,
  Panel,
  Toggle,
  errorText,
  formatLimit,
  formatMoney,
  humanize,
  inputClass,
} from '@/components/admin/ui'

function PlanEditor({ plan, catalog, stripeConfigured, onClose }: { plan: Plan; catalog: Catalog; stripeConfigured: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    name: plan.name,
    description: plan.description ?? '',
    price_monthly: String(plan.price_monthly),
    price_yearly: plan.price_yearly == null ? '' : String(plan.price_yearly),
    trial_days: String(plan.trial_days),
    is_trialable: plan.is_trialable,
    is_active: plan.is_active,
    is_public: plan.is_public,
    sort_order: String(plan.sort_order),
    highlights: plan.highlights.join('\n'),
    polar_product_id: plan.polar_product_id ?? '',
    polar_product_id_yearly: plan.polar_product_id_yearly ?? '',
  })
  const [features, setFeatures] = useState<Record<string, boolean>>(plan.features)
  const [limits, setLimits] = useState<Record<string, string>>(
    Object.fromEntries(catalog.limits.map((l) => [l.key, plan.limits[l.key] == null ? '' : String(plan.limits[l.key])]))
  )
  const set = (k: keyof typeof form, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }))

  const priceChanged =
    Number(form.price_monthly) !== plan.price_monthly ||
    (form.price_yearly === '' ? null : Number(form.price_yearly)) !== plan.price_yearly

  const save = useMutation({
    mutationFn: () =>
      adminApi.updatePlan(plan.id, {
        name: form.name.trim(),
        description: form.description,
        price_monthly: Number(form.price_monthly),
        ...(form.price_yearly !== '' ? { price_yearly: Number(form.price_yearly) } : {}),
        trial_days: Number(form.trial_days),
        is_trialable: form.is_trialable,
        is_active: form.is_active,
        is_public: form.is_public,
        sort_order: Number(form.sort_order),
        highlights: form.highlights.split('\n').map((s) => s.trim()).filter(Boolean),
        polar_product_id: form.polar_product_id.trim(),
        polar_product_id_yearly: form.polar_product_id_yearly.trim(),
        features,
        limits: Object.fromEntries(
          Object.entries(limits).filter(([, v]) => v.trim() !== '').map(([k, v]) => [k, Number(v)])
        ),
      } as Partial<Plan>),
    onSuccess: () => {
      toast.success(`${form.name} saved`)
      qc.invalidateQueries({ queryKey: ['admin', 'plans'] })
      onClose()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={`Edit ${plan.name}`}
      description="Changes apply to every organization on this plan immediately."
      footer={
        <>
          <AdminButton variant="ghost" onClick={onClose}>Cancel</AdminButton>
          <AdminButton variant="primary" loading={save.isPending} disabled={!form.name.trim()} onClick={() => save.mutate()}>
            Save plan
          </AdminButton>
        </>
      }
    >
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name"><input className={inputClass} value={form.name} onChange={(e) => set('name', e.target.value)} /></Field>
          <Field label="Display order"><input type="number" className={inputClass} value={form.sort_order} onChange={(e) => set('sort_order', e.target.value)} /></Field>
          <div className="sm:col-span-2">
            <Field label="Description"><input className={inputClass} value={form.description} onChange={(e) => set('description', e.target.value)} /></Field>
          </div>
          <Field label={`Monthly price (${plan.currency.toUpperCase()})`}>
            <input type="number" min={0} step="0.01" className={inputClass} value={form.price_monthly} onChange={(e) => set('price_monthly', e.target.value)} />
          </Field>
          <Field label={`Yearly price (${plan.currency.toUpperCase()})`} hint="Leave empty to offer monthly only.">
            <input type="number" min={0} step="0.01" className={inputClass} value={form.price_yearly} onChange={(e) => set('price_yearly', e.target.value)} />
          </Field>
          <Field label="Trial length (days)"><input type="number" min={1} max={365} className={inputClass} value={form.trial_days} onChange={(e) => set('trial_days', e.target.value)} /></Field>
        </div>

        {priceChanged && (
          <Callout tone="info" title="How price changes apply">
            {stripeConfigured
              ? 'A new Stripe price is created for new sign-ups and plan changes. Existing subscribers keep the price they signed up at until you move them in Stripe.'
              : 'Stripe is not configured, so only the displayed price changes. The Stripe price is created at the first checkout.'}
          </Callout>
        )}

        <div className="grid gap-3 sm:grid-cols-3">
          {([
            ['is_active', 'Available', 'New customers can choose it'],
            ['is_public', 'Shown on pricing page', 'Hidden plans can still be granted'],
            ['is_trialable', 'Free trial allowed', 'Card-free trial on this plan'],
          ] as const).map(([key, label, hint]) => (
            <div key={key} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 p-3">
              <div>
                <p className="text-sm font-medium text-slate-800">{label}</p>
                <p className="text-xs text-slate-500">{hint}</p>
              </div>
              <Toggle label={label} checked={form[key] as boolean} onChange={(v) => set(key, v)} />
            </div>
          ))}
        </div>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Polar products</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Monthly product ID" hint="From the Polar dashboard, or use Sync to Polar on the plan card.">
              <input className={`${inputClass} font-mono text-xs`} value={form.polar_product_id} onChange={(e) => set('polar_product_id', e.target.value)} placeholder="Not linked" />
            </Field>
            <Field label="Yearly product ID" hint="Leave empty to offer monthly only through Polar.">
              <input className={`${inputClass} font-mono text-xs`} value={form.polar_product_id_yearly} onChange={(e) => set('polar_product_id_yearly', e.target.value)} placeholder="Not linked" />
            </Field>
          </div>
        </div>

        <Field label="Pricing-page bullet points" hint="One per line.">
          <textarea rows={4} className={`${inputClass} h-auto py-2`} value={form.highlights} onChange={(e) => set('highlights', e.target.value)} />
        </Field>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Features</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {catalog.features.map((f) => (
              <div key={f.key} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
                <span className="text-sm text-slate-700">{f.label}</span>
                <Toggle label={f.label} checked={!!features[f.key]} onChange={(v) => setFeatures((s) => ({ ...s, [f.key]: v }))} />
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Limits (-1 = unlimited)</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {catalog.limits.map((l) => (
              <Field key={l.key} label={humanize(l.label)}>
                <input type="number" min={-1} className={inputClass} value={limits[l.key] ?? ''} onChange={(e) => setLimits((s) => ({ ...s, [l.key]: e.target.value }))} />
              </Field>
            ))}
          </div>
        </div>
      </div>
    </Dialog>
  )
}

/** One trial length for every plan: a trial runs on whichever plan it starts on. */
function TrialLengthPanel({ plans }: { plans: Plan[] }) {
  const qc = useQueryClient()
  const lengths = Array.from(new Set(plans.filter((p) => p.is_trialable).map((p) => p.trial_days)))
  const current = lengths.length === 1 ? lengths[0] : null
  const [days, setDays] = useState(current == null ? '' : String(current))

  const n = Number(days)
  const valid = days.trim() !== '' && Number.isInteger(n) && n >= 1 && n <= 365

  const save = useMutation({
    mutationFn: () => adminApi.setTrialLength(n),
    onSuccess: (res) => {
      toast.success(`Free trial set to ${res.days} day${res.days === 1 ? '' : 's'}`)
      qc.invalidateQueries({ queryKey: ['admin', 'plans'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <Panel
      className="mb-6"
      title={
        <span className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-brand-600" /> Free trial length
        </span>
      }
      description="How long a new card-free trial lasts, on every plan. Trials that have already started keep their end date; use Extend trial on an organization to change one."
    >
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Days">
          <input
            type="number"
            min={1}
            max={365}
            className={`${inputClass} w-32`}
            value={days}
            onChange={(e) => setDays(e.target.value)}
          />
        </Field>
        <AdminButton
          variant="primary"
          loading={save.isPending}
          disabled={!valid || n === current}
          onClick={() => save.mutate()}
        >
          Save
        </AdminButton>
        <p className="pb-2 text-sm text-slate-500">
          {current != null
            ? `Currently ${current} day${current === 1 ? '' : 's'}.`
            : lengths.length > 1
              ? `Plans currently differ (${lengths.sort((a, b) => a - b).join(', ')} days). Saving sets them all to the same length.`
              : 'No plan currently offers a free trial.'}
        </p>
      </div>
    </Panel>
  )
}

function PolarSyncButton({ plan, disabled }: { plan: Plan; disabled: boolean }) {
  const qc = useQueryClient()
  const sync = useMutation({
    mutationFn: () => adminApi.syncPlanToPolar(plan.id),
    onSuccess: () => {
      toast.success(`${plan.name} synced to Polar`)
      qc.invalidateQueries({ queryKey: ['admin', 'plans'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const linked = !!plan.polar_product_id
  return (
    <AdminButton icon={RefreshCw} loading={sync.isPending} disabled={disabled} onClick={() => sync.mutate()}>
      {linked ? 'Sync to Polar' : 'Create in Polar'}
    </AdminButton>
  )
}

export default function PlansPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['admin', 'plans'], queryFn: adminApi.plans })
  const polarActive = data?.payment_provider === 'polar'
  const unlinked = data?.plans.filter((p) => p.is_active && p.is_public && !p.polar_product_id) ?? []
  const catalog = useQuery({ queryKey: ['admin', 'catalog'], queryFn: adminApi.catalog, staleTime: Infinity })
  const [editing, setEditing] = useState<Plan | null>(null)

  const featureLabel = (key: string) => catalog.data?.features.find((f) => f.key === key)?.label ?? humanize(key)

  return (
    <>
      <PageHeader
        title="Plans & Pricing"
        description="Prices, trial length, features and limits for each plan. Edits take effect immediately and are no longer reset by deploys."
      />
      {error ? <Callout tone="danger" title="Could not load plans">{errorText(error)}</Callout> : null}
      {polarActive && unlinked.length > 0 && (
        <div className="mb-6">
          <Callout tone="warning" title={`${unlinked.length} plan${unlinked.length === 1 ? ' is' : 's are'} not linked to Polar`}>
            Polar is the active payment provider, so customers can&apos;t buy {unlinked.map((p) => p.name).join(', ')} until
            {unlinked.length === 1 ? ' it has' : ' they have'} a Polar product. Use <strong>Create in Polar</strong> on the plan, or paste the product IDs in Edit.
          </Callout>
        </div>
      )}
      {data && !polarActive && !data.stripe_configured && (
        <div className="mb-6">
          <Callout tone="warning" title="Stripe is not configured">
            Plans can be edited, but paid checkout is unavailable until a Stripe secret key is added under API Keys.
          </Callout>
        </div>
      )}

      {data && <TrialLengthPanel key={data.plans.map((p) => p.trial_days).join(',')} plans={data.plans} />}

      <div className="grid gap-6 lg:grid-cols-2">
        {isLoading && Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-80 animate-pulse rounded-xl bg-white" />)}
        {data?.plans.map((plan) => {
          const enabled = Object.entries(plan.features).filter(([, v]) => v).map(([k]) => k)
          return (
            <section key={plan.id} className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
              <header className="flex items-start justify-between gap-4 border-b border-slate-100 p-5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold text-slate-900">{plan.name}</h2>
                    {!plan.is_active && <Badge tone="danger">Unavailable</Badge>}
                    {!plan.is_public && <Badge>Hidden</Badge>}
                    {plan.admin_managed && <Badge tone="brand">Edited in admin</Badge>}
                  </div>
                  <p className="mt-0.5 text-sm text-slate-500">{plan.description}</p>
                  <p className="mt-3 text-2xl font-semibold text-slate-900">
                    {formatMoney(plan.price_monthly, plan.currency)}
                    <span className="text-sm font-normal text-slate-500"> / month</span>
                    {plan.price_yearly != null && (
                      <span className="ml-2 text-sm font-normal text-slate-500">· {formatMoney(plan.price_yearly, plan.currency)} / year</span>
                    )}
                  </p>
                </div>
                <div className="flex flex-shrink-0 flex-wrap justify-end gap-2">
                  {data.polar_configured && <PolarSyncButton plan={plan} disabled={false} />}
                  <AdminButton icon={Pencil} disabled={!catalog.data} onClick={() => setEditing(plan)}>Edit</AdminButton>
                </div>
              </header>

              <div className="grid flex-1 gap-5 p-5 sm:grid-cols-2">
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Limits</p>
                  <dl className="space-y-1.5 text-sm">
                    {catalog.data?.limits.map((l) => (
                      <div key={l.key} className="flex justify-between gap-2">
                        <dt className="text-slate-500">{humanize(l.label)}</dt>
                        <dd className="tabular-nums text-slate-800">{formatLimit(plan.limits[l.key])}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Features ({enabled.length})</p>
                  <ul className="space-y-1.5 text-sm">
                    {catalog.data?.features.map((f) => (
                      <li key={f.key} className="flex items-center gap-2">
                        {plan.features[f.key] ? (
                          <Check className="h-3.5 w-3.5 flex-shrink-0 text-emerald-600" />
                        ) : (
                          <X className="h-3.5 w-3.5 flex-shrink-0 text-slate-300" />
                        )}
                        <span className={plan.features[f.key] ? 'text-slate-700' : 'text-slate-400'}>{featureLabel(f.key)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
                <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {plan.subscribers} live subscription{plan.subscribers === 1 ? '' : 's'}</span>
                <span>Trial: {plan.is_trialable ? `${plan.trial_days} days` : 'none'}</span>
                <span className="font-mono">{plan.slug}</span>
                <span className="font-mono">{plan.stripe_price_id}</span>
                <span>
                  Polar:{' '}
                  {plan.polar_product_id ? (
                    <span className="font-mono">
                      {plan.polar_product_id}
                      {plan.polar_product_id_yearly ? ` · ${plan.polar_product_id_yearly}` : ''}
                    </span>
                  ) : (
                    <span className={polarActive ? 'font-medium text-amber-700' : ''}>not linked</span>
                  )}
                </span>
              </footer>
            </section>
          )
        })}
      </div>

      {editing && catalog.data && (
        <PlanEditor plan={editing} catalog={catalog.data} stripeConfigured={data?.stripe_configured ?? false} onClose={() => setEditing(null)} />
      )}
    </>
  )
}
