'use client'

import { useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { Eye, EyeOff, Mail } from 'lucide-react'
import { GoogleIcon, AppleIcon } from '@/lib/icons'

export default function LoginPage() {
  const { login, isLoggingIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    login({ email, password })
  }

  const handleSocial = (provider: string) => {
    toast.info(`${provider} sign-in is coming soon.`)
  }

  return (
    <div className="w-full max-w-md px-1">
      <div className="mb-7">
        <h1 className="text-[28px] md:text-3xl font-medium md:font-bold text-slate-900">Login into your account</h1>
        <p className="mt-2 text-base text-[#000000]">Welcome back select method to login</p>
      </div>

      {/* Social logins */}
      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => handleSocial('Google')}
          className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-2 md:px-4 py-2.5 text-sm md:text-base font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <GoogleIcon className="h-5 w-5" />
          Login With Google
        </button>
        <button
          type="button"
          onClick={() => handleSocial('Apple')}
          className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-2 md:px-4 py-2.5 text-sm md:text-base font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <AppleIcon className="h-5 w-5 text-slate-900" />
          Login With Apple
        </button>
      </div>

      {/* OR divider */}
      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-white px-3 text-xs font-medium text-slate-400">OR</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Email */}
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-base font-semibold text-slate-800">
            Email Id :
          </label>
          <div className="relative">
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              disabled={isLoggingIn}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 pr-11 text-base text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-brand-500 focus:ring-3 focus:ring-brand-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <Mail className="pointer-events-none absolute right-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          </div>
        </div>

        {/* Password */}
        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-base font-semibold text-slate-800">
            Password:
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••"
              required
              disabled={isLoggingIn}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 pr-11 text-base text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-brand-500 focus:ring-3 focus:ring-brand-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-600"
            >
              {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>
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
