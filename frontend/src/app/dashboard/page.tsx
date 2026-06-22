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
    <div className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-10 w-10 rounded-lg bg-slate-100" />
        <div className="h-4 w-4 rounded bg-slate-100" />
      </div>
      <div className="h-7 w-16 bg-slate-100 rounded mb-1" />
      <div className="h-4 w-24 bg-slate-100 rounded" />
    </div>
  )
}

const quickActions = [
  {
    title: 'Create an Agent',
    description: 'Deploy a new AI voice agent in minutes',
    icon: Bot,
    href: '/dashboard/agents/new',
    color: 'from-blue-600 to-blue-700',
    badge: 'Most popular',
  },
  {
    title: 'Connect an App',
    description: 'Sync with CRM, calendar, and 50+ tools',
    icon: Plug,
    href: '/dashboard/integrations',
    color: 'from-teal-500 to-cyan-600',
    badge: null,
  },
  {
    title: 'Build a Workflow',
    description: 'Automate complex tasks visually',
    icon: GitBranch,
    href: '/dashboard/workflows/new',
    color: 'from-violet-600 to-purple-700',
    badge: null,
  },
  {
    title: 'Browse Marketplace',
    description: 'Pre-built templates to get started fast',
    icon: Store,
    href: '/dashboard/marketplace',
    color: 'from-rose-500 to-pink-600',
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
        apiClient.get<{ integrations: any[]; total: number }>(API_ENDPOINTS.INTEGRATIONS + '?limit=500'),
        apiClient.get<{ workflows: any[]; total: number }>(API_ENDPOINTS.WORKFLOWS + '?limit=500'),
        apiClient.get<any[]>(API_ENDPOINTS.PHONE_NUMBERS),
      ])

      const agentData   = agentsRes.status  === 'fulfilled' ? agentsRes.value.data  : null
      const callData    = callsRes.status   === 'fulfilled' ? callsRes.value.data   : null
      const intData     = intRes.status     === 'fulfilled' ? intRes.value.data     : null
      const wfData      = wfRes.status      === 'fulfilled' ? wfRes.value.data      : null
      const phoneData   = phoneRes.status   === 'fulfilled' ? phoneRes.value.data   : null

      const agentList = agentData?.agents || []
      const intList   = intData?.integrations || []
      const wfList    = wfData?.workflows || []
      const phoneList = Array.isArray(phoneData) ? phoneData : []

      setStats({
        activeAgents: agentList.filter((a: any) => a.is_active).length,
        callsToday:   callData?.total_calls ?? 0,
        integrations: intList.filter((i: any) => i.status === 'connected').length,
        workflows:    wfList.length,
      })

      setChecklist({
        hasAgents:       agentList.length > 0,
        hasPhoneNumbers: phoneList.length > 0,
        hasIntegrations: intList.filter((i: any) => i.status === 'connected').length > 0,
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
    {
      name: 'Active Agents',
      value: stats?.activeAgents ?? 0,
      icon: Bot,
      lightColor: 'bg-blue-50',
      textColor: 'text-blue-600',
      href: '/dashboard/agents',
    },
    {
      name: 'Total Calls',
      value: stats?.callsToday ?? 0,
      icon: Phone,
      lightColor: 'bg-emerald-50',
      textColor: 'text-emerald-600',
      href: '/dashboard/calls',
    },
    {
      name: 'Integrations',
      value: stats?.integrations ?? 0,
      icon: Plug,
      lightColor: 'bg-violet-50',
      textColor: 'text-violet-600',
      href: '/dashboard/integrations',
    },
    {
      name: 'Workflows',
      value: stats?.workflows ?? 0,
      icon: GitBranch,
      lightColor: 'bg-amber-50',
      textColor: 'text-amber-600',
      href: '/dashboard/workflows',
    },
  ]

  const checklistSteps = [
    { title: 'Create your first AI agent',   href: '/dashboard/agents/new',     done: checklist?.hasAgents ?? false },
    { title: 'Connect a phone number',        href: '/dashboard/phone-numbers',  done: checklist?.hasPhoneNumbers ?? false },
    { title: 'Set up an integration',         href: '/dashboard/integrations',   done: checklist?.hasIntegrations ?? false },
    { title: 'Build your first workflow',     href: '/dashboard/workflows/new',  done: checklist?.hasWorkflows ?? false },
  ]
  const completedCount = checklistSteps.filter(s => s.done).length

  return (
    <div className="space-y-7">

      {/* ── Welcome banner ── */}
      <div className="relative overflow-hidden rounded-2xl gradient-primary p-6 md:p-8 text-white shadow-xl neon-glow">
        {/* Decorative orbs */}
        <div className="absolute -right-12 -top-12 h-56 w-56 rounded-full bg-white/5 blur-3xl pointer-events-none" />
        <div className="absolute right-24 bottom-0 h-36 w-36 rounded-full bg-white/5 blur-2xl pointer-events-none" />
        <div className="absolute left-1/2 top-0 h-px w-1/2 bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />

        <div className="relative">
          {/* Status badge */}
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 border border-white/15 backdrop-blur-sm px-3 py-1 text-xs font-medium mb-5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            All systems operational
          </div>

          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            Good day, {firstName}
          </h1>
          <p className="mt-2 text-blue-200 text-sm md:text-base max-w-lg leading-relaxed">
            Your voice AI platform is ready. Create your first agent or explore integrations to get started.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/dashboard/agents/new"
              className="inline-flex items-center gap-2 rounded-lg bg-white text-blue-800 px-4 py-2 text-sm font-semibold hover:bg-blue-50 transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" />
              Create Agent
            </Link>
            <Link
              href="/dashboard/analytics"
              className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm text-white px-4 py-2 text-sm font-semibold hover:bg-white/20 transition-colors"
            >
              <BarChart3 className="h-4 w-4" />
              View Analytics
            </Link>
          </div>
        </div>

        {/* Live stats strip on banner */}
        {!isLoading && stats && (
          <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3 pt-5 border-t border-white/10">
            {[
              { label: 'Active Agents', value: stats.activeAgents, icon: Bot },
              { label: 'Total Calls',   value: stats.callsToday,   icon: Phone },
              { label: 'Integrations',  value: stats.integrations, icon: Plug },
              { label: 'Workflows',     value: stats.workflows,    icon: GitBranch },
            ].map(item => {
              const Icon = item.icon
              return (
                <div key={item.label} className="text-center">
                  <div className="text-2xl font-bold text-white">{item.value}</div>
                  <div className="flex items-center justify-center gap-1 mt-0.5 text-xs text-blue-200">
                    <Icon className="h-3 w-3" />
                    {item.label}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading
          ? [1,2,3,4].map(i => <StatSkeleton key={i} />)
          : statCards.map((stat) => {
              const Icon = stat.icon
              return (
                <Link key={stat.name} href={stat.href} className="group">
                  <div className="bg-white rounded-xl border border-slate-200 p-5 card-shadow hover:shadow-md hover:border-slate-300 hover:-translate-y-0.5 transition-all duration-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${stat.lightColor}`}>
                        <Icon className={`h-5 w-5 ${stat.textColor}`} />
                      </div>
                      <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all" />
                    </div>
                    <div className="text-2xl font-bold text-slate-900 tabular-nums">{stat.value}</div>
                    <div className="text-sm text-slate-500 mt-0.5">{stat.name}</div>
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
                <Link key={action.title} href={action.href}>
                  <div className="group relative bg-white rounded-xl border border-slate-200 p-5 card-shadow hover:shadow-md hover:border-slate-300 hover:-translate-y-0.5 transition-all cursor-pointer overflow-hidden">
                    {action.badge && (
                      <span className="absolute top-3 right-3 rounded-full bg-blue-50 text-blue-700 border border-blue-100 text-xs font-medium px-2 py-0.5">
                        {action.badge}
                      </span>
                    )}
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${action.color} shadow-sm mb-3`}>
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <h3 className="font-semibold text-slate-900 text-sm group-hover:text-blue-700 transition-colors">
                      {action.title}
                    </h3>
                    <p className="text-slate-500 text-xs mt-1 leading-relaxed">{action.description}</p>
                    <div className="flex items-center gap-1 mt-3 text-xs font-medium text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity">
                      Get started <ArrowRight className="h-3 w-3" />
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
          <div className="bg-white rounded-xl border border-slate-200 card-shadow divide-y divide-slate-100">
            {features.map((f) => {
              const Icon = f.icon
              return (
                <div key={f.title} className="flex items-start gap-3 p-4">
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50 mt-0.5">
                    <Icon className="h-4 w-4 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-800">{f.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{f.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Getting started checklist ── */}
      <div className="bg-white rounded-xl border border-slate-200 card-shadow p-6">
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
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-50 text-blue-700 text-xs font-bold">
                  {completedCount}/{checklistSteps.length}
                </div>
                {completedCount === checklistSteps.length && (
                  <span className="text-xs font-medium text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-full px-2 py-0.5">
                    Complete!
                  </span>
                )}
              </>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {!isLoading && (
          <div className="h-1.5 w-full bg-slate-100 rounded-full mb-5 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${(completedCount / checklistSteps.length) * 100}%`,
                background: 'linear-gradient(90deg, #1168d4, #1a85ff)',
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
                      ? 'border-emerald-100 bg-emerald-50/50'
                      : 'border-slate-200 bg-slate-50 hover:bg-blue-50 hover:border-blue-200'
                  }`}>
                    <div className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold transition-colors ${
                      step.done
                        ? 'border-emerald-500 bg-emerald-500 text-white'
                        : 'border-slate-300 text-slate-400 group-hover:border-blue-400 group-hover:text-blue-500'
                    }`}>
                      {step.done ? <CheckCircle2 className="h-3.5 w-3.5" /> : i + 1}
                    </div>
                    <span className={`text-sm font-medium flex-1 transition-colors ${
                      step.done
                        ? 'text-emerald-700 line-through decoration-emerald-300'
                        : 'text-slate-700 group-hover:text-blue-700'
                    }`}>
                      {step.title}
                    </span>
                    {!step.done && (
                      <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-blue-400 transition-colors" />
                    )}
                    {step.done && (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />
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
