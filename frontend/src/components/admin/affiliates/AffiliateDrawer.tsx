'use client'

/** One affiliate: links, terms, Stripe, balance, payouts, referrals and commissions. */
import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Ban, Banknote, Mail, Pencil, PlayCircle, Plus } from 'lucide-react'
import { adminApi, COMMISSION_PERIOD_LABELS, type AffiliateDetail, type AffiliatePayout } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Callout,
  Detail,
  Dialog,
  Drawer,
  Field,
  Pagination,
  StatCard,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  errorText,
  formatDate,
  formatMoney,
  humanize,
  inputClass,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'
import { AffiliateFormDialog } from './AffiliateFormDialog'
import {
  AffiliateStatusBadge,
  CommissionActions,
  CommissionStatusBadge,
  CopyField,
  InviteLinkDialog,
  REFERRAL_STATUS,
  StripeStateBadge,
  billingReasonLabel,
  invalidateAffiliateData,
  moneyClass,
  payableIn,
} from './shared'

function SectionTitle({ children, actions }: { children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</p>
      {actions}
    </div>
  )
}

function YesNo({ value }: { value: boolean }) {
  return value ? <Badge tone="success">Yes</Badge> : <Badge>No</Badge>
}

// ---------------------------------------------------------------------------
// Payout
// ---------------------------------------------------------------------------

function PayoutDialog({ affiliate, open, onClose }: { affiliate: AffiliateDetail; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const p = affiliate.payout
  const [method, setMethod] = useState<'stripe' | 'manual'>(p.stripe_ready ? 'stripe' : 'manual')
  const [reference, setReference] = useState('')
  const [note, setNote] = useState('')
  const [ignoreMinimum, setIgnoreMinimum] = useState(false)
  const [failed, setFailed] = useState<AffiliatePayout | null>(null)

  const reset = () => {
    setReference('')
    setNote('')
    setIgnoreMinimum(false)
    setFailed(null)
    setMethod(p.stripe_ready ? 'stripe' : 'manual')
  }

  const pay = useMutation({
    mutationFn: () =>
      adminApi.createAffiliatePayout(affiliate.id, {
        method,
        reference: method === 'manual' ? reference.trim() : null,
        note: note.trim() || null,
        ignore_minimum: ignoreMinimum,
      }),
    onSuccess: (payout) => {
      invalidateAffiliateData(qc)
      qc.invalidateQueries({ queryKey: ['admin', 'affiliate-payouts'] })
      if (payout.status === 'failed') {
        // The payout was recorded but the transfer did not go through.
        setFailed(payout)
        toast.error('The payout failed — nothing was sent.')
        return
      }
      if (payout.status === 'processing') {
        toast.message(`Payout of ${formatMoney(payout.amount, payout.currency)} is processing. Check Commissions & Payouts for the result.`)
      } else {
        toast.success(`Paid ${formatMoney(payout.amount, payout.currency)} to ${affiliate.name}.`)
      }
      reset()
      onClose()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const close = () => {
    if (pay.isPending) return
    reset()
    onClose()
  }
  const blockedByMinimum = !p.meets_minimum && !ignoreMinimum
  const invalid = (method === 'manual' && !reference.trim()) || (method === 'stripe' && !p.stripe_ready) || blockedByMinimum

  return (
    <Dialog
      open={open}
      onClose={close}
      title={`Pay ${formatMoney(p.available)} to ${affiliate.name}`}
      description="Pays the whole approved balance. Commissions still in their hold period are not included."
      footer={
        <>
          <AdminButton variant="ghost" onClick={close} disabled={pay.isPending}>{failed ? 'Close' : 'Cancel'}</AdminButton>
          <AdminButton variant="primary" icon={Banknote} loading={pay.isPending} disabled={invalid} onClick={() => { setFailed(null); pay.mutate() }}>
            {failed ? 'Try again' : method === 'stripe' ? 'Send Stripe transfer' : 'Record as paid'}
          </AdminButton>
        </>
      }
    >
      <div className="space-y-4">
        {failed && (
          <Callout tone="danger" title="Payout failed">
            {failed.failure_reason || 'The transfer was not completed.'} The commissions are back in the available balance.
          </Callout>
        )}
        <div className="space-y-2">
          <label className={cn('flex cursor-pointer items-start gap-3 rounded-lg border p-3', method === 'stripe' ? 'border-brand-300 bg-brand-50/40' : 'border-slate-200', !p.stripe_ready && 'cursor-not-allowed opacity-50')}>
            <input type="radio" name="method" className="mt-0.5" checked={method === 'stripe'} disabled={!p.stripe_ready} onChange={() => setMethod('stripe')} />
            <span>
              <span className="block text-sm font-medium text-slate-800">Stripe transfer</span>
              <span className="block text-xs text-slate-500">
                {p.stripe_ready
                  ? 'Sent from VoiceCon’s Stripe balance to their connected account.'
                  : 'Unavailable — the affiliate has not finished connecting Stripe (or Stripe is not configured).'}
              </span>
            </span>
          </label>
          <label className={cn('flex cursor-pointer items-start gap-3 rounded-lg border p-3', method === 'manual' ? 'border-brand-300 bg-brand-50/40' : 'border-slate-200')}>
            <input type="radio" name="method" className="mt-0.5" checked={method === 'manual'} onChange={() => setMethod('manual')} />
            <span>
              <span className="block text-sm font-medium text-slate-800">Manual</span>
              <span className="block text-xs text-slate-500">You already paid them another way (bank transfer, PayPal…). This only records it.</span>
            </span>
          </label>
        </div>
        {method === 'manual' && (
          <Field label="Payment reference *" hint="e.g. bank transfer ID or PayPal transaction ID.">
            <input value={reference} onChange={(e) => setReference(e.target.value)} className={inputClass} maxLength={255} />
          </Field>
        )}
        <Field label="Note" hint="Optional, admin-only.">
          <input value={note} onChange={(e) => setNote(e.target.value)} className={inputClass} maxLength={2000} />
        </Field>
        {!p.meets_minimum && (
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input type="checkbox" className="mt-0.5 h-4 w-4 rounded border-slate-300" checked={ignoreMinimum} onChange={(e) => setIgnoreMinimum(e.target.checked)} />
            <span>
              Ignore the minimum payout
              <span className="block text-xs text-slate-500">
                The balance is below the {formatMoney(p.min_payout_amount)} minimum.
              </span>
            </span>
          </label>
        )}
      </div>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Adjustment
// ---------------------------------------------------------------------------

function AdjustmentDialog({ affiliate, open, onClose }: { affiliate: AffiliateDetail; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('')
  const value = Number(amount)
  const valid = amount.trim() !== '' && Number.isFinite(value) && value !== 0 && Math.abs(value) <= 100000 && note.trim().length >= 3

  const add = useMutation({
    mutationFn: () => adminApi.createAffiliateAdjustment({ affiliate_id: affiliate.id, amount: value, note: note.trim() }),
    onSuccess: () => {
      toast.success(value > 0 ? `Credited ${formatMoney(value)}.` : `Debited ${formatMoney(Math.abs(value))}.`)
      invalidateAffiliateData(qc)
      setAmount('')
      setNote('')
      onClose()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <Dialog
      open={open}
      onClose={() => !add.isPending && onClose()}
      title="Add adjustment"
      description="A manual credit or debit (e.g. a commission a webhook missed). It is approved and payable immediately."
      footer={
        <>
          <AdminButton variant="ghost" onClick={onClose} disabled={add.isPending}>Cancel</AdminButton>
          <AdminButton variant="primary" loading={add.isPending} disabled={!valid} onClick={() => add.mutate()}>Add adjustment</AdminButton>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Amount (USD)" hint="Use a negative number to debit.">
          <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className={inputClass} placeholder="25.00" />
        </Field>
        <Field label="Note *" hint="At least 3 characters. The affiliate may see this.">
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} className={cn(inputClass, 'h-auto py-2')} />
        </Field>
      </div>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

function ReferralsTable({ affiliateId }: { affiliateId: string }) {
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliate', affiliateId, 'referrals', page],
    queryFn: () => adminApi.affiliateReferrals(affiliateId, { page, page_size: 10 }),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="rounded-lg border border-slate-200">
      <Table>
        <thead>
          <tr><Th>Customer</Th><Th>Source</Th><Th>Status</Th><Th>Signed up</Th><Th>Converted</Th><Th className="text-right">Earned</Th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={6} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No referrals yet." />
          {data?.items.map((r) => {
            const [tone, label] = REFERRAL_STATUS[r.status] ?? ['neutral', humanize(r.status)]
            return (
              <Tr key={r.id}>
                <Td>
                  <p className="font-medium text-slate-900">{r.organization_name || '—'}</p>
                  <p className="text-xs text-slate-400">{r.email || '—'}</p>
                </Td>
                <Td className="text-slate-500">{humanize(r.source)}</Td>
                <Td><Badge tone={tone} dot>{label}</Badge></Td>
                <Td className="text-slate-500">{formatDate(r.signed_up_at)}</Td>
                <Td className="text-slate-500">{formatDate(r.converted_at)}</Td>
                <Td className="text-right tabular-nums">{formatMoney(r.earned)}</Td>
              </Tr>
            )
          })}
        </tbody>
      </Table>
      {data && data.total > 10 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
    </div>
  )
}

function CommissionsTable({ affiliateId }: { affiliateId: string }) {
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliate-commissions', { affiliate_id: affiliateId, page }],
    queryFn: () => adminApi.affiliateCommissions({ affiliate_id: affiliateId, page, page_size: 10 }),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="rounded-lg border border-slate-200">
      <Table>
        <thead>
          <tr><Th>Earned</Th><Th>Customer</Th><Th>For</Th><Th className="text-right">Amount</Th><Th>Status</Th><Th><span className="sr-only">Actions</span></Th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={6} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No commissions yet." />
          {data?.items.map((c) => (
            <Tr key={c.id}>
              <Td className="text-slate-500">{formatDate(c.earned_at)}</Td>
              <Td>
                <p className="text-slate-800">{c.customer || c.organization_name || '—'}</p>
                {c.customer && c.organization_name && <p className="text-xs text-slate-400">{c.organization_name}</p>}
              </Td>
              <Td className="text-slate-500">
                {c.kind === 'commission' ? billingReasonLabel(c.billing_reason, c.billing_period) || humanize(c.kind) : humanize(c.kind)}
                {c.kind === 'adjustment' && c.note && <p className="max-w-[12rem] truncate text-xs text-slate-400" title={c.note}>{c.note}</p>}
              </Td>
              <Td className={cn('text-right font-medium tabular-nums', moneyClass(c.amount))}>{formatMoney(c.amount, c.currency)}</Td>
              <Td>
                <CommissionStatusBadge status={c.status} />
                {c.status === 'pending' && <p className="mt-0.5 text-xs text-slate-400">{payableIn(c.available_at)}</p>}
              </Td>
              <Td className="text-right"><CommissionActions commission={c} /></Td>
            </Tr>
          ))}
        </tbody>
      </Table>
      {data && data.total > 10 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------

type Confirm = { title: string; description: string; confirm: string; danger?: boolean; status: 'active' | 'suspended' } | null

export function AffiliateDrawer({ affiliateId, onClose }: { affiliateId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const { data: a, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliate', affiliateId],
    queryFn: () => adminApi.affiliate(affiliateId),
  })
  const [editing, setEditing] = useState(false)
  const [paying, setPaying] = useState(false)
  const [adjusting, setAdjusting] = useState(false)
  const [confirm, setConfirm] = useState<Confirm>(null)
  const [invite, setInvite] = useState<{ url: string; sent: boolean; name?: string } | null>(null)

  const setStatus = useMutation({
    mutationFn: (status: 'active' | 'suspended') => adminApi.setAffiliateStatus(affiliateId, status),
    onSuccess: (res) => {
      toast.success(res.status === 'suspended' ? 'Affiliate suspended.' : 'Affiliate reinstated.')
      setConfirm(null)
      qc.setQueryData(['admin', 'affiliate', affiliateId], res)
      qc.invalidateQueries({ queryKey: ['admin', 'affiliates'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const resend = useMutation({
    mutationFn: () => adminApi.resendAffiliateInvite(affiliateId),
    onSuccess: (res) => {
      toast.success(res.invite_sent ? 'Invite email sent.' : 'Invite link created — the email could not be sent.')
      setInvite({ url: res.invite_url, sent: res.invite_sent, name: a?.email ?? undefined })
      qc.invalidateQueries({ queryKey: ['admin', 'affiliate', affiliateId] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const footer = a && (
    <>
      <AdminButton icon={Pencil} onClick={() => setEditing(true)}>Edit</AdminButton>
      {a.status !== 'suspended' && (
        <AdminButton icon={Mail} loading={resend.isPending} onClick={() => resend.mutate()}>
          Resend invite
        </AdminButton>
      )}
      {a.status === 'suspended' ? (
        <AdminButton
          variant="primary"
          icon={PlayCircle}
          onClick={() => setConfirm({
            title: `Reinstate ${a.name}?`,
            description: 'Their referral link and coupon work again and new payments earn commission.',
            confirm: 'Reinstate',
            status: 'active',
          })}
        >
          Reinstate
        </AdminButton>
      ) : (
        <AdminButton
          variant="danger"
          icon={Ban}
          onClick={() => setConfirm({
            title: `Suspend ${a.name}?`,
            description: 'Their referral link and coupon stop working and new payments stop earning commission. Existing commissions and balances are kept.',
            confirm: 'Suspend',
            danger: true,
            status: 'suspended',
          })}
        >
          Suspend
        </AdminButton>
      )}
    </>
  )

  return (
    <Drawer open onClose={onClose} title={a?.name || 'Affiliate'} subtitle={a ? [a.email, a.company].filter(Boolean).join(' · ') : undefined} footer={footer || undefined}>
      {error ? (
        <Callout tone="danger" title="Could not load this affiliate">{errorText(error)}</Callout>
      ) : isLoading || !a ? (
        <div className="h-40 animate-pulse rounded-lg bg-slate-50" />
      ) : (
        <div className="space-y-7">
          <div className="flex flex-wrap items-center gap-2">
            <AffiliateStatusBadge status={a.status} />
            <StripeStateBadge state={a.stripe.state} />
            {a.status === 'invited' && !a.has_password && <Badge tone="warning">Hasn’t set a password</Badge>}
            <span className="text-xs text-slate-400">
              {a.activated_at ? `Active since ${formatDate(a.activated_at)}` : a.invited_at ? `Invited ${formatDate(a.invited_at)}` : `Created ${formatDate(a.created_at)}`}
            </span>
          </div>

          <section>
            <SectionTitle>Balance</SectionTitle>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <StatCard label="Pending" value={formatMoney(a.balance.pending)} hint="In hold period" />
              <StatCard label="Available" value={formatMoney(a.balance.available)} tone="success" />
              <StatCard label="In payout" value={formatMoney(a.balance.in_payout)} />
              <StatCard label="Paid" value={formatMoney(a.balance.paid)} />
              <StatCard label="Lifetime" value={formatMoney(a.balance.lifetime)} />
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-3">
              <div className="text-sm">
                <p className="font-medium text-slate-800">{formatMoney(a.payout.available)} ready to pay</p>
                <p className="text-xs text-slate-500">
                  Minimum payout {formatMoney(a.payout.min_payout_amount)}
                  {!a.payout.meets_minimum && a.payout.available > 0 && ' — below minimum'}
                  {a.payout.processing > 0 && ` · ${a.payout.processing} payout${a.payout.processing === 1 ? '' : 's'} processing`}
                </p>
              </div>
              <AdminButton variant="primary" icon={Banknote} disabled={a.payout.available <= 0} onClick={() => setPaying(true)}>
                Pay {formatMoney(a.payout.available)} now
              </AdminButton>
            </div>
          </section>

          <section>
            <SectionTitle>Activity</SectionTitle>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Detail label="Clicks">{a.stats.clicks.toLocaleString()}</Detail>
              <Detail label="Clicks (30d)">{a.stats.clicks_30d.toLocaleString()}</Detail>
              <Detail label="Referrals">{a.stats.referrals.toLocaleString()}</Detail>
              <Detail label="Conversions">{a.stats.conversions.toLocaleString()}</Detail>
            </dl>
          </section>

          <section>
            <SectionTitle>Links</SectionTitle>
            <div className="space-y-2">
              <Field label="Landing page"><CopyField value={a.links.landing} label="Landing link" /></Field>
              <Field label="Sign-up page"><CopyField value={a.links.signup} label="Sign-up link" /></Field>
            </div>
          </section>

          <section>
            <SectionTitle>Terms</SectionTitle>
            <dl className="grid grid-cols-2 gap-4">
              <Detail label="Earns on">{COMMISSION_PERIOD_LABELS[a.commission_billing_periods ?? 'yearly']}</Detail>
              <Detail label="Commission">
                {a.commission_billing_periods !== 'monthly' && <span className="block">{a.commission_percent}% of annual payments</span>}
                {a.commission_billing_periods !== 'yearly' && (
                  <span className="block">{a.commission_percent_monthly ?? a.commission_percent}% of monthly payments</span>
                )}
              </Detail>
              <Detail label="Referral code"><span className="font-mono">{a.referral_code}</span></Detail>
              <Detail label="Commissioned payments / customer">
                {a.custom_max_payments ? (
                  <>
                    {a.commission_billing_periods !== 'monthly' && (
                      <span className="block">Annual: {a.max_commission_payments ?? 'unlimited'} (custom)</span>
                    )}
                    {a.commission_billing_periods !== 'yearly' && (
                      <span className="block">Monthly: {a.max_monthly_commission_payments ?? 'unlimited'} (custom)</span>
                    )}
                  </>
                ) : (
                  'Program default'
                )}
              </Detail>
              <Detail label="Coupon">
                {a.coupon ? (
                  <span>
                    <span className="font-mono">{a.coupon.code}</span> — {a.coupon.description}
                    <span className="block text-xs text-slate-500">
                      {a.coupon.applies_to === 'yearly' ? 'Annual plans only' : 'All plans'}
                      {!a.coupon.active && ' · inactive'}
                    </span>
                  </span>
                ) : '—'}
              </Detail>
            </dl>
            {a.notes && (
              <div className="mt-4">
                <Detail label="Internal notes"><span className="whitespace-pre-wrap">{a.notes}</span></Detail>
              </div>
            )}
          </section>

          <section>
            <SectionTitle>Stripe</SectionTitle>
            {!a.stripe.connect_available && (
              <div className="mb-3"><Callout tone="warning">Stripe is not configured on the platform — only manual payouts are possible.</Callout></div>
            )}
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <Detail label="State"><StripeStateBadge state={a.stripe.state} /></Detail>
              <Detail label="Account">{a.stripe.account_id ? <span className="font-mono text-xs">{a.stripe.account_id}</span> : '—'}</Detail>
              <Detail label="Country">{a.stripe.country?.toUpperCase() || '—'}</Detail>
              <Detail label="Details submitted"><YesNo value={a.stripe.details_submitted} /></Detail>
              <Detail label="Transfers enabled"><YesNo value={a.stripe.transfers_enabled} /></Detail>
              <Detail label="Payouts enabled"><YesNo value={a.stripe.payouts_enabled} /></Detail>
            </dl>
            {a.stripe.checked_at && <p className="mt-2 text-xs text-slate-400">Last checked {formatDate(a.stripe.checked_at, true)}</p>}
          </section>

          <section>
            <SectionTitle>Referrals</SectionTitle>
            <ReferralsTable affiliateId={a.id} />
          </section>

          <section>
            <SectionTitle actions={<AdminButton className="h-8 px-2.5 text-xs" icon={Plus} onClick={() => setAdjusting(true)}>Add adjustment</AdminButton>}>
              Commissions
            </SectionTitle>
            <CommissionsTable affiliateId={a.id} />
          </section>

          <AffiliateFormDialog open={editing} onClose={() => setEditing(false)} affiliate={a} />
          <PayoutDialog affiliate={a} open={paying} onClose={() => setPaying(false)} />
          <AdjustmentDialog affiliate={a} open={adjusting} onClose={() => setAdjusting(false)} />
        </div>
      )}

      <Dialog
        open={!!confirm}
        onClose={() => !setStatus.isPending && setConfirm(null)}
        title={confirm?.title}
        description={confirm?.description}
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setConfirm(null)} disabled={setStatus.isPending}>Cancel</AdminButton>
            <AdminButton variant={confirm?.danger ? 'danger' : 'primary'} loading={setStatus.isPending} onClick={() => confirm && setStatus.mutate(confirm.status)}>
              {confirm?.confirm}
            </AdminButton>
          </>
        }
      />
      <InviteLinkDialog invite={invite} onClose={() => setInvite(null)} />
    </Drawer>
  )
}
