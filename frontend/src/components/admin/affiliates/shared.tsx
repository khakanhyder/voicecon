'use client'

/** Pieces shared by the affiliate pages of the admin console. */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Check, Copy, XCircle } from 'lucide-react'
import {
  adminApi,
  type AffiliateCommission,
  type AffiliatePayout,
  type AffiliateStatus,
  type StripeConnectState,
} from '@/lib/admin'
import { AdminButton, Badge, Dialog, Field, errorText, humanize, inputClass, parseDate, type Tone } from '@/components/admin/ui'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Copy
// ---------------------------------------------------------------------------

export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy. Select the text and copy it by hand.')
    }
  }
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        copy()
      }}
      aria-label={label}
      title={label}
      className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700"
    >
      {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
    </button>
  )
}

/** A read-only value with a copy button next to it. */
export function CopyField({ value, label }: { value: string; label?: string }) {
  return (
    <div className="flex items-center gap-2">
      <input readOnly value={value} aria-label={label} className={cn(inputClass, 'font-mono text-xs')} onFocus={(e) => e.target.select()} />
      <CopyButton value={value} label={label ? `Copy ${label.toLowerCase()}` : 'Copy'} />
    </div>
  )
}

/** Shows an invite link after create / resend — email may not deliver, so the link is always offered. */
export function InviteLinkDialog({
  invite,
  onClose,
}: {
  invite: { url: string; sent: boolean; name?: string } | null
  onClose: () => void
}) {
  return (
    <Dialog
      open={!!invite}
      onClose={onClose}
      title="Portal invite link"
      description={
        invite?.sent
          ? `An invite email was sent${invite.name ? ` to ${invite.name}` : ''}. You can also share this link directly.`
          : 'No email was sent (or it could not be delivered). Share this link with the affiliate so they can set a password.'
      }
      footer={<AdminButton variant="primary" onClick={onClose}>Done</AdminButton>}
    >
      {invite && <CopyField value={invite.url} label="Invite link" />}
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Badges and labels
// ---------------------------------------------------------------------------

function ToneBadge({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <Badge tone={tone} dot>
      {children}
    </Badge>
  )
}

export function AffiliateStatusBadge({ status }: { status: AffiliateStatus }) {
  const tone: Tone = status === 'active' ? 'success' : status === 'invited' ? 'info' : 'danger'
  return <ToneBadge tone={tone}>{humanize(status)}</ToneBadge>
}

export function StripeStateBadge({ state }: { state: StripeConnectState }) {
  const map: Record<StripeConnectState, [Tone, string]> = {
    ready: ['success', 'Stripe ready'],
    incomplete: ['warning', 'Stripe incomplete'],
    not_connected: ['neutral', 'Not connected'],
  }
  const [tone, label] = map[state] ?? ['neutral', humanize(state)]
  return <ToneBadge tone={tone}>{label}</ToneBadge>
}

export function CommissionStatusBadge({ status }: { status: AffiliateCommission['status'] }) {
  const tones: Record<string, Tone> = {
    pending: 'warning',
    approved: 'info',
    paid: 'success',
    reversed: 'neutral',
    rejected: 'danger',
  }
  return <ToneBadge tone={tones[status] ?? 'neutral'}>{humanize(status)}</ToneBadge>
}

export function PayoutStatusBadge({ status }: { status: AffiliatePayout['status'] }) {
  const tones: Record<string, Tone> = { processing: 'warning', paid: 'success', failed: 'danger' }
  return <ToneBadge tone={tones[status] ?? 'neutral'}>{humanize(status)}</ToneBadge>
}

export function billingReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case 'subscription_create':
      return 'New annual'
    case 'subscription_cycle':
      return 'Annual renewal'
    case 'subscription_update':
      return 'Upgrade'
    default:
      return reason ? humanize(reason) : ''
  }
}

export const REFERRAL_STATUS: Record<string, [Tone, string]> = {
  signed_up: ['neutral', 'Signed up'],
  trial: ['info', 'Trial'],
  paying_monthly: ['brand', 'Paying monthly'],
  paying_annual: ['success', 'Paying annual'],
  canceled: ['neutral', 'Canceled'],
  lapsed: ['warning', 'Lapsed'],
}

/** "payable in 3 days" / "payable now" for a pending commission. */
export function payableIn(availableAt: string | null): string {
  const d = parseDate(availableAt)
  if (!d) return '—'
  const days = Math.ceil((d.getTime() - Date.now()) / 86_400_000)
  if (days <= 0) return 'payable now'
  return `payable in ${days} day${days === 1 ? '' : 's'}`
}

export function moneyClass(amount: number): string {
  return amount < 0 ? 'text-rose-600' : ''
}

// ---------------------------------------------------------------------------
// Commission actions (approve early / reject)
// ---------------------------------------------------------------------------

export function canReject(c: AffiliateCommission): boolean {
  return (c.status === 'pending' || c.status === 'approved') && !c.payout_id
}

export function invalidateAffiliateData(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['admin', 'affiliate-commissions'] })
  qc.invalidateQueries({ queryKey: ['admin', 'affiliates'] })
  qc.invalidateQueries({ queryKey: ['admin', 'affiliate'] })
}

/** Approve-early and reject buttons for one commission row, with the reject dialog. */
export function CommissionActions({ commission }: { commission: AffiliateCommission }) {
  const qc = useQueryClient()
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  const approve = useMutation({
    mutationFn: () => adminApi.approveAffiliateCommission(commission.id),
    onSuccess: () => {
      toast.success('Commission approved — it is payable now.')
      invalidateAffiliateData(qc)
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const reject = useMutation({
    mutationFn: () => adminApi.rejectAffiliateCommission(commission.id, reason.trim()),
    onSuccess: () => {
      toast.success('Commission rejected.')
      setRejecting(false)
      setReason('')
      invalidateAffiliateData(qc)
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const showApprove = commission.status === 'pending'
  const showReject = canReject(commission)
  if (!showApprove && !showReject) return null

  return (
    <div className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
      {showApprove && (
        <AdminButton className="h-8 px-2.5 text-xs" loading={approve.isPending} onClick={() => approve.mutate()}>
          Approve early
        </AdminButton>
      )}
      {showReject && (
        <AdminButton variant="ghost" icon={XCircle} className="h-8 px-2.5 text-xs text-rose-600 hover:bg-rose-50" onClick={() => setRejecting(true)}>
          Reject
        </AdminButton>
      )}
      <Dialog
        open={rejecting}
        onClose={() => !reject.isPending && setRejecting(false)}
        title="Reject this commission?"
        description={`${commission.affiliate_name ? `${commission.affiliate_name} will` : 'The affiliate will'} not be paid this ${humanize(commission.kind).toLowerCase()}. Use this for fraud, self-referrals or mistakes.`}
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setRejecting(false)} disabled={reject.isPending}>Cancel</AdminButton>
            <AdminButton variant="danger" loading={reject.isPending} disabled={reason.trim().length < 3} onClick={() => reject.mutate()}>
              Reject commission
            </AdminButton>
          </>
        }
      >
        <Field label="Reason" hint="At least 3 characters. Saved on the commission and in the audit log.">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className={cn(inputClass, 'h-auto py-2')}
            placeholder="e.g. Self-referral — same card as the affiliate"
          />
        </Field>
      </Dialog>
    </div>
  )
}
