'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, AlertTriangle, Loader2, ShieldCheck } from 'lucide-react'
import { PhoneDialog } from '@/components/phone-numbers/PhoneDialog'
import { OtpInput } from '@/components/auth/OtpInput'
import { PasswordInput } from '@/components/ui/password-input'
import { authService, type DeactivationTerms } from '@/lib/auth'
import { getErrorMessage } from '@/lib/api'
import { formatDate } from '@/lib/datetime'

const FIELD_CLASS =
  'h-[45px] w-full rounded-xl border border-slate-200 bg-white px-3 font-poppins text-[14px] text-[#000000] outline-none transition-colors placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15'
const PRIMARY =
  'inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white hover:bg-[#0c5a4b] disabled:opacity-50'
const DANGER =
  'inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-red-600 px-5 text-[14px] font-semibold text-white hover:bg-red-700 disabled:opacity-50'
const SECONDARY =
  'inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50'

/** The API refuses a second code to the same address inside a minute. */
const RESEND_SECONDS = 60

interface Props {
  open: boolean
  onClose: () => void
  email: string
  /** False for accounts that only sign in with Google or Apple. */
  hasPassword: boolean
  /** The account is deactivated and this browser's session is already cleared. */
  onDeactivated: () => void
}

/**
 * Deactivating the account, in two steps: prove it is you, then read what will
 * happen and confirm. Nothing changes on the account until the final button,
 * so closing the dialog at any point is safe.
 *
 * An account with a password proves it with the password. One that signs in
 * with Google or Apple has none, so it is sent a code instead.
 */
export function DeactivateAccountDialog({ open, onClose, email, hasPassword, onDeactivated }: Props) {
  const [step, setStep] = useState<'verify' | 'confirm'>('verify')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [codeSent, setCodeSent] = useState(false)
  const [resendIn, setResendIn] = useState(0)
  const [terms, setTerms] = useState<DeactivationTerms | null>(null)
  const [understood, setUnderstood] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!open) return
    setStep('verify')
    setPassword('')
    setCode('')
    setCodeSent(false)
    setResendIn(0)
    setTerms(null)
    setUnderstood(false)
    setBusy(false)
    setError('')
    setNotice('')
  }, [open])

  useEffect(() => {
    if (resendIn <= 0) return
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  const sendCode = async () => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await authService.sendDeactivationCode()
      setCodeSent(true)
      setResendIn(RESEND_SECONDS)
      setCode(res.debug_code ?? '')
      if (res.debug_code) setNotice(`Dev mode: no email was sent. Your code is ${res.debug_code}.`)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const verify = async (submittedCode = code) => {
    if (busy) return
    if (hasPassword ? !password : submittedCode.length < 6) return
    setBusy(true)
    setError('')
    try {
      const result = await authService.verifyDeactivation(
        hasPassword ? { password } : { code: submittedCode },
      )
      setTerms(result)
      setStep('confirm')
    } catch (e) {
      setError(getErrorMessage(e))
      if (!hasPassword) setCode('')
    } finally {
      setBusy(false)
    }
  }

  const deactivate = async () => {
    if (!terms || !understood || busy) return
    setBusy(true)
    setError('')
    try {
      await authService.deactivateAccount(terms.deactivation_token)
      onDeactivated()
    } catch (e) {
      setError(getErrorMessage(e))
      setBusy(false)
    }
  }

  const canVerify = hasPassword ? !!password : codeSent && code.length >= 6

  return (
    <PhoneDialog
      open={open}
      onClose={onClose}
      busy={busy}
      size="md"
      title={step === 'verify' ? 'Confirm it’s you' : 'Deactivate your account?'}
      description={
        step === 'verify'
          ? 'Before you deactivate your account, we need to check it is really you.'
          : 'Please read this before you continue.'
      }
      icon={
        step === 'verify' ? (
          <ShieldCheck className="h-5 w-5" />
        ) : (
          <AlertTriangle className="h-5 w-5 text-red-600" />
        )
      }
      footer={
        step === 'verify' ? (
          <>
            <button type="button" onClick={onClose} disabled={busy} className={SECONDARY}>
              Cancel
            </button>
            {hasPassword || codeSent ? (
              <button
                type="submit"
                form="deactivate-verify-form"
                disabled={busy || !canVerify}
                className={PRIMARY}
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                {busy ? 'Checking…' : 'Continue'}
              </button>
            ) : (
              <button type="button" onClick={sendCode} disabled={busy} className={PRIMARY}>
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                {busy ? 'Sending…' : 'Email me a code'}
              </button>
            )}
          </>
        ) : (
          <>
            <button type="button" onClick={onClose} disabled={busy} className={SECONDARY}>
              Keep my account
            </button>
            <button type="button" onClick={deactivate} disabled={busy || !understood} className={DANGER}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? 'Deactivating…' : 'Deactivate account'}
            </button>
          </>
        )
      }
    >
      {step === 'verify' ? (
        <form
          id="deactivate-verify-form"
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            verify()
          }}
        >
          {hasPassword ? (
            <div className="space-y-1.5">
              <label
                htmlFor="deactivate-password"
                className="block font-poppins text-[14px] font-bold text-[#000000]"
              >
                Your password <span className="text-red-500">*</span>
              </label>
              <PasswordInput
                id="deactivate-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  setError('')
                }}
                autoComplete="current-password"
                autoFocus
                className={FIELD_CLASS}
              />
              <p className="text-xs text-slate-500">
                Enter the password for <span className="break-all font-medium text-slate-700">{email}</span>.
                Nothing is deactivated at this step.
              </p>
            </div>
          ) : !codeSent ? (
            <p className="text-[14px] leading-relaxed text-slate-700">
              Your account signs in with Google or Apple, so there is no password to ask for. We&apos;ll
              email a 6-digit code to{' '}
              <strong className="break-all font-semibold text-slate-900">{email}</strong> instead.
              Nothing is deactivated at this step.
            </p>
          ) : (
            <div className="space-y-4">
              <p className="text-[14px] leading-relaxed text-slate-700">
                Enter the 6-digit code we sent to{' '}
                <strong className="break-all font-semibold text-slate-900">{email}</strong>.
              </p>
              <OtpInput
                value={code}
                onChange={(v) => {
                  setCode(v)
                  setError('')
                }}
                onComplete={verify}
                disabled={busy}
                autoFocus
              />
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-slate-500">
                <span>Didn&apos;t get it? Check your spam folder.</span>
                <button
                  type="button"
                  onClick={sendCode}
                  disabled={busy || resendIn > 0}
                  className="font-semibold text-[#0F6A59] hover:underline disabled:text-slate-400 disabled:no-underline"
                >
                  {resendIn > 0 ? `Resend in ${resendIn}s` : 'Send a new code'}
                </button>
              </div>
            </div>
          )}

          {notice && (
            <p
              role="status"
              className="rounded-xl border border-[#0F6A59]/30 bg-[#0F6A59]/[0.04] px-3 py-2.5 text-[13px] text-[#0F6A59]"
            >
              {notice}
            </p>
          )}
          {error && <ErrorNote>{error}</ErrorNote>}
        </form>
      ) : (
        terms && (
          <div className="space-y-4">
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3.5 text-[14px] leading-relaxed text-red-900">
              Your account will be <strong>deactivated immediately</strong> and will be{' '}
              <strong>
                permanently deleted after {terms.retention_days} day{terms.retention_days === 1 ? '' : 's'}
              </strong>{' '}
              (on {formatDate(terms.deletion_date, { month: 'long' })}).
            </div>

            <p className="text-[14px] leading-relaxed text-slate-700">
              If you want to reactivate your account within this period, please contact us at{' '}
              <a
                href={`mailto:${terms.support_email}`}
                className="break-all font-semibold text-[#0F6A59] hover:underline"
              >
                {terms.support_email}
              </a>
              . Our support team will reactivate your account within 2 business days.
            </p>

            <ul className="list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-slate-600">
              <li>You are signed out everywhere and can no longer sign in.</li>
              <li>
                Workspaces you own are switched off: agents stop answering calls and workflows stop
                running, for you and for anyone you invited.
              </li>
              <li>Any subscription on those workspaces is cancelled now. Nothing more is charged.</li>
              <li>
                After {terms.retention_days} day{terms.retention_days === 1 ? '' : 's'} the account
                cannot be recovered. This email address can then be used to create a new account.
              </li>
            </ul>

            <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-slate-200 px-3 py-3 text-[14px] text-slate-800">
              <input
                type="checkbox"
                checked={understood}
                onChange={(e) => setUnderstood(e.target.checked)}
                disabled={busy}
                className="mt-0.5 h-4 w-4 flex-shrink-0 rounded border-slate-300 text-red-600 focus:ring-red-500"
              />
              <span>I understand, and I want to deactivate my account.</span>
            </label>

            {error && <ErrorNote>{error}</ErrorNote>}
          </div>
        )
      )}
    </PhoneDialog>
  )
}

function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-700"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
      <span>{children}</span>
    </div>
  )
}
