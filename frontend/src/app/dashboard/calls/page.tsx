'use client'

import { useState, useEffect } from 'react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import Link from 'next/link'
import {
  Phone, Search,
  Clock, DollarSign, Bot, ChevronDown, ArrowUpRight, Download
} from 'lucide-react'

interface Call {
  id: string
  direction: 'inbound' | 'outbound' | 'test'
  status: 'completed' | 'failed' | 'missed' | 'in_progress' | 'initiated'
  from_number: string
  to_number: string
  duration_seconds: number | null
  cost_total: number | null
  started_at: string | null
  created_at: string
  agent_id: string | null
  agent_name?: string | null
  sentiment_label?: string
  call_metadata?: Record<string, any>
}

function formatDuration(seconds: number | null) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return '—'
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
    } catch { }
  }

  const filtered = calls.filter(c => {
    const matchSearch = !search || c.from_number?.includes(search) || c.to_number?.includes(search)
    const matchStatus = statusFilter === 'all' || c.status === statusFilter
    return matchSearch && matchStatus
  })

  const statCards = [
    { label: 'Total Calls', value: stats.total, icon: Phone, iconColor: 'text-[#106959]', iconBg: 'bg-[#0F6A5918]', accent: 'border-l-[#106959]', valueBg: 'from-[#0F6A5905] to-white' },
    { label: 'Completed', value: stats.completed, icon: Phone, iconColor: 'text-emerald-600', iconBg: 'bg-emerald-50', accent: 'border-l-emerald-500', valueBg: 'from-emerald-50/40 to-white' },
    { label: 'Active Now', value: stats.active, icon: Phone, iconColor: 'text-blue-600', iconBg: 'bg-blue-50', accent: 'border-l-blue-500', valueBg: 'from-blue-50/40 to-white' },
    { label: 'Total Minutes', value: stats.duration.toFixed(1), icon: Clock, iconColor: 'text-violet-600', iconBg: 'bg-violet-50', accent: 'border-l-violet-500', valueBg: 'from-violet-50/40 to-white' },
    { label: 'Total Cost', value: `$${stats.cost.toFixed(2)}`, icon: DollarSign, iconColor: 'text-amber-600', iconBg: 'bg-amber-50', accent: 'border-l-amber-500', valueBg: 'from-amber-50/40 to-white' },
  ]

  return (
    <div className="space-y-6">

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <div key={card.label} className={`flex items-center justify-between bg-gradient-to-br ${card.valueBg} rounded-[12px] border border-black/10 border-l-[3px] ${card.accent} p-5 hover:shadow-md transition-shadow duration-200`}>

              <div className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-[10px] ${card.iconBg}`}>
                <Icon className={`h-6 w-6 ${card.iconColor}`} />
              </div>
              <div>
                <div className="text-[28px] font-bold font-poppins text-[#000000] leading-none">{card.value}</div>
                <div className="text-[13px] font-poppins text-black/50 mt-1.5 font-medium">{card.label}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-black/40" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by phone number…"
            className="w-full h-[45px] rounded-[8px] bg-[#0F6A590A] border border-[#000000] pl-9 pr-4 font-poppins text-[14px] text-black placeholder:text-black/40 outline-none"
          />
        </div>
        <div className="relative">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="appearance-none h-[45px] rounded-[8px] bg-[#0F6A590A] border border-[#000000] pl-4 pr-9 font-poppins text-[14px] text-black outline-none cursor-pointer"
          >
            <option value="all">All statuses</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="missed">Missed</option>
            <option value="in_progress">In Progress</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-black/40 pointer-events-none" />
        </div>
      </div>

      {/* Table Export */}
      <div className="flex items-center justify-between mb-3 mt-2 pr-1">
        <div />
        <button className="flex items-center gap-1.5 text-[14px] font-poppins font-medium text-black hover:text-[#106959] transition-colors">
          Export CSV
          <Download className="h-4 w-4" />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-[10px] border border-[#000000] overflow-hidden">
        <div className="overflow-x-auto">
          <div className="min-w-[90rem] w-full">
            {/* Table Header Always Visible */}
            <div className="grid grid-cols-[2.5rem_6rem_2fr_3fr_3fr_2fr_2fr_2fr_6rem_5rem] gap-4 px-6 py-4 bg-[#0F6A5904] border-b border-[#000000] text-[14px] font-poppins text-[#000000] uppercase tracking-wide">
              <div className="flex items-center">
                <input title="Select all" type="checkbox" className="rounded-[4px] border border-black/20 text-[#106959] focus:ring-[#106959] h-4 w-4 cursor-pointer" />
              </div>
              <div>Call ID</div>
              <div>Assistant</div>
              <div>Assistant Phone Number</div>
              <div>Customer Phone Number</div>
              <div>End Reason</div>
              <div>Success Evaluation</div>
              <div>Start Time</div>
              <div>Duration</div>
              <div>Cost</div>
            </div>

            {isLoading ? (
              <div className="divide-y divide-[#E2E8F0]">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="flex items-center gap-4 px-6 py-5 animate-pulse">
                    <div className="h-4 w-4 bg-slate-200 rounded-[4px] flex-shrink-0" />
                    <div className="h-4 w-16 bg-slate-100 rounded" />
                    <div className="h-4 w-24 bg-slate-100 rounded" />
                    <div className="h-4 w-28 bg-slate-100 rounded" />
                    <div className="h-4 w-28 bg-slate-100 rounded" />
                    <div className="h-4 w-20 bg-slate-100 rounded" />
                    <div className="h-5 w-16 bg-slate-100 rounded-full" />
                    <div className="h-4 w-20 bg-slate-100 rounded" />
                    <div className="h-4 w-12 bg-slate-100 rounded" />
                    <div className="h-4 w-12 bg-slate-100 rounded" />
                  </div>
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 px-8 text-center bg-white">
                <div className="flex h-16 w-16 items-center justify-center rounded-[10px] bg-[#0F6A5910] mb-5">
                  <Phone className="h-8 w-8 text-[#106959]" />
                </div>
                <h3 className="text-[18px] font-bold font-poppins text-[#000000]">
                  {search || statusFilter !== 'all' ? 'No calls match your filters' : 'No calls yet'}
                </h3>
                <p className="text-black font-poppins text-[14px] mt-1.5 max-w-sm">
                  {search || statusFilter !== 'all'
                    ? 'Try adjusting your search or filters to find what you are looking for.'
                    : 'Your call history will appear here once your agents start making or receiving calls.'}
                </p>
                {calls.length === 0 && (
                  <Link href="/dashboard/agents">
                    <button className="mt-6 flex items-center gap-2 rounded-[8px] bg-[#106959] px-6 h-[45px] font-poppins font-semibold text-[14px] text-white hover:opacity-90 transition-all shadow-sm shadow-[#106959]/20">
                      View your agents
                      <ArrowUpRight className="h-4 w-4" />
                    </button>
                  </Link>
                )}
              </div>
            ) : (
              <div className="divide-y divide-[#E2E8F0]">
                {filtered.map((call) => {
                  const endReason = call.call_metadata?.disconnection_reason || call.status
                  const assistantPhone = call.direction === 'outbound' ? call.from_number : call.direction === 'inbound' ? call.to_number : 'Web Test'
                  const customerPhone = call.direction === 'inbound' ? call.from_number : call.direction === 'outbound' ? call.to_number : 'Web Test'

                  return (
                    <Link key={call.id} href={`/dashboard/calls/${call.id}`} className="block">
                      <div className="grid grid-cols-[2.5rem_6rem_2fr_3fr_3fr_2fr_2fr_2fr_6rem_5rem] gap-4 px-6 py-4 hover:bg-[#0F6A5908] transition-colors group cursor-pointer items-center">
                        <div className="flex items-center" onClick={(e) => e.stopPropagation()}>
                          <input type="checkbox" title="Select call" className="rounded-[4px] border border-black/20 text-[#106959] focus:ring-[#106959] h-4 w-4 cursor-pointer" />
                        </div>

                        <div className="text-[13px] font-poppins text-black/80 truncate font-medium" title={call.id}>
                          {call.id.slice(0, 8).toUpperCase()}
                        </div>

                        <div className="flex items-center gap-2 overflow-hidden">
                          <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-[#106959]/10">
                            <Bot className="h-3.5 w-3.5 text-[#106959]" />
                          </div>
                          <span
                            className="truncate text-[14px] font-poppins font-semibold text-[#000000]"
                            title={call.agent_name || call.agent_id || undefined}
                          >
                            {call.agent_name || (call.agent_id ? `${call.agent_id.slice(0, 8)}…` : 'Unknown')}
                          </span>
                        </div>

                        <div className="text-[14px] font-poppins text-black/70 truncate">
                          {assistantPhone}
                        </div>

                        <div className="text-[14px] font-poppins text-[#000000] font-medium truncate">
                          {customerPhone}
                        </div>

                        <div className="flex items-center">
                          <span className="truncate text-[13px] font-poppins text-black/70 capitalize max-w-[7.5rem]" title={endReason}>
                            {endReason.replace(/_/g, ' ')}
                          </span>
                        </div>

                        <div className="flex items-center">
                          {call.sentiment_label ? (
                            <span className={`inline-flex items-center rounded-[6px] px-2.5 py-1 text-xs font-semibold font-poppins capitalize ${call.sentiment_label === 'positive' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' :
                              call.sentiment_label === 'negative' ? 'bg-red-50 text-red-700 border border-red-100' :
                                'bg-blue-50 text-blue-700 border border-blue-100'
                              }`}>
                              {call.sentiment_label}
                            </span>
                          ) : (
                            <span className="text-[13px] font-poppins text-black/40">—</span>
                          )}
                        </div>

                        <div className="text-[13px] font-poppins text-black/70 truncate">
                          {formatDate(call.started_at || call.created_at)}
                        </div>

                        <div className="text-[13px] font-poppins text-black/70">
                          {formatDuration(call.duration_seconds)}
                        </div>

                        <div className="text-[13px] font-poppins font-semibold text-[#000000]">
                          {call.cost_total != null ? `$${Number(call.cost_total).toFixed(4)}` : '—'}
                        </div>
                      </div>
                    </Link>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
