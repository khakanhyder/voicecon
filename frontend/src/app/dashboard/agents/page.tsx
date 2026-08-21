'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import { ConfirmModal } from '@/components/ui/confirm-modal'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { PERMISSIONS } from '@/lib/workspace'
import {
  Bot, Plus, Search, MoreHorizontal, Phone, Mic, Cpu,
  Activity, Clock, ToggleLeft, ToggleRight, Trash2, Pencil,
  Users, LayoutGrid, List, Headphones, User, ShoppingCart, Calendar, HelpCircle
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

interface AgentStats {
  total_calls: number
  completed_calls: number
  total_duration_seconds: number
  /** Null when the agent has never been called — there is no rate to report. */
  success_rate: number | null
  last_call_at: string | null
}

/** Zeroes for an agent the stats endpoint has no row for: it has taken no calls. */
const EMPTY_STATS: AgentStats = {
  total_calls: 0,
  completed_calls: 0,
  total_duration_seconds: 0,
  success_rate: null,
  last_call_at: null,
}

function formatTotalTime(seconds: number) {
  if (!seconds) return '0m'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`
  if (m > 0) return `${m}m`
  return `${seconds}s`
}

/**
 * Every card carries the sidebar's brand green (#0F6A59) — only the glyph
 * rotates, so a wall of agents reads as one family.
 */
const CARD_ACCENT = { bg: 'bg-[#0F6A59]/10', text: 'text-[#0F6A59]' }

const cardStyles = [Headphones, User, ShoppingCart, Calendar, HelpCircle].map(Icon => ({ ...CARD_ACCENT, Icon }))

const providerBadge: Record<string, string> = {
  openai: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  anthropic: 'bg-violet-50 text-violet-700 border-violet-200',
  deepgram: 'bg-blue-50 text-blue-700 border-blue-200',
  elevenlabs: 'bg-amber-50 text-amber-700 border-amber-200',
}

function Waveform() {
  // A simple deterministic pseudo-waveform pattern
  const heights = [3, 5, 8, 4, 10, 6, 2, 7, 9, 3, 5, 8, 12, 6, 4, 9, 5, 3, 7, 4, 8, 5, 3, 10, 6, 4, 8, 5, 2, 6, 9, 4, 7, 3, 5, 8, 4, 10, 6, 2, 7, 9, 3, 5, 8, 12, 6, 4, 9, 5, 3, 7, 4]
  return (
    <div className="flex items-center gap-[2px] h-12 w-full max-w-full overflow-hidden opacity-30 my-2">
      {heights.map((h, i) => (
        <div key={i} className="w-[3px] bg-purple-500 rounded-full flex-shrink-0" style={{ height: `${h * 2.5}px` }} />
      ))}
    </div>
  )
}

function AgentCard({ agent, index, viewMode, stats, onClick, onDelete, canWrite, canDelete }: { agent: Agent; index: number; viewMode: 'grid' | 'list'; stats: AgentStats; onClick: () => void; onDelete: () => void; canWrite: boolean; canDelete: boolean }) {
  const style = cardStyles[index % cardStyles.length]
  const IconComponent = style.Icon
  const successRate = stats.success_rate == null ? '—' : `${stats.success_rate}%`

  if (viewMode === 'list') {
    return (
      <div className={`group bg-white rounded-xl border border-slate-200 flex flex-col xl:flex-row xl:items-center shadow-sm hover:shadow-[0_4px_12px_rgba(0,0,0,0.05)] transition-all overflow-hidden p-4 gap-4 xl:gap-6`}>
        {/* Icon and Name */}
        <div className="flex items-start gap-4 xl:w-1/3 cursor-pointer" onClick={onClick}>
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${style.bg}`}>
            <IconComponent className={`h-6 w-6 ${style.text}`} />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-lg leading-tight">{agent.name}</h3>
            <p className="text-sm text-slate-500 mt-0.5 line-clamp-1">{agent.description || 'No description provided.'}</p>
            <div className="flex items-center gap-1.5 mt-1.5 text-xs text-slate-400">
              <Calendar className="w-3.5 h-3.5" />
              Created {new Date(agent.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center justify-between xl:justify-center xl:gap-8 py-3 border-y xl:border-y-0 xl:border-x border-slate-100 xl:px-6 xl:w-1/3 cursor-pointer" onClick={onClick}>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 text-slate-900 font-bold text-sm">
              <Phone className="w-3.5 h-3.5 text-slate-400" />
              {stats.total_calls}
            </div>
            <span className="text-xs text-slate-400 mt-0.5">Calls</span>
          </div>
          <div className="w-px h-8 bg-slate-200 hidden xl:block"></div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 text-slate-900 font-bold text-sm">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              {formatTotalTime(stats.total_duration_seconds)}
            </div>
            <span className="text-xs text-slate-400 mt-0.5">Time</span>
          </div>
          <div className="w-px h-8 bg-slate-200 hidden xl:block"></div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 text-slate-900 font-bold text-sm">
              <Activity className="w-3.5 h-3.5 text-slate-400" />
              {successRate}
            </div>
            <span className="text-xs text-slate-400 mt-0.5">Success rate</span>
          </div>
        </div>

        {/* Actions & Providers */}
        <div className="flex items-center justify-between xl:justify-end xl:flex-1 gap-4">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${providerBadge[agent.llm_provider] || 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
              <Cpu className="h-3 w-3" /> {agent.llm_model}
            </span>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${providerBadge[agent.tts_provider] || 'bg-blue-50 text-blue-700 border-blue-200'}`}>
              <Activity className="h-3 w-3" /> {agent.tts_provider}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {canWrite && (
              <Link href={`/dashboard/agents/${agent.id}`} onClick={(e) => e.stopPropagation()}>
                <button className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors">
                  <Pencil className="h-4 w-4" /> Edit
                </button>
              </Link>
            )}
            {canDelete && (
              <button
                aria-label={`Delete ${agent.name}`}
                onClick={(e) => { e.stopPropagation(); onDelete(); }}
                className="flex items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } }}
      className={`group cursor-pointer bg-white rounded-xl border border-slate-200 flex flex-col justify-between shadow-sm hover:shadow-md hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0F6A59]/40 transition-all overflow-hidden p-5`}
    >
      <div>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-start gap-4">
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${style.bg}`}>
              <IconComponent className={`h-6 w-6 ${style.text}`} />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-lg leading-tight">{agent.name}</h3>
              <p className="text-sm text-slate-500 mt-1 line-clamp-2 pr-4 min-h-[40px]">
                {agent.description || 'No description provided for this agent.'}
              </p>
              <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-400">
                <Calendar className="w-3.5 h-3.5" />
                Created {new Date(agent.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold border ${agent.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-500 border-slate-200'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${agent.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`} />
              {agent.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>

        {/* <Waveform /> */}

        {/* Provider tags */}
        <div className="flex flex-wrap gap-2 mb-6">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${providerBadge[agent.llm_provider] || 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
            <Cpu className="h-3.5 w-3.5" />
            {agent.llm_model}
          </span>
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${providerBadge[agent.tts_provider] || 'bg-blue-50 text-blue-700 border-blue-200'}`}>
            <Activity className="h-3.5 w-3.5" />
            {agent.tts_provider}
          </span>
        </div>

        {/* Stats Row */}
        <div className="flex items-center justify-between border-t border-slate-100 pt-4">
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 text-slate-900 font-bold text-sm">
              <Phone className="w-3.5 h-3.5 text-slate-400" />
              {stats.total_calls}
            </div>
            <span className="text-xs text-slate-400 mt-0.5">Calls</span>
          </div>
          <div className="w-px h-8 bg-slate-200"></div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 text-slate-900 font-bold text-sm">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              {formatTotalTime(stats.total_duration_seconds)}
            </div>
            <span className="text-xs text-slate-400 mt-0.5">Total time</span>
          </div>
          <div className="w-px h-8 bg-slate-200"></div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 text-slate-900 font-bold text-sm">
              <Activity className="w-3.5 h-3.5 text-slate-400" />
              {successRate}
            </div>
            <span className="text-xs text-slate-400 mt-0.5">Success rate</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function AgentsPage() {
  const router = useRouter()
  // Agents belong to the workspace, so what you may do to them depends on your
  // role in it, not on who created them. A viewer gets a read-only list.
  const workspace = useWorkspaceStore((s) => s.current)
  const canWrite = workspace?.permissions.includes(PERMISSIONS.agentsWrite) ?? false
  const canDelete = workspace?.permissions.includes(PERMISSIONS.agentsDelete) ?? false
  const [agents, setAgents] = useState<Agent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [sortBy, setSortBy] = useState('Newest')
  const [agentToDelete, setAgentToDelete] = useState<Agent | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [stats, setStats] = useState<Record<string, AgentStats>>({})

  useEffect(() => {
    fetchAgents()
    fetchStats()
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

  // Stats are supplementary: if this call fails the cards still render, just
  // with zeroes, rather than taking the whole page down with a toast.
  const fetchStats = async () => {
    try {
      const response = await apiClient.get<{ stats: Record<string, AgentStats> }>(API_ENDPOINTS.AGENT_STATS)
      setStats(response.data.stats || {})
    } catch (error) {
      console.error('Failed to fetch agent stats:', error)
    }
  }

  const handleDeleteAgent = async () => {
    if (!agentToDelete) return
    setIsDeleting(true)
    try {
      await apiClient.delete(`${API_ENDPOINTS.AGENTS}/${agentToDelete.id}`)
      toast.success('Agent deleted successfully')
      setAgents(agents.filter(a => a.id !== agentToDelete.id))
      setAgentToDelete(null)
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
    }
  }

  const filtered = agents
    .filter(a =>
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.description?.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      if (sortBy === 'Name') return a.name.localeCompare(b.name);
      if (sortBy === 'Most Active') return (b.is_active === a.is_active) ? 0 : b.is_active ? -1 : 1;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex h-20 bg-white rounded border border-slate-200 animate-pulse mb-6"></div>
        <div className={`grid gap-6 ${viewMode === 'grid' ? 'sm:grid-cols-2 lg:grid-cols-3' : 'grid-cols-1'}`}>
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 h-[260px] animate-pulse">
              <div className="flex gap-4 mb-4">
                <div className="h-12 w-12 bg-slate-100 rounded-full shrink-0" />
                <div className="flex-1">
                  <div className="h-5 w-32 bg-slate-100 rounded mb-2" />
                  <div className="h-4 w-full bg-slate-100 rounded mb-1" />
                  <div className="h-4 w-3/4 bg-slate-100 rounded" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Search & Header replacing original Toolbar & Summary */}
      <div className="flex flex-col md:flex-row md:items-center justify-between bg-white rounded-xl border border-slate-200 p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] mb-6 gap-4">
        <div className="flex items-center gap-6 md:gap-8 flex-wrap">
          <div className="flex items-center gap-3 md:border-r border-slate-100 md:pr-8">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <Users className="h-6 w-6" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-500 mb-0.5">Total Agents</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900 leading-none">{agents.length}</span>
                <span className="text-xs text-slate-400">All configured agents</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#0F6A59]/10 text-[#0F6A59]">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-500 mb-0.5">Active Agents</div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-slate-900 leading-none">{agents.filter(a => a.is_active).length}</span>
                <span className="text-xs text-slate-400">Currently active</span>
                <span className="hidden sm:inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-600 border border-emerald-100 ml-2">
                  {agents.length > 0 ? Math.round((agents.filter(a => a.is_active).length / agents.length) * 100) : 0}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden sm:flex bg-slate-50 rounded-lg p-1 border border-slate-200 items-center">
            <button aria-label="Grid view" aria-pressed={viewMode === 'grid'} onClick={() => setViewMode('grid')} className={`rounded p-1.5 transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm' : 'hover:bg-slate-100'}`}>
              <LayoutGrid className={`w-4 h-4 ${viewMode === 'grid' ? 'text-emerald-600' : 'text-slate-400'}`} />
            </button>
            <button aria-label="List view" aria-pressed={viewMode === 'list'} onClick={() => setViewMode('list')} className={`rounded p-1.5 transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm' : 'hover:bg-slate-100'}`}>
              <List className={`w-4 h-4 ${viewMode === 'list' ? 'text-emerald-600' : 'text-slate-400'}`} />
            </button>
          </div>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="border border-slate-200 rounded-lg text-sm font-medium text-slate-600 py-2 pl-3 pr-8 outline-none bg-white hover:bg-slate-50 appearance-none cursor-pointer"
          >
            <option value="Newest">Sort by: Newest</option>
            <option value="Name">Sort by: Name</option>
            <option value="Most Active">Sort by: Most Active</option>
          </select>
        </div>
      </div>

      {search && filtered.length > 0 && (
        <div className="text-sm text-slate-500 mb-4 px-1">
          Found {filtered.length} agent{filtered.length === 1 ? '' : 's'} matching &ldquo;<span className="font-semibold text-slate-900">{search}</span>&rdquo;
        </div>
      )}

      {/* Agent grid or empty state */}
      {filtered.length === 0 && !isLoading ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-white py-20 px-8 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#0F6A59]/10 mb-5">
            <Bot className="h-8 w-8 text-[#0F6A59]/60" />
          </div>
          {search ? (
            <>
              <h3 className="text-lg font-semibold text-slate-800">No agents match &ldquo;{search}&rdquo;</h3>
              <p className="text-slate-500 text-sm mt-1.5">Try a different search term</p>
              <button onClick={() => setSearch('')} className="mt-4 text-sm text-[#0F6A59] hover:text-[#0d5a4c] font-medium">
                Clear search
              </button>
            </>
          ) : (
            <>
              <h3 className="text-lg font-semibold text-slate-800">No agents yet</h3>
              <p className="text-slate-500 text-sm mt-1.5 max-w-xs">
                {canWrite
                  ? 'Create your first AI voice agent to start handling calls automatically'
                  : 'Nobody on this team has created an agent yet. Your role is read-only.'}
              </p>
              {canWrite && (
                <Link href="/dashboard/agents/new">
                  <button className="mt-6 flex items-center gap-2 rounded-lg bg-[#0F6A59] hover:bg-[#0d5a4c] px-5 py-2.5 text-sm font-semibold text-white transition-all shadow-sm">
                    <Plus className="h-4 w-4" />
                    Create your first agent
                  </button>
                </Link>
              )}
            </>
          )}
        </div>
      ) : (
        <div className={`grid gap-6 ${viewMode === 'grid' ? 'sm:grid-cols-2 lg:grid-cols-3' : 'grid-cols-1'}`}>
          {filtered.map((agent, index) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              index={index}
              viewMode={viewMode}
              stats={stats[agent.id] ?? EMPTY_STATS}
              onClick={() => router.push(`/dashboard/agents/${agent.id}`)}
              onDelete={() => setAgentToDelete(agent)}
              canWrite={canWrite}
              canDelete={canDelete}
            />
          ))}

          {/* Add another card — creation affordance, so contributors only */}
          {canWrite && (
          <Link href="/dashboard/agents/new">
            <div className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/50 p-8 hover:border-[#0F6A59]/40 hover:bg-[#0F6A59]/5 transition-all group cursor-pointer ${viewMode === 'list' ? 'h-[162px]' : 'h-full min-h-[240px]'
              }`}>
              <div className={`flex items-center justify-center rounded-full bg-[#0F6A59]/10 transition-colors mb-4 ${viewMode === 'list' ? 'h-12 w-12' : 'h-16 w-16'
                }`}>
                <Plus className={`${viewMode === 'list' ? 'h-5 w-5' : 'h-6 w-6'} text-[#0F6A59] transition-colors`} />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Add New Agent</h3>
              {viewMode === 'grid' && (
                <p className="text-sm font-medium text-slate-500 text-center mb-6">
                  Create a new AI voice agent<br />in just a few steps.
                </p>
              )}
              <button className={`bg-[#0F6A59] hover:bg-[#0c5044] text-white rounded-lg py-2.5 text-sm font-bold flex items-center gap-2 transition-colors ${viewMode === 'list' ? 'px-4' : 'px-6'
                }`}>
                <Plus className="w-4 h-4" /> New Agent
              </button>
            </div>
          </Link>
          )}
        </div>
      )}

      <ConfirmModal
        isOpen={!!agentToDelete}
        title="Delete Agent"
        description={`Are you sure you want to delete ${agentToDelete?.name}? This action cannot be undone.`}
        confirmText="Delete Agent"
        cancelText="Cancel"
        isDestructive={true}
        isLoading={isDeleting}
        onConfirm={handleDeleteAgent}
        onCancel={() => setAgentToDelete(null)}
      />
    </div>
  )
}
