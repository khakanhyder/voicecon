'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  Bot, Plus, Search, MoreHorizontal, Phone, Mic, Cpu,
  ArrowRight, Activity, Clock, ToggleLeft, ToggleRight, Trash2, Pencil,
} from 'lucide-react'

interface Agent {
  id: string
  name: string
  description: string
  llm_provider: string
  llm_model: string
  tts_provider: string
  stt_provider: string
  is_active: boolean
  created_at: string
}

const providerBadge: Record<string, string> = {
  openai: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  anthropic: 'bg-violet-50 text-violet-700 border-violet-200',
  deepgram: 'bg-blue-50 text-blue-700 border-blue-200',
  elevenlabs: 'bg-amber-50 text-amber-700 border-amber-200',
}

function AgentCard({ agent, onClick }: { agent: Agent; onClick: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="group bg-white rounded-xl border border-slate-200 card-shadow hover:card-shadow-md hover:border-slate-300 transition-all overflow-hidden">
      {/* Card header */}
      <div className="p-5 pb-4 cursor-pointer" onClick={onClick}>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 border border-blue-100">
              <Bot className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 leading-tight">{agent.name}</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Created {new Date(agent.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${agent.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-500 border-slate-200'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${agent.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`} />
              {agent.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>

        <p className="text-sm text-slate-500 line-clamp-2 mb-4 min-h-[2.5rem]">
          {agent.description || 'No description provided'}
        </p>

        {/* Provider tags */}
        <div className="flex flex-wrap gap-1.5">
          <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${providerBadge[agent.llm_provider] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
            <Cpu className="h-3 w-3" />
            {agent.llm_model}
          </span>
          <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${providerBadge[agent.tts_provider] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
            <Mic className="h-3 w-3" />
            {agent.tts_provider}
          </span>
          <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${providerBadge[agent.stt_provider] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
            <Activity className="h-3 w-3" />
            {agent.stt_provider}
          </span>
        </div>
      </div>

      {/* Card footer */}
      <div className="border-t border-slate-100 bg-slate-50 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> 0 calls</span>
          <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> 0 min</span>
        </div>
        <div className="flex items-center gap-1">
          <Link href={`/dashboard/agents/${agent.id}/edit`} onClick={(e) => e.stopPropagation()}>
            <button className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:bg-white hover:text-slate-700 hover:border hover:border-slate-200 transition-all">
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </button>
          </Link>
          <button
            onClick={(e) => { e.stopPropagation(); onClick() }}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 transition-all"
          >
            View <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AgentsPage() {
  const router = useRouter()
  const [agents, setAgents] = useState<Agent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetchAgents()
  }, [])

  const fetchAgents = async () => {
    try {
      const response = await apiClient.get<{ agents: Agent[]; total: number }>(API_ENDPOINTS.AGENTS)
      setAgents(response.data.agents || [])
    } catch (error) {
      console.error('Failed to fetch agents:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  const filtered = agents.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.description?.toLowerCase().includes(search.toLowerCase())
  )

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-7 w-32 bg-slate-200 rounded-lg animate-pulse" />
            <div className="h-4 w-56 bg-slate-100 rounded mt-2 animate-pulse" />
          </div>
          <div className="h-9 w-28 bg-slate-200 rounded-lg animate-pulse" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 h-52 animate-pulse">
              <div className="flex gap-3 mb-4">
                <div className="h-11 w-11 bg-slate-100 rounded-xl" />
                <div className="flex-1">
                  <div className="h-4 w-32 bg-slate-100 rounded" />
                  <div className="h-3 w-24 bg-slate-100 rounded mt-1.5" />
                </div>
              </div>
              <div className="h-3 bg-slate-100 rounded w-full mb-2" />
              <div className="h-3 bg-slate-100 rounded w-3/4" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search agents…"
            className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:border-blue-500 focus:ring-3 focus:ring-blue-500/15 transition-all"
          />
        </div>
        <Link href="/dashboard/agents/new">
          <button className="flex items-center gap-2 rounded-lg gradient-primary px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm whitespace-nowrap">
            <Plus className="h-4 w-4" />
            New Agent
          </button>
        </Link>
      </div>

      {/* Summary bar */}
      {agents.length > 0 && (
        <div className="flex items-center gap-4 text-sm text-slate-500">
          <span><span className="font-semibold text-slate-900">{agents.length}</span> agents total</span>
          <span><span className="font-semibold text-emerald-600">{agents.filter(a => a.is_active).length}</span> active</span>
          {search && <span className="text-blue-600">{filtered.length} matching &ldquo;{search}&rdquo;</span>}
        </div>
      )}

      {/* Agent grid or empty state */}
      {filtered.length === 0 && !isLoading ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-white py-20 px-8 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 mb-5">
            <Bot className="h-8 w-8 text-blue-400" />
          </div>
          {search ? (
            <>
              <h3 className="text-lg font-semibold text-slate-800">No agents match &ldquo;{search}&rdquo;</h3>
              <p className="text-slate-500 text-sm mt-1.5">Try a different search term</p>
              <button onClick={() => setSearch('')} className="mt-4 text-sm text-blue-600 hover:text-blue-700 font-medium">
                Clear search
              </button>
            </>
          ) : (
            <>
              <h3 className="text-lg font-semibold text-slate-800">No agents yet</h3>
              <p className="text-slate-500 text-sm mt-1.5 max-w-xs">
                Create your first AI voice agent to start handling calls automatically
              </p>
              <Link href="/dashboard/agents/new">
                <button className="mt-6 flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm">
                  <Plus className="h-4 w-4" />
                  Create your first agent
                </button>
              </Link>
            </>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onClick={() => router.push(`/dashboard/agents/${agent.id}`)}
            />
          ))}

          {/* Add another card */}
          <Link href="/dashboard/agents/new">
            <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-8 h-full min-h-48 hover:border-blue-300 hover:bg-blue-50 transition-all group cursor-pointer">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border-2 border-dashed border-slate-300 group-hover:border-blue-400 transition-colors mb-3">
                <Plus className="h-5 w-5 text-slate-400 group-hover:text-blue-500 transition-colors" />
              </div>
              <p className="text-sm font-medium text-slate-500 group-hover:text-blue-600 transition-colors">Add agent</p>
            </div>
          </Link>
        </div>
      )}
    </div>
  )
}
