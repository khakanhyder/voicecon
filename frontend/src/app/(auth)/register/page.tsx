'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { Eye, EyeOff, Mail, Lock, User, Building2, ArrowRight, Check } from 'lucide-react'

export default function RegisterPage() {
  const { register, isRegistering } = useAuth()
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    company_name: '',
  })
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
      company_name: formData.company_name || undefined,
    })
  }

  const passwordStrength = formData.password.length === 0 ? null
    : formData.password.length < 6 ? 'weak'
    : formData.password.length < 10 ? 'medium'
    : 'strong'

  return (
    <div className="w-full max-w-md">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Create your account</h1>
        <p className="mt-2 text-slate-500">Start your free trial, no credit card required</p>
      </div>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <div className="h-5 w-5 flex-shrink-0 rounded-full bg-red-100 flex items-center justify-center mt-0.5">
            <span className="text-red-500 font-bold text-xs">!</span>
          </div>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label htmlFor="full_name" className="block text-sm font-medium text-slate-700">Full name</label>
            <div className="relative">
              <User className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
              <input
                id="full_name"
                name="full_name"
                type="text"
                value={formData.full_name}
                onChange={handleChange}
                placeholder="John Doe"
                disabled={isRegistering}
                className="w-full rounded-lg border border-slate-300 bg-white pl-10 pr-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 disabled:opacity-50"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="company_name" className="block text-sm font-medium text-slate-700">Company <span className="text-slate-400 font-normal">(optional)</span></label>
            <div className="relative">
              <Building2 className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
              <input
                id="company_name"
                name="company_name"
                type="text"
                value={formData.company_name}
                onChange={handleChange}
                placeholder="Acme Inc"
                disabled={isRegistering}
                className="w-full rounded-lg border border-slate-300 bg-white pl-10 pr-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 disabled:opacity-50"
              />
            </div>
          </div>
        </div>

        {/* Email */}
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-sm font-medium text-slate-700">Email address</label>
          <div className="relative">
            <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            <input
              id="email"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="you@company.com"
              required
              disabled={isRegistering}
              className="w-full rounded-lg border border-slate-300 bg-white pl-10 pr-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 disabled:opacity-50"
            />
          </div>
        </div>

        {/* Password */}
        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-sm font-medium text-slate-700">Password</label>
          <div className="relative">
            <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            <input
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={handleChange}
              placeholder="Min. 8 characters"
              required
              disabled={isRegistering}
              className="w-full rounded-lg border border-slate-300 bg-white pl-10 pr-11 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {passwordStrength && (
            <div className="flex items-center gap-2 mt-1.5">
              <div className="flex gap-1 flex-1">
                {['weak', 'medium', 'strong'].map((level, i) => (
                  <div
                    key={level}
                    className={`h-1 flex-1 rounded-full transition-colors ${
                      passwordStrength === 'weak' && i === 0 ? 'bg-red-400' :
                      passwordStrength === 'medium' && i <= 1 ? 'bg-amber-400' :
                      passwordStrength === 'strong' ? 'bg-emerald-400' : 'bg-slate-200'
                    }`}
                  />
                ))}
              </div>
              <span className={`text-xs font-medium ${
                passwordStrength === 'weak' ? 'text-red-500' :
                passwordStrength === 'medium' ? 'text-amber-500' : 'text-emerald-500'
              }`}>
                {passwordStrength.charAt(0).toUpperCase() + passwordStrength.slice(1)}
              </span>
            </div>
          )}
        </div>

        {/* Confirm Password */}
        <div className="space-y-1.5">
          <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700">Confirm password</label>
          <div className="relative">
            <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            <input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="Re-enter password"
              required
              disabled={isRegistering}
              className="w-full rounded-lg border border-slate-300 bg-white pl-10 pr-10 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 disabled:opacity-50"
            />
            {formData.confirmPassword && formData.password === formData.confirmPassword && (
              <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
                <Check className="h-4 w-4 text-emerald-500" />
              </div>
            )}
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={isRegistering}
          className="w-full flex items-center justify-center gap-2 rounded-lg gradient-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:opacity-90 focus:outline-none focus:ring-3 focus:ring-blue-500/30 transition-all disabled:opacity-60 disabled:cursor-not-allowed mt-2"
        >
          {isRegistering ? (
            <>
              <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              Creating account…
            </>
          ) : (
            <>
              Create account
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </form>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-slate-50 px-3 text-slate-400">Already have an account?</span>
        </div>
      </div>

      <Link
        href="/login"
        className="flex items-center justify-center gap-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-all"
      >
        Sign in instead
        <ArrowRight className="h-4 w-4 text-slate-400" />
      </Link>

      <p className="mt-6 text-center text-xs text-slate-400">
        By creating an account, you agree to our{' '}
        <a href="#" className="underline hover:text-slate-600">Terms of Service</a>
        {' '}and{' '}
        <a href="#" className="underline hover:text-slate-600">Privacy Policy</a>.
      </p>
    </div>
  )
}
