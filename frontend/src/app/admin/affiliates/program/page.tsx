'use client'

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Lock, Save } from 'lucide-react'
import { adminApi, type AffiliateProgram, type AffiliateProgramUpdate } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Callout,
  Field,
  PageHeader,
  Panel,
  Toggle,
  errorText,
  formatDate,
  inputClass,
} from '@/components/admin/ui'

interface FormState {
  enabled: boolean
  commission: string
  holdDays: string
  minPayout: string
  cookieDays: string
  windowDays: string
  maxPayments: string
  plans: string[]
}

function fromProgram(p: AffiliateProgram): FormState {
  return {
    enabled: p.enabled,
    commission: String(p.default_commission_percent),
    holdDays: String(p.hold_days),
    minPayout: String(p.min_payout_amount),
    cookieDays: String(p.cookie_days),
    windowDays: p.referral_window_days == null ? '' : String(p.referral_window_days),
    maxPayments: p.max_commission_payments == null ? '' : String(p.max_commission_payments),
    plans: [...p.eligible_plan_slugs],
  }
}

function int(value: string, min: number, max: number): number | null {
  if (value.trim() === '') return null
  const n = Number(value)
  return Number.isInteger(n) && n >= min && n <= max ? n : NaN
}

function toBody(f: FormState): { body: AffiliateProgramUpdate | null; problem: string | null } {
  const commission = Number(f.commission)
  if (f.commission.trim() === '' || !Number.isFinite(commission) || commission < 0 || commission > 100)
    return { body: null, problem: 'Default commission must be 0–100%.' }
  const hold = int(f.holdDays, 0, 365)
  if (hold == null || Number.isNaN(hold)) return { body: null, problem: 'Hold days must be a whole number from 0 to 365.' }
  const minPayout = Number(f.minPayout)
  if (f.minPayout.trim() === '' || !Number.isFinite(minPayout) || minPayout < 0 || minPayout > 100000)
    return { body: null, problem: 'Minimum payout must be $0–$100,000.' }
  const cookie = int(f.cookieDays, 1, 365)
  if (cookie == null || Number.isNaN(cookie)) return { body: null, problem: 'Cookie days must be a whole number from 1 to 365.' }
  const window = int(f.windowDays, 1, 3650)
  if (Number.isNaN(window)) return { body: null, problem: 'Referral window must be 1–3650 days, or blank for no limit.' }
  const maxPayments = int(f.maxPayments, 1, 100)
  if (Number.isNaN(maxPayments)) return { body: null, problem: 'Commissioned payments must be 1–100, or blank for every renewal.' }
  return {
    problem: null,
    body: {
      enabled: f.enabled,
      default_commission_percent: commission,
      hold_days: hold,
      min_payout_amount: minPayout,
      cookie_days: cookie,
      referral_window_days: window,
      max_commission_payments: maxPayments,
      eligible_plan_slugs: f.plans,
    },
  }
}

export default function AffiliateProgramPage() {
  const qc = useQueryClient()
  const { data: program, isLoading, error } = useQuery({ queryKey: ['admin', 'affiliate-program'], queryFn: adminApi.affiliateProgram })
  const [form, setForm] = useState<FormState | null>(null)

  useEffect(() => {
    if (program && !form) setForm(fromProgram(program))
  }, [program, form])

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => (f ? { ...f, [key]: value } : f))

  const { body, problem } = form ? toBody(form) : { body: null, problem: null }
  const dirty = useMemo(
    () => !!(program && form && JSON.stringify(fromProgram(program)) !== JSON.stringify(form)),
    [program, form]
  )

  const save = useMutation({
    mutationFn: (b: AffiliateProgramUpdate) => adminApi.updateAffiliateProgram(b),
    onSuccess: (res) => {
      qc.setQueryData(['admin', 'affiliate-program'], res)
      qc.invalidateQueries({ queryKey: ['admin', 'affiliates'] })
      setForm(fromProgram(res))
      toast.success('Program rules saved.')
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const togglePlan = (slug: string, on: boolean) =>
    set('plans', on ? [...(form?.plans ?? []), slug] : (form?.plans ?? []).filter((s) => s !== slug))

  return (
    <>
      <PageHeader
        title="Affiliate program"
        description="Rules that apply to every affiliate unless their own terms override them. Changes apply to future payments; commissions already earned are not recalculated."
        actions={
          <>
            {dirty && (
              <AdminButton variant="ghost" onClick={() => program && setForm(fromProgram(program))} disabled={save.isPending}>
                Discard
              </AdminButton>
            )}
            <AdminButton variant="primary" icon={Save} loading={save.isPending} disabled={!dirty || !body} onClick={() => body && save.mutate(body)}>
              Save rules
            </AdminButton>
          </>
        }
      />

      {error ? (
        <Callout tone="danger" title="Could not load the program rules">{errorText(error)}</Callout>
      ) : isLoading || !program || !form ? (
        <div className="h-64 animate-pulse rounded-xl bg-white" />
      ) : (
        <div className="space-y-6">
          {!program.stripe_connect_ready && (
            <Callout tone="warning" title="Stripe secret key not configured">
              Affiliates can’t connect Stripe and Stripe payouts are disabled; manual payouts still work.
            </Callout>
          )}
          {program.payment_provider === 'polar' && (
            <Callout tone="info" title="Customers pay through Polar">
              Stripe payouts are sent from VoiceCon’s Stripe balance — keep it topped up.
            </Callout>
          )}
          {problem && <Callout tone="danger">{problem}</Callout>}

          <Panel
            title="Program"
            description={program.updated_at ? `Last changed ${formatDate(program.updated_at, true)}` : undefined}
            actions={<Toggle checked={form.enabled} onChange={(v) => set('enabled', v)} label="Program enabled" />}
          >
            <p className="text-sm text-slate-600">
              {form.enabled
                ? 'On — referral links and coupons are tracked and eligible payments earn commission.'
                : 'Off — links and coupons are not tracked and no new commissions are earned. Existing balances can still be paid.'}
            </p>
            <div className="mt-4 flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
              <Lock className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" />
              <span>
                <span className="font-medium">Commission is paid on annual (yearly) plans only</span> — monthly payments never earn commission.
              </span>
            </div>
          </Panel>

          <Panel title="Commission & payouts">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Default commission %" hint="New affiliates start at this rate.">
                <input type="number" min={0} max={100} step="0.01" value={form.commission} onChange={(e) => set('commission', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Hold days (refund window)" hint="A commission becomes payable this many days after the payment.">
                <input type="number" min={0} max={365} value={form.holdDays} onChange={(e) => set('holdDays', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Minimum payout ($)" hint="Balances below this are carried over.">
                <input type="number" min={0} step="0.01" value={form.minPayout} onChange={(e) => set('minPayout', e.target.value)} className={inputClass} />
              </Field>
            </div>
          </Panel>

          <Panel title="Attribution">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Referral cookie (days)" hint="How long a click on a referral link is remembered before sign-up.">
                <input type="number" min={1} max={365} value={form.cookieDays} onChange={(e) => set('cookieDays', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Referral window (days)" hint="The first annual payment must happen within this many days of sign-up. Blank = no limit.">
                <input type="number" min={1} max={3650} value={form.windowDays} onChange={(e) => set('windowDays', e.target.value)} className={inputClass} placeholder="No limit" />
              </Field>
              <Field label="Commissioned payments per customer" hint="Blank = every annual renewal. 1 = first annual payment only. Affiliates can override this.">
                <input type="number" min={1} max={100} value={form.maxPayments} onChange={(e) => set('maxPayments', e.target.value)} className={inputClass} placeholder="Every renewal" />
              </Field>
            </div>
          </Panel>

          <Panel title="Eligible plans" description="Leave all unchecked to pay commission on every plan.">
            {program.plans.length === 0 ? (
              <p className="text-sm text-slate-500">No active plans.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {program.plans.map((p) => (
                  <label key={p.slug} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 text-sm hover:bg-slate-50">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300"
                      checked={form.plans.includes(p.slug)}
                      onChange={(e) => togglePlan(p.slug, e.target.checked)}
                    />
                    <span className="flex-1 text-slate-800">{p.name}</span>
                    {!p.has_yearly && <Badge tone="warning">No annual price</Badge>}
                  </label>
                ))}
              </div>
            )}
            <p className="mt-3 text-xs text-slate-500">
              {form.plans.length === 0 ? 'Currently: all plans are eligible.' : `Currently: ${form.plans.length} plan${form.plans.length === 1 ? '' : 's'} eligible.`}{' '}
              Plans without an annual price can never earn commission.
            </p>
          </Panel>
        </div>
      )}
    </>
  )
}
