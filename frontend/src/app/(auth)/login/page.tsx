'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { SocialAuthButtons } from '@/components/auth/SocialAuthButtons'
import { Mail } from 'lucide-react'
import { FieldError, errorInputClass, fieldErrorProps } from '@/components/ui/field-error'
import { PasswordInput } from '@/components/ui/password-input'

export default function LoginPage() {
  const { login, isLoggingIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})

  /**
   * Check both fields and report everything that is wrong at once.
   *
   * The browser's built-in validation stops at the first invalid field, so a
   * form with two empty inputs takes two attempts to find that out. Returning
   * a map lets every message appear together, under the field it belongs to.
   */
  const validate = () => {
    const next: { email?: string; password?: string } = {}
    const trimmed = email.trim()

    if (!trimmed) {
      next.email = 'Enter your email address'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      next.email = 'Enter a valid email address, like you@example.com'
    }

    if (!password) {
      next.password = 'Enter your password'
    }

    setErrors(next)
    return next
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const found = validate()
    if (Object.keys(found).length > 0) {
      // Focus the first field that failed, so keyboard and screen-reader users
      // are taken to the problem instead of having to hunt for it.
      document.getElementById(found.email ? 'email' : 'password')?.focus()
      return
    }
    login({ email: email.trim(), password })
  }

  return (
    <div className="w-full max-w-md px-1">
      <div className="mb-7">
        <h1 className="text-[28px] md:text-3xl font-medium md:font-bold text-slate-900">Log in to your account</h1>
        <p className="mt-2 text-base text-[#000000]">Welcome back! Select a method to sign in.</p>
      </div>

      {/* Social logins */}
      <SocialAuthButtons verb="Login" />

      {/* OR divider */}
      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-white px-3 text-xs font-medium text-slate-400">OR</span>
        </div>
      </div>

      {/* noValidate: this form reports its own errors below each field —
          see components/ui/field-error.tsx for why the native bubble is not
          good enough. The `required` attributes stay for semantics and for
          assistive technology. */}
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        {/* Email */}
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-base font-semibold text-slate-800">
            Email address
          </label>
          <div className="relative">
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
              }}
              placeholder="you@example.com"
              required
              disabled={isLoggingIn}
              {...fieldErrorProps('email', errors.email)}
              className={`w-full rounded-lg border bg-white px-4 py-2.5 pr-11 text-base text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:ring-3 disabled:cursor-not-allowed disabled:opacity-50 ${
                errors.email
                  ? errorInputClass
                  : 'border-slate-300 focus:border-brand-500 focus:ring-brand-500/15'
              }`}
            />
            <Mail className="pointer-events-none absolute right-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          </div>
          <FieldError id="email-error" message={errors.email} />
        </div>

        {/* Password */}
        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-base font-semibold text-slate-800">
            Password:
          </label>
          <PasswordInput
            id="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }))
            }}
            // Not a row of dots. A dotted placeholder renders an *empty*
            // password box as though it already contains a password, so
            // "Please fill out this field" pointed at a field that looked
            // full — which is exactly how this was reported.
            placeholder="Enter your password"
            required
            disabled={isLoggingIn}
            {...fieldErrorProps('password', errors.password)}
            className={`w-full rounded-lg border bg-white px-4 py-2.5 pr-11 text-base text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:ring-3 disabled:cursor-not-allowed disabled:opacity-50 ${
              errors.password
                ? errorInputClass
                : 'border-slate-300 focus:border-brand-500 focus:ring-brand-500/15'
            }`}
          />
          <FieldError id="password-error" message={errors.password} />
          <div className="flex justify-end pt-1">
            <Link
              href="/forgot-password"
              className="text-base font-medium text-[#202020] underline hover:text-slate-800"
            >
              Forgot password?
            </Link>
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={isLoggingIn}
          className="shadow-base w-full rounded-lg bg-[#243275] px-4 py-3 text-base font-semibold text-white transition-all hover:bg-[#1c2960] focus:outline-none focus:ring-3 focus:ring-[#243275]/30 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoggingIn ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Logging in…
            </span>
          ) : (
            'Login Now'
          )}
        </button>
      </form>

      <p className="mt-6 text-base text-[#000000]">
        Don&apos;t have an account?{' '}
        <Link href="/register" className="font-semibold text-brand-600 hover:text-brand-700">
          Sign up here.
        </Link>
      </p>
    </div>
  )
}
