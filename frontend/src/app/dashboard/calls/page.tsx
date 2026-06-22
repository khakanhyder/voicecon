'use client'

import { useState, useEffect } from 'react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import Link from 'next/link'
import {
  Phone, PhoneIncoming, PhoneOutgoing, Search,
  Clock, DollarSign, Bot, ChevronDown, ArrowUpRight, Monitor,
} from 'lucide-react'

interface Call {
  id: string
  direction: 'inbound' | 'outbound' | 'test'
  status: 'completed' | 'failed' | 'missed' | 'in_progress' | 'initiated'
  from_number: string
  to_number: string
  duration_seconds: number | null
  cost_total: number | null
  started_at: string
  agent_id: string
}

const statusConfig: Record<string, { color: string; bg: string }> = {
  completed: { color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200' },
  failed: { color: 'text-red-700', bg: 'bg-red-50 border-red-200' },
  missed: { color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200' },
  in_progress: { color: 'text-blue-700', bg: 'bg-blue-50 border-blue-200' },
  initiated: { color: 'text-slate-700', bg: 'bg-slate-50 border-slate-200' },
}

function formatDuration(seconds: number | null) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function CallsPage() {
  const [calls, setCalls] = useState<Call[]>([])
  const [stats, setStats] = useState({ total: 0, completed: 0, active: 0, duration: 0, cost: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  useEffect(() => {
    Promise.all([fetchCalls(), fetchStats()])
  }, [])

  const fetchCalls = async () => {
    try {
      const res = await apiClient.get<{ calls: Call[]; total: number }>(API_ENDPOINTS.CALLS)
      setCalls(res.data.calls || [])
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const res = await apiClient.get<any>(API_ENDPOINTS.CALL_STATS)
      const d = res.data
      setStats({
        total: d.total_calls || 0,
        completed: d.completed_calls || 0,
        active: d.active_calls || 0,
        duration: d.total_duration_minutes || 0,
        cost: d.total_cost || 0,
      })
    } catch {}
  }

  const filtered = calls.filter(c => {
    const matchSearch = !search || c.from_number?.includes(search) || c.to_number?.includes(search)
    const matchStatus = statusFilter === 'all' || c.status === statusFilter
    return matchSearch && matchStatus
  })

  const statCards = [
    { label: 'Total Calls', value: stats.total, icon: Phone, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Completed', value: stats.completed, icon: Phone, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Active Now', value: stats.active, icon: Phone, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Total Minutes', value: stats.duration.toFixed(1), icon: Clock, color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'Total Cost', value: `$${stats.cost.toFixed(2)}`, icon: DollarSign, color: 'text-amber-600', bg: 'bg-amber-50' },
  ]

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <div key={card.label} className="bg-white rounded-xl border border-slate-200 p-4 card-shadow">
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${card.bg} mb-3`}>
                <Icon className={`h-4 w-4 ${card.color}`} />
              </div>
              <div className="text-xl font-bold text-slate-900">{card.value}</div>
              <div className="text-xs text-slate-500 mt-0.5">{card.label}</div>
            </div>
          )
        })}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by phone number…"
            className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 transition-all"
          />
        </div>
        <div className="relative">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="appearance-none rounded-lg border border-slate-300 bg-white pl-4 pr-9 py-2.5 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 transition-all cursor-pointer"
          >
            <option value="all">All statuses</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="missed">Missed</option>
            <option value="in_progress">In Progress</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 card-shadow overflow-hidden">
        {isLoading ? (
          <div className="divide-y divide-slate-100">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="flex items-center gap-4 px-6 py-4 animate-pulse">
                <div className="h-9 w-9 bg-slate-100 rounded-lg flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-3.5 w-32 bg-slate-100 rounded" />
                  <div className="h-3 w-48 bg-slate-100 rounded" />
                </div>
                <div className="h-5 w-20 bg-slate-100 rounded-full" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 mb-5">
              <Phone className="h-8 w-8 text-slate-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-800">
              {search || statusFilter !== 'all' ? 'No calls match your filters' : 'No calls yet'}
            </h3>
            <p className="text-slate-500 text-sm mt-1.5 max-w-xs">
              {search || statusFilter !== 'all'
                ? 'Try adjusting your search or filters'
                : 'Your call history will appear here once agents start handling calls'}
            </p>
            {calls.length === 0 && (
              <Link href="/dashboard/agents/new">
                <button className="mt-6 flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-all">
                  Create your first agent
                  <ArrowUpRight className="h-4 w-4" />
                </button>
              </Link>
            )}
          </div>
        ) : (
          <>
            <div className="hidden md:grid grid-cols-[2rem_1fr_1fr_7rem_6rem_7rem_3rem] gap-4 px-6 py-3 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wide">
              <div />
              <div>From / To</div>
              <div>Agent</div>
              <div>Status</div>
              <div>Duration</div>
              <div>When</div>
              <div />
            </div>

            <div className="divide-y divide-slate-100">
              {filtered.map((call) => {
                const status = statusConfig[call.status] || statusConfig.initiated
                return (
                  <Link key={call.id} href={`/dashboard/calls/${call.id}`}>
                  <div className="flex flex-col md:grid md:grid-cols-[2rem_1fr_1fr_7rem_6rem_7rem_3rem] gap-2 md:gap-4 px-4 md:px-6 py-4 hover:bg-slate-50 transition-colors group cursor-pointer">
                    <div className="hidden md:flex items-center">
                      {call.direction === 'test'
                        ? <Monitor className="h-4 w-4 text-blue-400" />
                        : call.direction === 'inbound'
                        ? <PhoneIncoming className="h-4 w-4 text-slate-400" />
                        : <PhoneOutgoing className="h-4 w-4 text-slate-400" />
                      }
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 md:hidden">
                        {call.direction === 'test'
                          ? <Monitor className="h-4 w-4 text-blue-500" />
                          : call.direction === 'inbound'
                          ? <PhoneIncoming className="h-4 w-4 text-slate-500" />
                          : <PhoneOutgoing className="h-4 w-4 text-slate-500" />
                        }
                      </div>
                      <div>
                        {call.direction === 'test' ? (
                          <>
                            <p className="text-sm font-medium text-slate-900">Web Test Call</p>
                            <p className="text-xs text-slate-400">Browser · Dashboard</p>
                          </>
                        ) : (
                          <>
                            <p className="text-sm font-medium text-slate-900">{call.from_number || '—'}</p>
                            <p className="text-xs text-slate-400">→ {call.to_number || '—'}</p>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="hidden md:flex items-center">
                      <span className="inline-flex items-center gap-1.5 text-sm text-slate-500">
                        <Bot className="h-3.5 w-3.5" />
                        <span className="truncate max-w-[8rem]">{call.agent_id?.slice(0, 8) || '—'}</span>
                      </span>
                    </div>
                    <div className="flex items-center">
                      <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${status.bg} ${status.color}`}>
                        {call.status}
                      </span>
                    </div>
                    <div className="hidden md:flex items-center text-sm text-slate-600">
                      {formatDuration(call.duration_seconds)}
                    </div>
                    <div className="hidden md:flex items-center text-sm text-slate-500">
                      {formatDate(call.started_at)}
                    </div>
                    <div className="hidden md:flex items-center">
                      <button className="opacity-0 group-hover:opacity-100 transition-opacity rounded-lg p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50">
                        <ArrowUpRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  </Link>
                )
              })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
