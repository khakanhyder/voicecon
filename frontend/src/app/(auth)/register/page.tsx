'use client'

import { useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { Eye, EyeOff, Mail, Lock, Phone, User } from 'lucide-react'
import { GoogleIcon, AppleIcon } from '@/lib/icons'

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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
    if (error) setError('')
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    register({
      email: formData.email,
      password: formData.password,
      full_name: formData.full_name || undefined,
      phone_number: formData.phone ? `${dialCode} ${formData.phone}`.trim() : undefined,
    })
  }

  const handleSocial = (provider: string) => {
    toast.info(`${provider} sign-up is coming soon.`)
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
            <div className="relative">
              <input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="info@voicecon.com"
                required
                disabled={isRegistering}
                className={`${inputClass} pr-10`}
              />
              <Mail className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            </div>
          </div>
        </div>

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
          disabled={isRegistering}
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
