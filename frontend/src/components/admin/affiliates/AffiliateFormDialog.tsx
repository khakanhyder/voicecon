'use client'

/** Create / edit an affiliate: identity, which payments earn and at what rate, coupon and commission limits. */
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  adminApi,
  COMMISSION_PERIOD_LABELS,
  type AffiliateCreateBody,
  type CommissionBillingPeriods,
  type AffiliateDetail,
  type AffiliateUpdateBody,
} from '@/lib/admin'
import { AdminButton, Dialog, Field, Toggle, errorText, inputClass } from '@/components/admin/ui'
import { cn } from '@/lib/utils'

type Duration = 'once' | 'forever' | 'repeating'
type AppliesTo = 'yearly' | 'all'

interface FormState {
  email: string
  name: string
  company: string
  earnsOn: CommissionBillingPeriods
  commission: string
  commissionMonthly: string
  referralCode: string
  discount: string
  couponCode: string
  appliesTo: AppliesTo
  duration: Duration
  months: string
  customMax: boolean
  maxPayments: string
  maxMonthlyPayments: string
  notes: string
  sendInvite: boolean
  removeCoupon: boolean
}

const EMPTY: FormState = {
  email: '',
  name: '',
  company: '',
  earnsOn: 'yearly',
  commission: '',
  commissionMonthly: '',
  referralCode: '',
  discount: '0',
  couponCode: '',
  appliesTo: 'yearly',
  duration: 'once',
  months: '3',
  customMax: false,
  maxPayments: '',
  maxMonthlyPayments: '',
  notes: '',
  sendInvite: true,
  removeCoupon: false,
}

function fromAffiliate(a: AffiliateDetail): FormState {
  return {
    ...EMPTY,
    email: a.email ?? '',
    name: a.name,
    company: a.company ?? '',
    earnsOn: a.commission_billing_periods ?? 'yearly',
    commission: String(a.commission_percent),
    commissionMonthly: a.commission_percent_monthly == null ? '' : String(a.commission_percent_monthly),
    referralCode: a.referral_code,
    discount: String(a.coupon?.percent_off ?? a.discount_percent ?? 0),
    couponCode: a.coupon?.code ?? '',
    appliesTo: a.discount_applies_to ?? 'yearly',
    duration: a.discount_duration ?? 'once',
    months: a.discount_duration_months ? String(a.discount_duration_months) : '3',
    customMax: a.custom_max_payments,
    maxPayments: a.max_commission_payments ? String(a.max_commission_payments) : '',
    maxMonthlyPayments: a.max_monthly_commission_payments ? String(a.max_monthly_commission_payments) : '',
    notes: a.notes ?? '',
  }
}

const REFERRAL_RE = /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/
const COUPON_RE = /^[A-Z0-9](?:[A-Z0-9_-]{1,38}[A-Z0-9])$/

function num(value: string): number | null {
  if (value.trim() === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function problems(f: FormState, editing: boolean): string | null {
  if (!editing && !f.email.includes('@')) return 'Enter a valid email address.'
  if (!f.name.trim()) return 'Enter the affiliate’s name.'
  const commission = num(f.commission)
  if (f.commission.trim() && (commission == null || commission < 0 || commission > 100)) return 'Annual commission must be 0–100%.'
  const monthly = num(f.commissionMonthly)
  if (f.earnsOn !== 'yearly' && f.commissionMonthly.trim() && (monthly == null || monthly < 0 || monthly > 100))
    return 'Monthly commission must be 0–100%.'
  if (f.referralCode.trim() && !REFERRAL_RE.test(f.referralCode.trim()))
    return 'Referral codes are 3–40 characters: lowercase letters, numbers and hyphens.'
  if (!f.removeCoupon) {
    const discount = num(f.discount) ?? 0
    if (discount < 0 || discount > 100) return 'Discount must be 0–100%.'
    if (discount > 0 && f.couponCode.trim() && !COUPON_RE.test(f.couponCode.trim().toUpperCase()))
      return 'Coupon codes are 3–40 characters: letters, numbers, hyphens and underscores.'
    if (discount > 0 && f.duration === 'repeating') {
      const m = num(f.months)
      if (m == null || m < 1 || m > 36 || !Number.isInteger(m)) return 'A repeating discount lasts 1–36 months.'
    }
  }
  if (f.customMax && f.earnsOn !== 'monthly' && f.maxPayments.trim()) {
    const m = num(f.maxPayments)
    if (m == null || m < 1 || m > 100 || !Number.isInteger(m))
      return 'Commissioned annual payments must be a whole number from 1 to 100, or blank for unlimited.'
  }
  if (f.customMax && f.earnsOn !== 'yearly' && f.maxMonthlyPayments.trim()) {
    const m = num(f.maxMonthlyPayments)
    if (m == null || m < 1 || m > 240 || !Number.isInteger(m))
      return 'Commissioned monthly payments must be a whole number from 1 to 240, or blank for unlimited.'
  }
  return null
}

function terms(f: FormState) {
  const discount = f.removeCoupon ? 0 : num(f.discount) ?? 0
  // Without a discount the duration is moot; "once" avoids the months check.
  const duration: Duration = discount > 0 ? f.duration : 'once'
  return {
    name: f.name.trim(),
    company: f.company.trim(),
    commission_billing_periods: f.earnsOn,
    commission_percent: num(f.commission),
    // Blank = same as the annual rate. Irrelevant (and cleared) for annual-only.
    commission_percent_monthly: f.earnsOn === 'yearly' ? null : num(f.commissionMonthly),
    discount_percent: discount,
    discount_applies_to: f.appliesTo,
    discount_duration: duration,
    discount_duration_months: duration === 'repeating' ? num(f.months) : null,
    custom_max_payments: f.customMax,
    max_commission_payments: f.customMax ? num(f.maxPayments) : null,
    max_monthly_commission_payments: f.customMax ? num(f.maxMonthlyPayments) : null,
    notes: f.notes.trim(),
  }
}

export function AffiliateFormDialog({
  open,
  onClose,
  affiliate,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  /** Present when editing. */
  affiliate?: AffiliateDetail | null
  onCreated?: (created: AffiliateDetail) => void
}) {
  const qc = useQueryClient()
  const editing = !!affiliate
  const [form, setForm] = useState<FormState>(EMPTY)
  const program = useQuery({ queryKey: ['admin', 'affiliate-program'], queryFn: adminApi.affiliateProgram, enabled: open })

  useEffect(() => {
    if (open) setForm(affiliate ? fromAffiliate(affiliate) : EMPTY)
  }, [open, affiliate])

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }))

  const save = useMutation({
    mutationFn: async (): Promise<AffiliateDetail> => {
      const base = terms(form)
      if (affiliate) {
        const discount = base.discount_percent
        const removeCoupon = form.removeCoupon || (discount <= 0 && !!affiliate.coupon)
        const referral = form.referralCode.trim()
        const body: AffiliateUpdateBody = {
          ...base,
          commission_percent: base.commission_percent ?? undefined,
          referral_code: referral && referral !== affiliate.referral_code ? referral : null,
          coupon_code: removeCoupon ? null : form.couponCode.trim().toUpperCase() || null,
          remove_coupon: removeCoupon,
        }
        if (removeCoupon) delete body.discount_percent
        return adminApi.updateAffiliate(affiliate.id, body)
      }
      const discount = base.discount_percent
      const body: AffiliateCreateBody = {
        ...base,
        email: form.email.trim(),
        company: base.company || null,
        commission_percent: base.commission_percent ?? undefined,
        referral_code: form.referralCode.trim() || undefined,
        coupon_code: discount > 0 ? form.couponCode.trim().toUpperCase() || undefined : undefined,
        send_invite: form.sendInvite,
      }
      return adminApi.createAffiliate(body)
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['admin', 'affiliates'] })
      qc.invalidateQueries({ queryKey: ['admin', 'affiliate', result.id] })
      if (editing) {
        toast.success('Affiliate updated.')
      } else {
        toast.success(result.invite_sent ? `Affiliate created — invite emailed to ${result.email}.` : 'Affiliate created.')
        onCreated?.(result)
      }
      onClose()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const problem = problems(form, editing)
  const discount = num(form.discount) ?? 0
  const couponOff = form.removeCoupon
  const defaultPct = program.data?.default_commission_percent
  const programMax = program.data?.max_commission_payments
  const programMonthlyMax = program.data?.max_monthly_commission_payments
  const earnsYearly = form.earnsOn !== 'monthly'
  const earnsMonthly = form.earnsOn !== 'yearly'
  const annualPct = form.commission.trim() || (editing ? '' : defaultPct != null ? String(defaultPct) : '')

  return (
    <Dialog
      open={open}
      onClose={() => !save.isPending && onClose()}
      wide
      title={editing ? `Edit ${affiliate?.name}` : 'New affiliate'}
      description={
        editing
          ? 'Changes apply to future commissions and checkouts. Earned commissions keep the rate they were earned at.'
          : 'Creates a portal login for this person (or reuses their existing account) and a referral link.'
      }
      footer={
        <>
          <AdminButton variant="ghost" onClick={onClose} disabled={save.isPending}>Cancel</AdminButton>
          <AdminButton variant="primary" loading={save.isPending} disabled={!!problem} onClick={() => save.mutate()} title={problem ?? undefined}>
            {editing ? 'Save changes' : 'Create affiliate'}
          </AdminButton>
        </>
      }
    >
      <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          {!editing && (
            <Field label="Email *">
              <input type="email" value={form.email} onChange={(e) => set('email', e.target.value)} className={inputClass} placeholder="partner@example.com" />
            </Field>
          )}
          <Field label="Name *">
            <input value={form.name} onChange={(e) => set('name', e.target.value)} className={inputClass} placeholder="Jane Doe" />
          </Field>
          <Field label="Company">
            <input value={form.company} onChange={(e) => set('company', e.target.value)} className={inputClass} placeholder="Optional" />
          </Field>
          <Field label="Referral code" hint={editing ? 'Changing it breaks links already shared.' : 'Blank = generated from the name. Lowercase letters, digits, hyphens.'}>
            <input
              value={form.referralCode}
              onChange={(e) => set('referralCode', e.target.value.toLowerCase().replace(/\s+/g, '-'))}
              className={cn(inputClass, 'font-mono')}
              placeholder="jane-doe"
            />
          </Field>
        </div>

        <fieldset className="rounded-xl border border-slate-200 p-4">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Commission</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Earns commission on" hint="Payments on the other billing type earn nothing.">
              <select
                value={form.earnsOn}
                onChange={(e) => set('earnsOn', e.target.value as CommissionBillingPeriods)}
                className={inputClass}
              >
                {(Object.keys(COMMISSION_PERIOD_LABELS) as CommissionBillingPeriods[]).map((k) => (
                  <option key={k} value={k}>{COMMISSION_PERIOD_LABELS[k]}</option>
                ))}
              </select>
            </Field>
            {earnsYearly && (
              <Field label="Annual commission %" hint={editing ? 'Of each commissioned annual payment.' : 'Blank uses the program default.'}>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step="0.01"
                  value={form.commission}
                  onChange={(e) => set('commission', e.target.value)}
                  className={inputClass}
                  placeholder={defaultPct != null ? String(defaultPct) : ''}
                />
              </Field>
            )}
            {earnsMonthly && (
              <Field
                label="Monthly commission %"
                hint={
                  form.earnsOn === 'both'
                    ? `Of each commissioned monthly payment. Blank = same as annual${annualPct ? ` (${annualPct}%)` : ''}.`
                    : `Of each commissioned monthly payment.${!editing && defaultPct != null ? ` Blank = program default (${defaultPct}%).` : ''}`
                }
              >
                <input
                  type="number"
                  min={0}
                  max={100}
                  step="0.01"
                  value={form.commissionMonthly}
                  onChange={(e) => set('commissionMonthly', e.target.value)}
                  className={inputClass}
                  placeholder={form.earnsOn === 'both' ? annualPct || 'Same as annual' : defaultPct != null ? String(defaultPct) : ''}
                />
              </Field>
            )}
          </div>
        </fieldset>

        <fieldset className="rounded-xl border border-slate-200 p-4">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Customer coupon</legend>
          {editing && affiliate?.coupon && (
            <label className="mb-3 flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={form.removeCoupon} onChange={(e) => set('removeCoupon', e.target.checked)} className="h-4 w-4 rounded border-slate-300" />
              Remove coupon <span className="text-xs text-slate-400">({affiliate.coupon.code} stops working)</span>
            </label>
          )}
          <div className={cn('grid gap-4 sm:grid-cols-2', couponOff && 'pointer-events-none opacity-50')}>
            <Field label="Discount %" hint="0 = no coupon.">
              <input type="number" min={0} max={100} step="0.01" value={form.discount} onChange={(e) => set('discount', e.target.value)} className={inputClass} disabled={couponOff} />
            </Field>
            <Field label="Coupon code" hint="Blank = made from the referral code.">
              <input
                value={form.couponCode}
                onChange={(e) => set('couponCode', e.target.value.toUpperCase())}
                className={cn(inputClass, 'font-mono')}
                placeholder="JANEDOE"
                disabled={couponOff || discount <= 0}
              />
            </Field>
            <Field label="Applies to">
              <select value={form.appliesTo} onChange={(e) => set('appliesTo', e.target.value as AppliesTo)} className={inputClass} disabled={couponOff || discount <= 0}>
                <option value="yearly">Annual plans only</option>
                <option value="all">All plans</option>
              </select>
            </Field>
            <Field label="Duration">
              <div className="flex gap-2">
                <select value={form.duration} onChange={(e) => set('duration', e.target.value as Duration)} className={inputClass} disabled={couponOff || discount <= 0}>
                  <option value="once">First payment only</option>
                  <option value="forever">Every payment</option>
                  <option value="repeating">Repeating for N months</option>
                </select>
                {form.duration === 'repeating' && (
                  <input
                    type="number"
                    min={1}
                    max={36}
                    value={form.months}
                    onChange={(e) => set('months', e.target.value)}
                    className={cn(inputClass, 'w-24')}
                    aria-label="Months"
                    disabled={couponOff || discount <= 0}
                  />
                )}
              </div>
            </Field>
          </div>
          {editing && affiliate?.coupon && !form.removeCoupon && discount <= 0 && (
            <p className="mt-3 text-xs text-amber-700">A 0% discount removes the coupon {affiliate.coupon.code}.</p>
          )}
        </fieldset>

        <fieldset className="rounded-xl border border-slate-200 p-4">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Commission limit</legend>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-800">Custom limit for this affiliate</p>
              <p className="text-xs text-slate-500">
                Off = program rule:{' '}
                {[
                  earnsYearly && (programMax ? `${programMax} annual payment${programMax === 1 ? '' : 's'}` : 'every annual payment'),
                  earnsMonthly &&
                    (programMonthlyMax ? `${programMonthlyMax} monthly payment${programMonthlyMax === 1 ? '' : 's'}` : 'every monthly payment'),
                ]
                  .filter(Boolean)
                  .join(' and ')}{' '}
                per customer.
              </p>
            </div>
            <Toggle checked={form.customMax} onChange={(v) => set('customMax', v)} label="Custom commission limit" />
          </div>
          {form.customMax && (
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              {earnsYearly && (
                <Field label="Commissioned annual payments per customer" hint="1 = first annual payment only. Blank = every annual renewal.">
                  <input type="number" min={1} max={100} value={form.maxPayments} onChange={(e) => set('maxPayments', e.target.value)} className={inputClass} placeholder="Unlimited" />
                </Field>
              )}
              {earnsMonthly && (
                <Field label="Commissioned monthly payments per customer" hint="12 = the first year of monthly payments. Blank = every month.">
                  <input type="number" min={1} max={240} value={form.maxMonthlyPayments} onChange={(e) => set('maxMonthlyPayments', e.target.value)} className={inputClass} placeholder="Unlimited" />
                </Field>
              )}
            </div>
          )}
        </fieldset>

        <Field label="Internal notes" hint="Only visible to admins.">
          <textarea value={form.notes} onChange={(e) => set('notes', e.target.value)} rows={3} className={cn(inputClass, 'h-auto py-2')} />
        </Field>

        {!editing && (
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.sendInvite} onChange={(e) => set('sendInvite', e.target.checked)} className="h-4 w-4 rounded border-slate-300" />
            Send invite email
          </label>
        )}

        {problem && <p className="text-xs text-rose-600">{problem}</p>}
      </div>
    </Dialog>
  )
}
