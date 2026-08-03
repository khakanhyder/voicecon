'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { authService } from '@/lib/auth'
import { SocialAuthButtons } from '@/components/auth/SocialAuthButtons'
import { OtpInput } from '@/components/auth/OtpInput'
import { BadgeCheck, Eye, EyeOff, Loader2, Mail, Lock, Phone, User } from 'lucide-react'

const COUNTRY_CODES = [
  { code: '+1', flag: '🇺🇸' },
  { code: '+44', flag: '🇬🇧' },
  { code: '+91', flag: '🇮🇳' },
  { code: '+92', flag: '🇵🇰' },
  { code: '+61', flag: '🇦🇺' },
  { code: '+971', flag: '🇦🇪' },
]

export default function RegisterPage() {
  const { register, isRegistering } = useAuth()
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    phone: '',
  })
  const [dialCode, setDialCode] = useState('+1')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  // ── Email verification ────────────────────────────────────────────────────
  // The account is only created for an address the user has proved they own, so
  // the code step gates the submit button.
  const [codeSent, setCodeSent] = useState(false)
  const [code, setCode] = useState('')
  const [isSendingCode, setIsSendingCode] = useState(false)
  const [isVerifying, setIsVerifying] = useState(false)
  const [verifiedEmail, setVerifiedEmail] = useState<string | null>(null)
  const [verificationToken, setVerificationToken] = useState('')
  const [resendIn, setResendIn] = useState(0)

  const emailIsVerified =
    !!verifiedEmail && verifiedEmail === formData.email.trim().toLowerCase()

  // Countdown for the resend link; the API refuses a resend inside a minute.
  useEffect(() => {
    if (resendIn <= 0) return
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData({ ...formData, [name]: value })
    if (error) setError('')
    // Editing the address invalidates the code that was sent to the old one.
    if (name === 'email') {
      setCodeSent(false)
      setCode('')
    }
  }

  /** Unlock the email field so a wrong address can be corrected. */
  const clearVerification = () => {
    setVerifiedEmail(null)
    setVerificationToken('')
    setCodeSent(false)
    setCode('')
  }

  const sendCode = async () => {
    const email = formData.email.trim()
    if (!email) {
      setError('Enter your email address first')
      return
    }
    setError('')
    setIsSendingCode(true)
    try {
      const res = await authService.sendEmailCode(email)
      setCodeSent(true)
      setResendIn(60)
      toast.success(res.message)
      if (res.debug_code) {
        // Local dev with no mail server: skip the inbox round-trip.
        setCode(res.debug_code)
        toast.info(`Dev mode — your code is ${res.debug_code}`)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not send the verification code')
    } finally {
      setIsSendingCode(false)
    }
  }

  const submitCode = async (submitted: string) => {
    setError('')
    setIsVerifying(true)
    try {
      const res = await authService.verifyEmailCode(formData.email.trim(), submitted)
      setVerifiedEmail(res.email)
      setVerificationToken(res.email_verification_token)
      setCodeSent(false)
      toast.success('Email verified')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not verify that code')
      setCode('')
    } finally {
      setIsVerifying(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!emailIsVerified) {
      setError('Please verify your email address before creating your account')
      return
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    register({
      email: formData.email.trim(),
      password: formData.password,
      full_name: formData.full_name || undefined,
      phone_number: formData.phone ? `${dialCode} ${formData.phone}`.trim() : undefined,
      email_verification_token: verificationToken,
    })
  }

  const inputClass =
    'w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-[#243275] focus:ring-3 focus:ring-[#243275]/15 disabled:opacity-50'

  return (
    <div className="w-full max-w-md px-1 lg:max-w-4xl">
      <div className="mb-7">
        <h1 className="text-[28px] font-medium text-slate-900 md:text-3xl md:font-bold">
          Sign Up into your account
        </h1>
        <p className="mt-2 text-base text-[#000000]">Welcome back select method to login</p>
      </div>

      {/* Social signups */}
      <SocialAuthButtons verb="Sign up" />

      {/* OR divider */}
      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-white px-3 text-xs font-medium text-slate-400">OR</span>
        </div>
      </div>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-red-100 text-xs font-bold text-red-500">
            !
          </span>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Name + Email */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="full_name" className="block text-base font-semibold text-slate-800">
              Your Name
            </label>
            <div className="relative">
              <User className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="full_name"
                name="full_name"
                type="text"
                value={formData.full_name}
                onChange={handleChange}
                placeholder="John Doe"
                disabled={isRegistering}
                className={`${inputClass} pl-10`}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="email" className="block text-base font-semibold text-slate-800">
              Email Id :
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="info@voicecon.com"
                  required
                  disabled={isRegistering || emailIsVerified}
                  className={`${inputClass} pr-10`}
                />
                {emailIsVerified ? (
                  <BadgeCheck className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-emerald-600" />
                ) : (
                  <Mail className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                )}
              </div>
              {emailIsVerified ? (
                <button
                  type="button"
                  onClick={clearVerification}
                  title="Verified — click to use a different email"
                  className="flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 text-sm font-semibold text-emerald-700 transition-colors hover:bg-emerald-100"
                >
                  <BadgeCheck className="h-4 w-4" />
                  Verified
                </button>
              ) : (
                <button
                  type="button"
                  onClick={sendCode}
                  disabled={isSendingCode || isRegistering || !formData.email.trim()}
                  className="flex items-center gap-1.5 whitespace-nowrap rounded-lg border border-[#243275] px-4 text-sm font-semibold text-[#243275] transition-all hover:bg-[#243275] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSendingCode && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  {codeSent ? 'Resend' : 'Verify'}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Code entry — only while a code is outstanding */}
        {codeSent && !emailIsVerified && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-800">
              Enter the 6-digit code we emailed to {formData.email.trim()}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              It expires in 10 minutes. Check your spam folder if it hasn&apos;t arrived.
            </p>
            <div className="mt-3 max-w-xs">
              <OtpInput
                value={code}
                onChange={setCode}
                onComplete={submitCode}
                disabled={isVerifying}
                autoFocus
              />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => submitCode(code)}
                disabled={code.length < 6 || isVerifying}
                className="flex items-center gap-1.5 rounded-lg bg-[#243275] px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-[#1c2960] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isVerifying && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Verify email
              </button>
              <button
                type="button"
                onClick={sendCode}
                disabled={resendIn > 0 || isSendingCode}
                className="text-sm font-medium text-slate-500 transition-colors hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {resendIn > 0 ? `Resend in ${resendIn}s` : 'Send a new code'}
              </button>
            </div>
          </div>
        )}

        {/* Phone number */}
        <div className="space-y-1.5">
          <label htmlFor="phone" className="block text-base font-semibold text-slate-800">
            Phone Number
          </label>
          <div className="flex gap-2">
            <div className="relative">
              <select
                value={dialCode}
                onChange={(e) => setDialCode(e.target.value)}
                disabled={isRegistering}
                aria-label="Country code"
                className="h-full appearance-none rounded-lg border border-slate-300 bg-white py-2.5 pl-3 pr-7 text-base text-slate-900 outline-none transition-all focus:border-[#243275] focus:ring-3 focus:ring-[#243275]/15"
              >
                {COUNTRY_CODES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.flag} {c.code}
                  </option>
                ))}
              </select>
            </div>
            <div className="relative flex-1">
              <Phone className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="phone"
                name="phone"
                type="tel"
                value={formData.phone}
                onChange={handleChange}
                placeholder="(301) 798 1897"
                disabled={isRegistering}
                className={`${inputClass} pl-10`}
              />
            </div>
          </div>
        </div>

        {/* Password + Confirm */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="password" className="block text-base font-semibold text-slate-800">
              Password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••"
                required
                disabled={isRegistering}
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
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor="confirmPassword"
              className="block text-base font-semibold text-slate-800"
            >
              Confirm Password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="••••••••"
                required
                disabled={isRegistering}
                className={`${inputClass} pl-10`}
              />
            </div>
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={isRegistering || !emailIsVerified}
          title={emailIsVerified ? undefined : 'Verify your email address first'}
          className="shadow-base w-full rounded-lg bg-[#243275] px-4 py-3 text-base font-semibold text-white transition-all hover:bg-[#1c2960] focus:outline-none focus:ring-3 focus:ring-[#243275]/30 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isRegistering ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Creating account…
            </span>
          ) : (
            'Sign up Now'
          )}
        </button>
      </form>

      <p className="mt-5 text-sm text-[#000000]">
        already have an account?{' '}
        <Link href="/login" className="font-semibold text-brand-600 hover:text-brand-700">
          Sign in here.
        </Link>
      </p>
    </div>
  )
}
