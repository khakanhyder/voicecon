'use client'

/**
 * Call history for a single agent. Carried over from the old agent view page,
 * which is now folded into the agent editor.
 */

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { Phone, PhoneIncoming, PhoneOutgoing, ArrowUpRight } from 'lucide-react'

interface AgentCall {
  id: string
  direction: 'inbound' | 'outbound'
  status: string
  from_number: string
  to_number: string
  duration_seconds: number | null
  cost_total: number | null
  started_at: string | null
}

const STATUS_COLOR: Record<string, string> = {
  completed:   'bg-emerald-50 text-emerald-700 border-emerald-200',
  failed:      'bg-red-50 text-red-700 border-red-200',
  missed:      'bg-amber-50 text-amber-700 border-amber-200',
  in_progress: 'bg-blue-50 text-blue-700 border-blue-200',
  initiated:   'bg-slate-50 text-slate-600 border-slate-200',
}

export function AgentCallsTab({ agentId }: { agentId: string }) {
  const [calls, setCalls] = useState<AgentCall[]>([])
  const [loading, setLoading] = useState(true)

  const fetchCalls = useCallback(async () => {
    setLoading(true)
    try {
      const r = await apiClient.get<{ calls: AgentCall[]; total: number }>(
        `${API_ENDPOINTS.CALLS}?agent_id=${agentId}&limit=50`
      )
      setCalls(r.data.calls || [])
    } catch {
      // A dead calls endpoint shouldn't blank the editor — show the empty state.
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => { if (agentId) fetchCalls() }, [agentId, fetchCalls])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-500">Recent calls handled by this agent.</p>
        <button
          onClick={fetchCalls}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-all"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1,2,3].map(i => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}
        </div>
      ) : calls.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 mb-4">
            <Phone className="h-7 w-7 text-slate-300" />
          </div>
          <p className="text-sm font-medium text-slate-600">No calls yet</p>
          <p className="text-xs text-slate-400 mt-1">Call history will appear here once this agent handles calls.</p>
        </div>
      ) : (
        <div className="divide-y divide-slate-200 rounded-[8px] border border-slate-200 overflow-hidden">
          <div className="hidden md:grid grid-cols-[2rem_1fr_6rem_5rem_6rem_3rem] gap-3 px-4 py-2.5 bg-slate-50 text-xs font-semibold text-slate-400 uppercase tracking-wide">
            <div />
            <div>From / To</div>
            <div>Status</div>
            <div>Duration</div>
            <div>When</div>
            <div />
          </div>
          {calls.map(call => {
            const dur = call.duration_seconds
            const durStr = !dur ? '—' : dur < 60 ? `${dur}s` : `${Math.floor(dur/60)}m ${dur%60}s`
            const when = call.started_at ? (() => {
              const d = new Date(call.started_at), now = new Date()
              const diff = now.getTime() - d.getTime()
              if (diff < 60_000) return 'Just now'
              if (diff < 3_600_000) return `${Math.floor(diff/60_000)}m ago`
              if (diff < 86_400_000) return `${Math.floor(diff/3_600_000)}h ago`
              return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            })() : '—'
            return (
              <Link href={`/dashboard/calls/${call.id}`} key={call.id}>
                <div className="flex flex-col md:grid md:grid-cols-[2rem_1fr_6rem_5rem_6rem_3rem] gap-2 md:gap-3 px-4 py-3 hover:bg-slate-50 transition-colors group cursor-pointer">
                  <div className="hidden md:flex items-center">
                    {call.direction === 'inbound'
                      ? <PhoneIncoming className="h-3.5 w-3.5 text-slate-400" />
                      : <PhoneOutgoing className="h-3.5 w-3.5 text-slate-400" />}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-800">{call.from_number || '—'}</p>
                    <p className="text-xs text-slate-400">→ {call.to_number || '—'}</p>
                  </div>
                  <div className="flex items-center">
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_COLOR[call.status] || STATUS_COLOR.initiated}`}>
                      {call.status}
                    </span>
                  </div>
                  <div className="hidden md:flex items-center text-sm text-slate-500">{durStr}</div>
                  <div className="hidden md:flex items-center text-xs text-slate-400">{when}</div>
                  <div className="hidden md:flex items-center">
                    <ArrowUpRight className="h-4 w-4 text-slate-300 group-hover:text-blue-500 transition-colors" />
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
