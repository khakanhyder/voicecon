'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import {
  Users, Search, Phone, PhoneIncoming, PhoneOutgoing, ChevronRight,
  Clock, FileText, ArrowUpRight, Smile, Meh, Frown,
} from 'lucide-react'

interface Contact {
  contact_number: string
  total_calls: number
  completed_calls: number
  total_duration_seconds: number
  total_cost: number
  avg_sentiment_score: number | null
  last_call_at: string | null
}

interface ContactCall {
  id: string
  direction: 'inbound' | 'outbound' | 'test'
  status: string
  from_number: string
  to_number: string
  duration_seconds: number | null
  cost_total: number | null
  sentiment_score: number | null
  sentiment_label: string | null
  summary: string | null
  started_at: string | null
}

const statusConfig: Record<string, { color: string; bg: string }> = {
  completed: { color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200' },
  failed: { color: 'text-red-700', bg: 'bg-red-50 border-red-200' },
  missed: { color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200' },
  in_progress: { color: 'text-blue-700', bg: 'bg-blue-50 border-blue-200' },
  initiated: { color: 'text-slate-600', bg: 'bg-slate-50 border-slate-200' },
}

function fmtDuration(seconds: number | null) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function fmtDate(dateStr: string | null) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function SentimentIcon({ score }: { score: number | null }) {
  if (score == null) return <Meh className="h-3.5 w-3.5 text-slate-300" />
  if (score > 0.6) return <Smile className="h-3.5 w-3.5 text-emerald-500" />
  if (score < 0.4) return <Frown className="h-3.5 w-3.5 text-red-400" />
  return <Meh className="h-3.5 w-3.5 text-amber-400" />
}

export default function CallerHistory() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [calls, setCalls] = useState<ContactCall[]>([])
  const [callsLoading, setCallsLoading] = useState(false)

  useEffect(() => {
    apiClient.get<{ contacts: Contact[] }>(API_ENDPOINTS.CALL_CONTACTS)
      .then(r => setContacts(r.data.contacts || []))
      .catch(() => setContacts([]))
      .finally(() => setLoading(false))
  }, [])

  const selectContact = useCallback((number: string) => {
    setSelected(number)
    setCallsLoading(true)
    apiClient.get<{ calls: ContactCall[] }>(API_ENDPOINTS.CALL_CONTACT_CALLS(number))
      .then(r => setCalls(r.data.calls || []))
      .catch(() => setCalls([]))
      .finally(() => setCallsLoading(false))
  }, [])

  const filtered = contacts.filter(c =>
    !search || c.contact_number.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <Users className="h-4 w-4 text-slate-400" />
          Caller History
          {!loading && (
            <span className="text-xs font-normal text-slate-400">{contacts.length} callers</span>
          )}
        </h3>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search callers…"
            className="w-56 rounded-lg border border-slate-300 bg-white pl-8 pr-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 transition-all"
          />
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}
        </div>
      ) : contacts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Users className="h-8 w-8 text-slate-200 mb-2" />
          <p className="text-sm text-slate-400">No callers yet</p>
          <p className="text-xs text-slate-300 mt-1">
            Callers appear here once your agents handle phone calls
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Caller list */}
          <div className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
            {filtered.length === 0 ? (
              <p className="text-sm text-slate-400 py-6 text-center">No callers match “{search}”.</p>
            ) : filtered.map(c => {
              const isSelected = selected === c.contact_number
              return (
                <button
                  key={c.contact_number}
                  onClick={() => selectContact(c.contact_number)}
                  className={`w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                    isSelected
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-slate-100 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-slate-100">
                    <Phone className="h-4 w-4 text-slate-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{c.contact_number}</p>
                    <p className="text-xs text-slate-400">
                      {c.total_calls} call{c.total_calls !== 1 ? 's' : ''} · {fmtDate(c.last_call_at)}
                    </p>
                  </div>
                  <SentimentIcon score={c.avg_sentiment_score} />
                  <ChevronRight className={`h-4 w-4 flex-shrink-0 ${isSelected ? 'text-blue-500' : 'text-slate-300'}`} />
                </button>
              )
            })}
          </div>

          {/* Selected caller's calls */}
          <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3 min-h-[200px]">
            {!selected ? (
              <div className="flex flex-col items-center justify-center h-full py-12 text-center">
                <FileText className="h-8 w-8 text-slate-200 mb-2" />
                <p className="text-sm text-slate-400">Select a caller</p>
                <p className="text-xs text-slate-300 mt-1">View their full call history and summaries</p>
              </div>
            ) : callsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => <div key={i} className="h-16 bg-white rounded-lg animate-pulse" />)}
              </div>
            ) : (
              <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                <p className="text-xs font-semibold text-slate-500 px-1 mb-1">
                  {calls.length} call{calls.length !== 1 ? 's' : ''} with {selected}
                </p>
                {calls.map(call => {
                  const status = statusConfig[call.status] || statusConfig.initiated
                  return (
                    <Link key={call.id} href={`/dashboard/calls/${call.id}`}>
                      <div className="group bg-white rounded-lg border border-slate-100 p-3 hover:border-blue-200 hover:shadow-sm transition-all cursor-pointer">
                        <div className="flex items-center gap-2 mb-1">
                          {call.direction === 'inbound'
                            ? <PhoneIncoming className="h-3.5 w-3.5 text-slate-400" />
                            : <PhoneOutgoing className="h-3.5 w-3.5 text-slate-400" />}
                          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${status.bg} ${status.color}`}>
                            {call.status}
                          </span>
                          <span className="text-xs text-slate-400 flex items-center gap-1">
                            <Clock className="h-3 w-3" /> {fmtDuration(call.duration_seconds)}
                          </span>
                          <span className="text-xs text-slate-400 ml-auto">{fmtDate(call.started_at)}</span>
                          <ArrowUpRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-blue-500 transition-colors" />
                        </div>
                        <p className="text-xs text-slate-600 line-clamp-2">
                          {call.summary || <span className="italic text-slate-400">No summary available yet</span>}
                        </p>
                      </div>
                    </Link>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
