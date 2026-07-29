'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import Link from 'next/link'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import {
  Bot, Phone, Plug, GitBranch, BarChart3, ArrowRight,
  TrendingUp, Zap, Clock, CheckCircle2, Plus, Store,
} from 'lucide-react'

interface DashboardStats {
  activeAgents: number
  callsToday: number
  integrations: number
  workflows: number
}

interface ChecklistStatus {
  hasAgents: boolean
  hasPhoneNumbers: boolean
  hasIntegrations: boolean
  hasWorkflows: boolean
}

function StatSkeleton() {
  return (
    <div className="animate-pulse rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="h-10 w-10 rounded-lg bg-slate-100" />
        <div className="h-4 w-4 rounded bg-slate-100" />
      </div>
      <div className="h-7 w-16 bg-slate-100 rounded mb-1" />
      <div className="h-4 w-24 bg-slate-100 rounded" />
    </div>
  )
}

/**
 * Accent ramp — brand green through teal to cyan, with a single warm tone so
 * the four tiles stay distinguishable without leaving the palette.
 */
const ACCENTS = {
  green: { solid: '#0F6A59', tint: 'rgba(15,106,89,0.13)',  grad: 'linear-gradient(135deg, #0F6A59 0%, #17836b 100%)' },
  teal:  { solid: '#0d8a7a', tint: 'rgba(13,138,122,0.13)', grad: 'linear-gradient(135deg, #0d8a7a 0%, #14a894 100%)' },
  cyan:  { solid: '#0e7490', tint: 'rgba(14,116,144,0.13)', grad: 'linear-gradient(135deg, #0e7490 0%, #1595b5 100%)' },
  amber: { solid: '#b45309', tint: 'rgba(180,83,9,0.13)',   grad: 'linear-gradient(135deg, #b45309 0%, #d97a20 100%)' },
} as const

const quickActions = [
  {
    title: 'Create an Agent',
    description: 'Deploy a new AI voice agent in minutes',
    icon: Bot,
    href: '/dashboard/agents/new',
    accent: ACCENTS.green,
    badge: 'Most popular',
  },
  {
    title: 'Connect an App',
    description: 'Sync with CRM, calendar, and 50+ tools',
    icon: Plug,
    href: '/dashboard/integrations',
    accent: ACCENTS.teal,
    badge: null,
  },
  {
    title: 'Build a Workflow',
    description: 'Automate complex tasks visually',
    icon: GitBranch,
    href: '/dashboard/workflows/new',
    accent: ACCENTS.cyan,
    badge: null,
  },
  {
    title: 'Browse Marketplace',
    description: 'Pre-built templates to get started fast',
    icon: Store,
    href: '/dashboard/marketplace',
    accent: ACCENTS.amber,
    badge: 'New',
  },
]

const features = [
  { icon: Zap,          title: 'Real-time AI',        desc: 'Sub-500ms voice response with GPT-4 & Claude' },
  { icon: TrendingUp,   title: 'Smart Analytics',     desc: 'Track call quality, sentiment, and performance' },
  { icon: Clock,        title: '24/7 Available',      desc: 'Agents that never sleep, never miss a call' },
  { icon: CheckCircle2, title: 'Compliant & Secure',  desc: 'SOC 2 Type II, GDPR, HIPAA ready' },
]

export default function DashboardPage() {
  const { user } = useAuth()
  const firstName = user?.full_name?.split(' ')[0] || 'there'

  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [checklist, setChecklist] = useState<ChecklistStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    setIsLoading(true)
    try {
      const [agentsRes, callsRes, intRes, wfRes, phoneRes] = await Promise.allSettled([
        apiClient.get<{ agents: any[]; total: number }>(API_ENDPOINTS.AGENTS + '?limit=500'),
        apiClient.get<any>(API_ENDPOINTS.CALL_STATS),
        apiClient.get<{ connections: any[]; total: number }>(API_ENDPOINTS.INTEGRATION_CONNECTIONS + '?limit=500'),
        apiClient.get<{ workflows: any[]; total: number }>(API_ENDPOINTS.WORKFLOWS + '?limit=500'),
        apiClient.get<any[]>(API_ENDPOINTS.PHONE_NUMBERS),
      ])

      const agentData   = agentsRes.status  === 'fulfilled' ? agentsRes.value.data  : null
      const callData    = callsRes.status   === 'fulfilled' ? callsRes.value.data   : null
      const intData     = intRes.status     === 'fulfilled' ? intRes.value.data     : null
      const wfData      = wfRes.status      === 'fulfilled' ? wfRes.value.data      : null
      const phoneData   = phoneRes.status   === 'fulfilled' ? phoneRes.value.data   : null

      const agentList = agentData?.agents || []
      const intList   = intData?.connections || []
      const wfList    = wfData?.workflows || []
      const phoneList = Array.isArray(phoneData) ? phoneData : []

      setStats({
        activeAgents: agentList.filter((a: any) => a.is_active).length,
        callsToday:   callData?.total_calls ?? 0,
        integrations: intList.filter((i: any) => i.status === 'active' || i.status === 'connected').length,
        workflows:    wfList.length,
      })

      setChecklist({
        hasAgents:       agentList.length > 0,
        hasPhoneNumbers: phoneList.length > 0,
        hasIntegrations: intList.filter((i: any) => i.status === 'active' || i.status === 'connected').length > 0,
        hasWorkflows:    wfList.length > 0,
      })
    } catch (e) {
      setStats({ activeAgents: 0, callsToday: 0, integrations: 0, workflows: 0 })
      setChecklist({ hasAgents: false, hasPhoneNumbers: false, hasIntegrations: false, hasWorkflows: false })
    } finally {
      setIsLoading(false)
    }
  }

  const statCards = [
    { name: 'Active Agents', value: stats?.activeAgents ?? 0, icon: Bot,       accent: ACCENTS.green, href: '/dashboard/agents' },
    { name: 'Total Calls',   value: stats?.callsToday   ?? 0, icon: Phone,     accent: ACCENTS.teal,  href: '/dashboard/calls' },
    { name: 'Integrations',  value: stats?.integrations ?? 0, icon: Plug,      accent: ACCENTS.cyan,  href: '/dashboard/integrations' },
    { name: 'Workflows',     value: stats?.workflows    ?? 0, icon: GitBranch, accent: ACCENTS.amber, href: '/dashboard/workflows' },
  ]

  const checklistSteps = [
    { title: 'Create your first AI agent',   href: '/dashboard/agents/new',     done: checklist?.hasAgents ?? false },
    { title: 'Connect a phone number',        href: '/dashboard/phone-numbers',  done: checklist?.hasPhoneNumbers ?? false },
    { title: 'Set up an integration',         href: '/dashboard/integrations',   done: checklist?.hasIntegrations ?? false },
    { title: 'Build your first workflow',     href: '/dashboard/workflows/new',  done: checklist?.hasWorkflows ?? false },
  ]
  const completedCount = checklistSteps.filter(s => s.done).length

  return (
    <div className="space-y-6">

      {/* ── Welcome banner ── */}
      <section className="gradient-brand relative overflow-hidden rounded-3xl p-6 text-white shadow-[0_18px_40px_-18px_rgba(15,106,89,0.55)] md:p-9">
        {/* Depth: soft light pools + a dotted texture + concentric rings */}
        <div className="pointer-events-none absolute -right-28 -top-32 h-96 w-96 rounded-full bg-white/12 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-28 left-1/4 h-72 w-72 rounded-full bg-emerald-200/10 blur-3xl" />
        <div className="brand-dots pointer-events-none absolute inset-0 opacity-[0.12]" />
        <div className="pointer-events-none absolute -right-16 top-1/2 hidden h-[420px] w-[420px] -translate-y-1/2 rounded-full border border-white/10 lg:block">
          <div className="absolute inset-12 rounded-full border border-white/10" />
          <div className="absolute inset-24 rounded-full border border-white/[0.07]" />
        </div>

        <div className="relative">
          {/* Status badge */}
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium backdrop-blur-sm">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-300" />
            </span>
            All systems operational
          </div>

          <h1 className="text-2xl font-bold tracking-tight md:text-4xl">
            Good day, {firstName}
          </h1>
          <p className="mt-2.5 max-w-lg text-sm leading-relaxed text-emerald-50/80 md:text-base">
            Your voice AI platform is ready. Create your first agent or explore integrations to get started.
          </p>

          <div className="mt-7 flex flex-wrap gap-3">
            <Link
              href="/dashboard/agents/new"
              className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-[#0F6A59] shadow-lg shadow-black/10 transition-all hover:-translate-y-0.5 hover:shadow-xl"
            >
              <Plus className="h-4 w-4" />
              Create Agent
            </Link>
            <Link
              href="/dashboard/analytics"
              className="inline-flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-5 py-2.5 text-sm font-semibold text-white backdrop-blur-sm transition-colors hover:bg-white/20"
            >
              <BarChart3 className="h-4 w-4" />
              View Analytics
            </Link>
          </div>
        </div>

        {/* Live stats strip on banner */}
        {!isLoading && stats && (
          <div className="relative mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: 'Active Agents', value: stats.activeAgents, icon: Bot },
              { label: 'Total Calls',   value: stats.callsToday,   icon: Phone },
              { label: 'Integrations',  value: stats.integrations, icon: Plug },
              { label: 'Workflows',     value: stats.workflows,    icon: GitBranch },
            ].map(item => {
              const Icon = item.icon
              return (
                <div
                  key={item.label}
                  className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 backdrop-blur-sm transition-colors hover:bg-white/[0.16]"
                >
                  <div className="text-2xl font-bold tabular-nums text-white">{item.value}</div>
                  <div className="mt-1 flex items-center gap-1.5 text-xs text-emerald-50/75">
                    <Icon className="h-3.5 w-3.5" />
                    {item.label}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading
          ? [1,2,3,4].map(i => <StatSkeleton key={i} />)
          : statCards.map((stat) => {
              const Icon = stat.icon
              return (
                <Link key={stat.name} href={stat.href} className="group block">
                  <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 transition-all duration-200 hover:-translate-y-1 hover:border-slate-300 hover:shadow-[0_16px_32px_-18px_rgba(15,23,42,0.35)]">
                    {/* Accent bar wipes in on hover */}
                    <span
                      className="absolute inset-x-0 top-0 h-1 origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100"
                      style={{ background: stat.accent.grad }}
                    />
                    {/* Corner wash */}
                    <span
                      className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
                      style={{ background: stat.accent.tint }}
                    />

                    <div className="relative flex items-start justify-between">
                      <div
                        className="flex h-12 w-12 items-center justify-center rounded-2xl transition-transform duration-200 group-hover:scale-105"
                        style={{ background: stat.accent.tint }}
                      >
                        <Icon className="h-5 w-5" style={{ color: stat.accent.solid }} />
                      </div>
                      <ArrowRight className="h-4 w-4 text-slate-300 transition-all group-hover:translate-x-0.5 group-hover:text-slate-400" />
                    </div>
                    <div className="relative mt-5 text-3xl font-bold tabular-nums text-slate-900">{stat.value}</div>
                    <div className="relative mt-0.5 text-sm text-slate-500">{stat.name}</div>
                  </div>
                </Link>
              )
            })
        }
      </div>

      {/* ── Quick actions + Platform features ── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Quick actions */}
        <div className="xl:col-span-2">
          <h2 className="text-sm font-semibold text-slate-900 mb-4">Quick actions</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {quickActions.map((action) => {
              const Icon = action.icon
              return (
                <Link key={action.title} href={action.href} className="group block">
                  <div className="relative h-full cursor-pointer overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 transition-all duration-200 hover:-translate-y-1 hover:border-slate-300 hover:shadow-[0_16px_32px_-18px_rgba(15,23,42,0.35)]">
                    {/* Colour wash that blooms from the icon on hover */}
                    <span
                      className="pointer-events-none absolute -left-8 -top-8 h-32 w-32 rounded-full opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
                      style={{ background: action.accent.tint }}
                    />

                    {action.badge && (
                      <span
                        className="absolute right-3 top-3 rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{ background: action.accent.tint, color: action.accent.solid }}
                      >
                        {action.badge}
                      </span>
                    )}

                    <div
                      className="relative mb-4 flex h-12 w-12 items-center justify-center rounded-2xl shadow-sm transition-transform duration-200 group-hover:scale-105"
                      style={{ background: action.accent.grad }}
                    >
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <h3 className="relative text-sm font-semibold text-slate-900">{action.title}</h3>
                    <p className="relative mt-1 text-xs leading-relaxed text-slate-500">{action.description}</p>
                    <div
                      className="relative mt-3 flex items-center gap-1 text-xs font-semibold opacity-0 transition-all duration-200 group-hover:opacity-100"
                      style={{ color: action.accent.solid }}
                    >
                      Get started <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>

        {/* Platform features */}
        <div>
          <h2 className="text-sm font-semibold text-slate-900 mb-4">Platform features</h2>
          <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            {features.map((f) => {
              const Icon = f.icon
              return (
                <div key={f.title} className="flex items-start gap-3 p-4 transition-colors hover:bg-slate-50/70">
                  <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-[#0F6A59]/10">
                    <Icon className="h-4 w-4 text-[#0F6A59]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-800">{f.title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{f.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Getting started checklist ── */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Getting started</h2>
            <p className="text-sm text-slate-500 mt-0.5">Complete these steps to set up your workspace</p>
          </div>
          <div className="flex items-center gap-2">
            {isLoading ? (
              <div className="h-4 w-12 bg-slate-100 rounded animate-pulse" />
            ) : (
              <>
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#0F6A59]/10 text-xs font-bold text-[#0F6A59]">
                  {completedCount}/{checklistSteps.length}
                </div>
                {completedCount === checklistSteps.length && (
                  <span className="rounded-full border border-[#0F6A59]/20 bg-[#0F6A59]/10 px-2 py-0.5 text-xs font-medium text-[#0F6A59]">
                    Complete!
                  </span>
                )}
              </>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {!isLoading && (
          <div className="mb-5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${(completedCount / checklistSteps.length) * 100}%`,
                background: 'linear-gradient(90deg, #0F6A59, #1fa183)',
              }}
            />
          </div>
        )}

        <div className="space-y-2.5">
          {isLoading
            ? [1,2,3,4].map(i => (
                <div key={i} className="h-13 rounded-lg bg-slate-100 animate-pulse" style={{ height: '52px' }} />
              ))
            : checklistSteps.map((step, i) => (
                <Link key={step.title} href={step.href}>
                  <div className={`flex items-center gap-4 rounded-lg border px-4 py-3 transition-all group ${
                    step.done
                      ? 'border-[#0F6A59]/20 bg-[#0F6A59]/[0.06]'
                      : 'border-slate-200 bg-slate-50 hover:border-[#0F6A59]/30 hover:bg-[#0F6A59]/[0.04]'
                  }`}>
                    <div className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold transition-colors ${
                      step.done
                        ? 'border-[#0F6A59] bg-[#0F6A59] text-white'
                        : 'border-slate-300 text-slate-400 group-hover:border-[#0F6A59] group-hover:text-[#0F6A59]'
                    }`}>
                      {step.done ? <CheckCircle2 className="h-3.5 w-3.5" /> : i + 1}
                    </div>
                    <span className={`text-sm font-medium flex-1 transition-colors ${
                      step.done
                        ? 'text-[#0F6A59] line-through decoration-[#0F6A59]/40'
                        : 'text-slate-700 group-hover:text-[#0F6A59]'
                    }`}>
                      {step.title}
                    </span>
                    {!step.done && (
                      <ArrowRight className="h-4 w-4 text-slate-300 transition-colors group-hover:text-[#0F6A59]" />
                    )}
                    {step.done && (
                      <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-[#0F6A59]" />
                    )}
                  </div>
                </Link>
              ))
          }
        </div>
      </div>

    </div>
  )
}
