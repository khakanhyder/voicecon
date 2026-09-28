'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, Loader2, Mail, MailCheck } from 'lucide-react'
import { PhoneDialog } from '@/components/phone-numbers/PhoneDialog'
import { OtpInput } from '@/components/auth/OtpInput'
import { PasswordInput } from '@/components/ui/password-input'
import { authService, type User } from '@/lib/auth'
import { getErrorMessage } from '@/lib/api'

const FIELD_CLASS =
  'h-[45px] w-full rounded-xl border border-slate-200 bg-white px-3 font-poppins text-[14px] text-[#000000] outline-none transition-colors placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15'
const PRIMARY =
  'inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white hover:bg-[#0c5a4b] disabled:opacity-50'
const SECONDARY =
  'inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50'

/** The API refuses a second code to the same address inside a minute. */
const RESEND_SECONDS = 60
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface Props {
  open: boolean
  onClose: () => void
  currentEmail: string
  /** False for accounts that only sign in with Google or Apple. */
  hasPassword: boolean
  onChanged: (user: User) => void
}

/**
 * Changing the account email, in two steps: say where to move to, then prove
 * it with the code sent there. The account keeps its current address until
 * the code is accepted, so closing the dialog at any point changes nothing.
 */
export function ChangeEmailDialog({ open, onClose, currentEmail, hasPassword, onChanged }: Props) {
  const [step, setStep] = useState<'address' | 'code'>('address')
  const [newEmail, setNewEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [expiresIn, setExpiresIn] = useState(10)
  const [resendIn, setResendIn] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!open) return
    setStep('address')
    setNewEmail('')
    setPassword('')
    setCode('')
    setResendIn(0)
    setBusy(false)
    setError('')
    setNotice('')
  }, [open])

  useEffect(() => {
    if (resendIn <= 0) return
    const timer = setTimeout(() => setResendIn(s => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  const address = newEmail.trim().toLowerCase()
  const sameAsCurrent = address === currentEmail.trim().toLowerCase()
  const canSend = EMAIL_SHAPE.test(address) && !sameAsCurrent && (!hasPassword || !!password)

  const sendCode = async (resend = false) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await authService.requestEmailChange({
        new_email: address,
        ...(hasPassword ? { current_password: password } : {}),
      })
      setExpiresIn(res.expires_in_minutes)
      setResendIn(RESEND_SECONDS)
      setCode(res.debug_code ?? '')
      setStep('code')
      if (res.debug_code) setNotice(`Dev mode: no email was sent. Your code is ${res.debug_code}.`)
      else if (resend) setNotice(`We sent a new code to ${address}. The earlier one no longer works.`)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const confirm = async (submitted = code) => {
    if (submitted.length < 6 || busy) return
    setBusy(true)
    setError('')
    try {
      onChanged(await authService.confirmEmailChange({ new_email: address, code: submitted }))
    } catch (e) {
      setError(getErrorMessage(e))
      setCode('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <PhoneDialog
      open={open}
      onClose={onClose}
      busy={busy}
      size="md"
      title={step === 'address' ? 'Change email address' : 'Check your new inbox'}
      description={
        step === 'address'
          ? "We'll send a code to the new address to confirm it's yours."
          : 'Your email address has not changed yet.'
      }
      icon={step === 'address' ? <Mail className="h-5 w-5" /> : <MailCheck className="h-5 w-5" />}
      footer={
        step === 'address' ? (
          <>
            <button type="button" onClick={onClose} disabled={busy} className={SECONDARY}>
              Cancel
            </button>
            <button type="submit" form="change-email-form" disabled={busy || !canSend} className={PRIMARY}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? 'Sending…' : 'Send code'}
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={onClose} disabled={busy} className={SECONDARY}>
              Cancel
            </button>
            <button type="button" onClick={() => confirm()} disabled={busy || code.length < 6} className={PRIMARY}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? 'Confirming…' : 'Confirm new email'}
            </button>
          </>
        )
      }
    >
      {step === 'address' ? (
        <form
          id="change-email-form"
          className="space-y-4"
          onSubmit={e => {
            e.preventDefault()
            if (canSend && !busy) sendCode()
          }}
        >
          <div className="space-y-1.5">
            <span className="block font-poppins text-[14px] font-bold text-[#000000]">Current email</span>
            <div className="flex h-[45px] items-center truncate rounded-xl border border-slate-200 bg-slate-50 px-3 font-poppins text-sm text-slate-600">
              {currentEmail}
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="new-email" className="block font-poppins text-[14px] font-bold text-[#000000]">
              New email <span className="text-red-500">*</span>
            </label>
            <input
              id="new-email"
              type="email"
              value={newEmail}
              onChange={e => { setNewEmail(e.target.value); setError('') }}
              placeholder="you@company.com"
              autoComplete="email"
              autoFocus
              className={FIELD_CLASS}
            />
            {sameAsCurrent && address && (
              <p className="text-xs text-amber-700">That is already your email address.</p>
            )}
          </div>

          {hasPassword && (
            <div className="space-y-1.5">
              <label htmlFor="change-email-password" className="block font-poppins text-[14px] font-bold text-[#000000]">
                Your password <span className="text-red-500">*</span>
              </label>
              <PasswordInput
                id="change-email-password"
                value={password}
                onChange={e => { setPassword(e.target.value); setError('') }}
                autoComplete="current-password"
                className={FIELD_CLASS}
              />
              <p className="text-xs text-slate-500">So we know it is really you making this change.</p>
            </div>
          )}

          {error && <ErrorNote>{error}</ErrorNote>}
        </form>
      ) : (
        <div className="space-y-5">
          <p className="text-[14px] leading-relaxed text-slate-700">
            Enter the 6-digit code we sent to{' '}
            <strong className="break-all font-semibold text-slate-900">{address}</strong>. It expires in{' '}
            {expiresIn} minutes.
          </p>

          <OtpInput value={code} onChange={v => { setCode(v); setError('') }} onComplete={confirm} disabled={busy} autoFocus />

          {notice && (
            <p role="status" className="rounded-xl border border-[#0F6A59]/30 bg-[#0F6A59]/[0.04] px-3 py-2.5 text-[13px] text-[#0F6A59]">
              {notice}
            </p>
          )}
          {error && <ErrorNote>{error}</ErrorNote>}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-slate-500">
            <span>Didn&apos;t get it? Check your spam folder.</span>
            <button
              type="button"
              onClick={() => sendCode(true)}
              disabled={busy || resendIn > 0}
              className="font-semibold text-[#0F6A59] hover:underline disabled:text-slate-400 disabled:no-underline"
            >
              {resendIn > 0 ? `Resend in ${resendIn}s` : 'Send a new code'}
            </button>
            <button
              type="button"
              onClick={() => { setStep('address'); setCode(''); setError(''); setNotice('') }}
              disabled={busy}
              className="font-semibold text-[#0F6A59] hover:underline disabled:text-slate-400"
            >
              Use a different email
            </button>
          </div>
        </div>
      )}
    </PhoneDialog>
  )
}

function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-700">
      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
      <span>{children}</span>
    </div>
  )
}
