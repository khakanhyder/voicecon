'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { ArrowLeft, Eye, EyeOff, Loader2, Lock, Mail } from 'lucide-react'
import { authService } from '@/lib/auth'
import { OtpInput } from '@/components/auth/OtpInput'
import { useAuthStore } from '@/store/authStore'

const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-[#243275] focus:ring-3 focus:ring-[#243275]/15 disabled:opacity-50'

/**
 * Forgotten-password reset.
 *
 * Two steps on one screen: ask for the address, then take the emailed code plus
 * the new password. A correct reset signs the user straight in — they have just
 * proved the address and chosen a password, so the login form would be busywork.
 */
export default function ForgotPasswordPage() {
  const router = useRouter()
  const setUser = useAuthStore((s) => s.setUser)

  const [step, setStep] = useState<'email' | 'reset'>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isResetting, setIsResetting] = useState(false)
  const [resendIn, setResendIn] = useState(0)

  useEffect(() => {
    if (resendIn <= 0) return
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  const sendCode = async () => {
    if (!email.trim()) {
      setError('Enter your email address')
      return
    }
    setError('')
    setIsSending(true)
    try {
      const res = await authService.forgotPassword(email.trim())
      setStep('reset')
      setResendIn(60)
      toast.success(res.message)
      if (res.debug_code) {
        setCode(res.debug_code)
        toast.info(`Dev mode — your code is ${res.debug_code}`)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not send the reset code')
    } finally {
      setIsSending(false)
    }
  }

  const resetPassword = async () => {
    setError('')
    if (code.length < 6) {
      setError('Enter the 6-digit code from your email')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setIsResetting(true)
    try {
      const data = await authService.resetPassword({
        email: email.trim(),
        code,
        new_password: password,
      })
      setUser(data.user)
      toast.success('Password updated — you are signed in')
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not reset your password')
      setCode('')
    } finally {
      setIsResetting(false)
    }
  }

  return (
    <div className="w-full max-w-md px-1">
      <div className="mb-7">
        <h1 className="text-[28px] font-medium text-slate-900 md:text-3xl md:font-bold">
          {step === 'email' ? 'Forgot your password?' : 'Choose a new password'}
        </h1>
        <p className="mt-2 text-base text-slate-600">
          {step === 'email'
            ? 'Enter your email and we’ll send you a code to reset it.'
            : `Enter the 6-digit code we sent to ${email.trim()} and pick a new password.`}
        </p>
      </div>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-red-100 text-xs font-bold text-red-500">
            !
          </span>
          {error}
        </div>
      )}

      {step === 'email' ? (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            sendCode()
          }}
          className="space-y-5"
        >
          <div className="space-y-1.5">
            <label htmlFor="email" className="block text-base font-semibold text-slate-800">
              Email Id :
            </label>
            <div className="relative">
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  if (error) setError('')
                }}
                placeholder="info@voicecon.com"
                required
                disabled={isSending}
                className={`${inputClass} pr-10`}
              />
              <Mail className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSending}
            className="shadow-base w-full rounded-lg bg-[#243275] px-4 py-3 text-base font-semibold text-white transition-all hover:bg-[#1c2960] focus:outline-none focus:ring-3 focus:ring-[#243275]/30 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSending ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Sending code…
              </span>
            ) : (
              'Send reset code'
            )}
          </button>
        </form>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            resetPassword()
          }}
          className="space-y-5"
        >
          <div className="space-y-1.5">
            <label className="block text-base font-semibold text-slate-800">
              Verification code
            </label>
            <OtpInput value={code} onChange={setCode} disabled={isResetting} autoFocus />
            <button
              type="button"
              onClick={sendCode}
              disabled={resendIn > 0 || isSending}
              className="pt-1 text-sm font-medium text-slate-500 transition-colors hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {resendIn > 0 ? `Resend in ${resendIn}s` : 'Send a new code'}
            </button>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="block text-base font-semibold text-slate-800">
              New password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={isResetting}
                className={`${inputClass} pl-10 pr-10`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-600"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="text-xs text-slate-500">At least 8 characters.</p>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="confirmPassword"
              className="block text-base font-semibold text-slate-800"
            >
              Confirm new password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={isResetting}
                className={`${inputClass} pl-10`}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isResetting}
            className="shadow-base w-full rounded-lg bg-[#243275] px-4 py-3 text-base font-semibold text-white transition-all hover:bg-[#1c2960] focus:outline-none focus:ring-3 focus:ring-[#243275]/30 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isResetting ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Updating password…
              </span>
            ) : (
              'Reset password'
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setStep('email')
              setCode('')
              setError('')
            }}
            className="text-sm font-medium text-slate-500 transition-colors hover:text-slate-700"
          >
            Use a different email
          </button>
        </form>
      )}

      <p className="mt-6 flex items-center gap-1.5 text-sm text-slate-600">
        <ArrowLeft className="h-4 w-4" />
        <Link href="/login" className="font-semibold text-brand-600 hover:text-brand-700">
          Back to sign in
        </Link>
      </p>
    </div>
  )
}
