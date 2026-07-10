'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  Bot, Pencil, Trash2, ToggleLeft, ToggleRight, ArrowLeft, ChevronRight,
  Cpu, Mic, Volume2, Clock, Calendar, Settings2, MessageSquare,
  Phone, PhoneOff, PhoneCall, X, Send, Radio, Wifi,
  Shield, Sliders, Zap, Copy, Check, PhoneIncoming, PhoneOutgoing,
  ArrowUpRight,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────────────────

interface Agent {
  id: string
  name: string
  description: string
  llm_provider: string
  llm_model: string
  llm_temperature: number
  llm_max_tokens: number
  tts_provider: string
  tts_voice_id: string
  tts_speed: number
  stt_provider: string
  stt_model: string
  stt_language: string
  system_prompt: string
  first_message: string
  is_active: boolean
  interrupt_enabled: boolean
  interrupt_sensitivity: number
  silence_timeout: number
  max_call_duration: number
  background_noise_reduction: boolean
  sentiment_analysis_enabled: boolean
  created_at: string
  updated_at: string
}

interface Message {
  id: string
  role: 'user' | 'agent'
  text: string
  timestamp: Date
}

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

type CallState = 'idle' | 'starting' | 'listening' | 'processing' | 'speaking' | 'ended'
type SttMode  = 'none' | 'deepgram' | 'webspeech'
declare global { interface Window { SpeechRecognition: any; webkitSpeechRecognition: any } }

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Helpers ──────────────────────────────────────────────────────────────────

const providerColor: Record<string, string> = {
  openai:     'bg-emerald-50 text-emerald-700 border-emerald-200',
  anthropic:  'bg-violet-50 text-violet-700 border-violet-200',
  deepgram:   'bg-blue-50 text-blue-700 border-blue-200',
  elevenlabs: 'bg-amber-50 text-amber-700 border-amber-200',
  groq:       'bg-orange-50 text-orange-700 border-orange-200',
}

const formatDur = (s: number) => s >= 3600 ? `${Math.floor(s/3600)}h ${Math.floor((s%3600)/60)}m` : `${Math.floor(s/60)}m`
const formatTime = (s: number) => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`

const CALL_STATUS: Record<CallState, { label: string; dot: string; bar: string }> = {
  idle:       { label: 'Ready',       dot: 'bg-slate-400',   bar: '' },
  starting:   { label: 'Connecting', dot: 'bg-amber-400 animate-pulse',  bar: 'bg-amber-50' },
  listening:  { label: 'Listening',  dot: 'bg-emerald-500 animate-pulse', bar: 'bg-emerald-50' },
  processing: { label: 'Thinking',   dot: 'bg-blue-500 animate-pulse',    bar: 'bg-blue-50' },
  speaking:   { label: 'Speaking',   dot: 'bg-blue-500 animate-pulse',  bar: 'bg-blue-50' },
  ended:      { label: 'Call ended', dot: 'bg-slate-400',   bar: '' },
}

// ════════════════════════════════════════════════════════════════════════════
// Main Page
// ════════════════════════════════════════════════════════════════════════════

export default function AgentDetailPage() {
  const router   = useRouter()
  const params   = useParams()
  const agentId  = params.id as string

  const [agent,     setAgent]     = useState<Agent | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting,  setIsDeleting]  = useState(false)
  const [isToggling,  setIsToggling]  = useState(false)
  const [activeTab,   setActiveTab]   = useState<'overview'|'configuration'|'calls'>('overview')
  const [panelOpen,   setPanelOpen]   = useState(false)
  const [calls,       setCalls]       = useState<AgentCall[]>([])
  const [callsLoading, setCallsLoading] = useState(false)
  const [copied,      setCopied]      = useState(false)

  useEffect(() => { if (agentId) fetchAgent() }, [agentId])
  useEffect(() => { if (activeTab === 'calls' && agentId) fetchCalls() }, [activeTab, agentId])

  const fetchCalls = async () => {
    setCallsLoading(true)
    try {
      const r = await apiClient.get<{ calls: AgentCall[]; total: number }>(
        `${API_ENDPOINTS.CALLS}?agent_id=${agentId}&limit=50`
      )
      setCalls(r.data.calls || [])
    } catch {}
    finally { setCallsLoading(false) }
  }

  const copyAgentId = () => {
    if (!agent) return
    navigator.clipboard.writeText(agent.id).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const fetchAgent = async () => {
    try {
      const r = await apiClient.get<Agent>(API_ENDPOINTS.AGENT(agentId))
      setAgent(r.data)
    } catch (e) {
      toast.error(getErrorMessage(e))
      router.push('/dashboard/agents')
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggle = async () => {
    if (!agent) return
    setIsToggling(true)
    try {
      const r = await apiClient.patch<Agent>(API_ENDPOINTS.AGENT(agentId), { is_active: !agent.is_active })
      setAgent(r.data)
      toast.success(`Agent ${r.data.is_active ? 'activated' : 'deactivated'}`)
    } catch (e) { toast.error(getErrorMessage(e)) }
    finally { setIsToggling(false) }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this agent? This cannot be undone.')) return
    setIsDeleting(true)
    try {
      await apiClient.delete(API_ENDPOINTS.AGENT(agentId))
      toast.success('Agent deleted')
      router.push('/dashboard/agents')
    } catch (e) { toast.error(getErrorMessage(e)); setIsDeleting(false) }
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (isLoading) return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-64 bg-slate-200 rounded-lg" />
      <div className="h-32 bg-slate-100 rounded-2xl" />
      <div className="grid gap-4 md:grid-cols-3">
        {[1,2,3].map(i => <div key={i} className="h-24 bg-slate-100 rounded-xl" />)}
      </div>
    </div>
  )

  if (!agent) return null

  const tabs = [
    { id: 'overview'       as const, label: 'Overview',      icon: Settings2 },
    { id: 'configuration'  as const, label: 'Configuration', icon: Sliders   },
    { id: 'calls'          as const, label: 'Call History',  icon: Phone     },
  ]

  return (
    <>
      <div className="space-y-0">
        {/* ── Breadcrumb ── */}
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-5">
          <Link href="/dashboard/agents" className="flex items-center gap-1 hover:text-slate-700 transition-colors">
            <ArrowLeft className="h-3.5 w-3.5" /> Agents
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-slate-900 font-medium truncate">{agent.name}</span>
        </div>

        {/* ── Hero card ── */}
        <div className="bg-white rounded-2xl border border-slate-200 px-6 py-5 shadow-sm mb-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            {/* Avatar + name */}
            <div className="flex items-center gap-4 flex-1 min-w-0">
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl gradient-primary shadow">
                <Bot className="h-6 w-6 text-white" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-xl font-bold text-slate-900 truncate">{agent.name}</h1>
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium border ${
                    agent.is_active
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-slate-100 text-slate-500 border-slate-200'
                  }`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${agent.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                    {agent.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <p className="text-sm text-slate-500 truncate mt-0.5">
                  {agent.description || 'No description'}
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
              {/* Test Call — primary CTA */}
              <button
                onClick={() => setPanelOpen(true)}
                className="flex items-center gap-2 rounded-xl gradient-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm"
              >
                <PhoneCall className="h-4 w-4" />
                Test Call
              </button>

              <Link href={`/dashboard/agents/${agentId}/edit`}>
                <button className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all">
                  <Pencil className="h-4 w-4" /> Edit
                </button>
              </Link>
              <button
                onClick={handleToggle}
                disabled={isToggling}
                className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all disabled:opacity-50"
              >
                {agent.is_active
                  ? <ToggleRight className="h-4 w-4 text-emerald-600" />
                  : <ToggleLeft  className="h-4 w-4" />}
                {isToggling ? 'Updating…' : agent.is_active ? 'Deactivate' : 'Activate'}
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex items-center gap-1.5 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-100 transition-all disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                {isDeleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>

          {/* Provider pills */}
          <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-slate-100">
            <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${providerColor[agent.llm_provider] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
              <Cpu className="h-3 w-3" /> {agent.llm_model}
            </span>
            <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${providerColor[agent.tts_provider] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
              <Volume2 className="h-3 w-3" /> {agent.tts_provider}
            </span>
            <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${providerColor[agent.stt_provider] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
              <Mic className="h-3 w-3" /> {agent.stt_provider}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
              <Clock className="h-3 w-3" /> Max {formatDur(agent.max_call_duration || 1800)}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
              <Calendar className="h-3 w-3" /> {new Date(agent.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>

        {/* ── Tab bar ── */}
        <div className="flex gap-0 border-b border-slate-200 bg-white rounded-t-xl mb-0 px-1">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        {/* ── Tab content ── */}
        <div className="bg-white rounded-b-xl border border-t-0 border-slate-200 p-6 shadow-sm">

          {/* OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="grid gap-6 lg:grid-cols-2">
              {/* System prompt */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Settings2 className="h-4 w-4 text-slate-400" />
                  <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">System Prompt</h3>
                </div>
                <div className="rounded-xl bg-slate-50 border border-slate-100 p-4 font-mono text-sm text-slate-700 whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {agent.system_prompt || <span className="text-slate-400 italic">Not configured</span>}
                </div>
              </div>

              {/* First message */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="h-4 w-4 text-slate-400" />
                  <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">First Message</h3>
                </div>
                <div className="rounded-xl bg-slate-50 border border-slate-100 p-4 font-mono text-sm text-slate-700 whitespace-pre-wrap">
                  {agent.first_message || <span className="text-slate-400 italic">Not configured</span>}
                </div>

                {/* Mini info */}
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {[
                    { label: 'Barge-in',        value: agent.interrupt_enabled ? 'Enabled' : 'Disabled', icon: Mic, copyable: false },
                    { label: 'Silence Timeout',  value: `${((agent.silence_timeout||3000)/1000).toFixed(1)}s`, icon: Clock, copyable: false },
                    { label: 'Last Updated',     value: new Date(agent.updated_at).toLocaleDateString(), icon: Calendar, copyable: false },
                  ].map(({ label, value, icon: Icon }) => (
                    <div key={label} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                      <div className="flex items-center gap-1.5 mb-1">
                        <Icon className="h-3.5 w-3.5 text-slate-400" />
                        <span className="text-xs text-slate-400">{label}</span>
                      </div>
                      <p className="text-sm font-semibold text-slate-800">{value}</p>
                    </div>
                  ))}
                  {/* Agent ID — copyable */}
                  <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Shield className="h-3.5 w-3.5 text-slate-400" />
                      <span className="text-xs text-slate-400">Agent ID</span>
                    </div>
                    <button
                      onClick={copyAgentId}
                      className="flex items-center gap-1.5 group w-full text-left"
                      title="Click to copy"
                    >
                      <p className="text-sm font-semibold text-slate-800 truncate font-mono">
                        {agent.id.split('-')[0]}…
                      </p>
                      {copied
                        ? <Check className="h-3.5 w-3.5 text-emerald-500 flex-shrink-0" />
                        : <Copy className="h-3.5 w-3.5 text-slate-300 group-hover:text-blue-500 flex-shrink-0 transition-colors" />
                      }
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* CONFIGURATION */}
          {activeTab === 'configuration' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">Read-only view of current configuration.</p>
                <Link href={`/dashboard/agents/${agentId}/edit`}>
                  <button className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100 transition-all">
                    <Pencil className="h-3.5 w-3.5" /> Edit Configuration
                  </button>
                </Link>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                {/* LLM */}
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50">
                      <Cpu className="h-4 w-4 text-blue-600" />
                    </div>
                    <span className="text-sm font-semibold text-slate-800">Language Model</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    {[
                      { k: 'Provider',     v: agent.llm_provider },
                      { k: 'Model',        v: agent.llm_model },
                      { k: 'Temperature',  v: String(agent.llm_temperature) },
                      { k: 'Max Tokens',   v: String(agent.llm_max_tokens) },
                    ].map(({ k, v }) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-slate-400">{k}</span>
                        <span className="font-medium text-slate-700 capitalize truncate max-w-[120px]">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Voice */}
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50">
                      <Volume2 className="h-4 w-4 text-amber-600" />
                    </div>
                    <span className="text-sm font-semibold text-slate-800">Voice (TTS)</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    {[
                      { k: 'Provider', v: agent.tts_provider },
                      { k: 'Voice ID', v: agent.tts_voice_id ? agent.tts_voice_id.slice(0,8) + '…' : 'Default' },
                      { k: 'Speed',    v: `${agent.tts_speed || 1}x` },
                    ].map(({ k, v }) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-slate-400">{k}</span>
                        <span className="font-medium text-slate-700 capitalize">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* STT */}
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50">
                      <Mic className="h-4 w-4 text-blue-600" />
                    </div>
                    <span className="text-sm font-semibold text-slate-800">Speech-to-Text</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    {[
                      { k: 'Provider', v: agent.stt_provider },
                      { k: 'Model',    v: agent.stt_model || 'nova-2' },
                      { k: 'Language', v: agent.stt_language || 'en' },
                    ].map(({ k, v }) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-slate-400">{k}</span>
                        <span className="font-medium text-slate-700 capitalize">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Conversation settings */}
              <div className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100">
                    <Sliders className="h-4 w-4 text-slate-600" />
                  </div>
                  <span className="text-sm font-semibold text-slate-800">Conversation Settings</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  {[
                    { k: 'Barge-in',         v: agent.interrupt_enabled ? 'Enabled' : 'Disabled' },
                    { k: 'Sensitivity',       v: agent.interrupt_sensitivity ?? 0.5 },
                    { k: 'Silence Timeout',   v: `${((agent.silence_timeout||3000)/1000).toFixed(1)}s` },
                    { k: 'Max Duration',      v: formatDur(agent.max_call_duration||1800) },
                    { k: 'Noise Reduction',   v: agent.background_noise_reduction ? 'On' : 'Off' },
                    { k: 'Sentiment Analysis', v: agent.sentiment_analysis_enabled ? 'On' : 'Off' },
                  ].map(({ k, v }) => (
                    <div key={k}>
                      <p className="text-xs text-slate-400 mb-0.5">{k}</p>
                      <p className="font-semibold text-slate-800">{v}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          {/* CALLS */}
          {activeTab === 'calls' && (
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

              {callsLoading ? (
                <div className="space-y-2">
                  {[1,2,3].map(i => (
                    <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />
                  ))}
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
                <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 overflow-hidden">
                  <div className="hidden md:grid grid-cols-[2rem_1fr_6rem_5rem_6rem_3rem] gap-3 px-4 py-2.5 bg-slate-50 text-xs font-semibold text-slate-400 uppercase tracking-wide">
                    <div />
                    <div>From / To</div>
                    <div>Status</div>
                    <div>Duration</div>
                    <div>When</div>
                    <div />
                  </div>
                  {calls.map(call => {
                    const statusColor: Record<string, string> = {
                      completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
                      failed:    'bg-red-50 text-red-700 border-red-200',
                      missed:    'bg-amber-50 text-amber-700 border-amber-200',
                      in_progress: 'bg-blue-50 text-blue-700 border-blue-200',
                      initiated: 'bg-slate-50 text-slate-600 border-slate-200',
                    }
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
                              : <PhoneOutgoing className="h-3.5 w-3.5 text-slate-400" />
                            }
                          </div>
                          <div>
                            <p className="text-sm font-medium text-slate-800">{call.from_number || '—'}</p>
                            <p className="text-xs text-slate-400">→ {call.to_number || '—'}</p>
                          </div>
                          <div className="flex items-center">
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${statusColor[call.status] || statusColor.initiated}`}>
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
          )}

        </div>
      </div>

      {/* ── Sliding Call Test Panel ── */}
      <CallTestPanel
        agent={agent}
        agentId={agentId}
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
      />
    </>
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Call Test Panel (Vapi-style right drawer)
// ════════════════════════════════════════════════════════════════════════════

function CallTestPanel({
  agent, agentId, open, onClose
}: {
  agent: Agent
  agentId: string
  open: boolean
  onClose: () => void
}) {
  const [callState, setCallState] = useState<CallState>('idle')
  const [messages,  setMessages]  = useState<Message[]>([])
  const [liveText,  setLiveText]  = useState('')
  const [agentText, setAgentText] = useState('')
  const [volume,    setVolume]    = useState(0)
  const [elapsed,   setElapsed]   = useState(0)
  const [textInput, setTextInput] = useState('')
  const [sttMode,   setSttMode]   = useState<SttMode>('none')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ── Core refs ──────────────────────────────────────────────────────────────
  const isActiveRef       = useRef(false)
  const isPlayingRef      = useRef(false)
  const callStateRef      = useRef<CallState>('idle')
  const historyRef        = useRef<{ role: string; text: string }[]>([])
  const interruptRef      = useRef(true)
  const endPhrasesRef     = useRef<string[]>([])
  const maxDurRef         = useRef(1800)
  const idleTimeoutRef    = useRef(8000)
  const streamRef         = useRef<MediaStream | null>(null)
  const audioQueueRef     = useRef<{ audio_base64: string; format: string }[]>([])
  const currentAudioRef   = useRef<HTMLAudioElement | null>(null)
  const abortCtrlRef      = useRef<AbortController | null>(null)
  const drainResolveRef   = useRef<(() => void) | null>(null)
  const drainGenRef       = useRef(0)
  const timerRef          = useRef<ReturnType<typeof setInterval> | null>(null)
  const animFrameRef      = useRef<number>(0)
  const analyserRef       = useRef<AnalyserNode | null>(null)
  const audioCtxRef       = useRef<AudioContext | null>(null)
  const idleTimerRef      = useRef<ReturnType<typeof setTimeout> | null>(null)
  const maxTimerRef       = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dgWsRef           = useRef<WebSocket | null>(null)
  const mediaRecRef       = useRef<MediaRecorder | null>(null)
  const dgAvailRef        = useRef(true)
  const recognitionRef    = useRef<any>(null)
  const intentStopRef     = useRef(false)
  const startSpeechRef    = useRef<() => void>(() => {})
  const startWebSpeechRef = useRef<() => void>(() => {})
  const startDgRef        = useRef<() => void>(() => {})
  const streamRespRef     = useRef<(t: string) => Promise<void>>(async () => {})
  const resetIdleRef      = useRef<() => void>(() => {})
  const endCallRef        = useRef<() => void>(() => {})

  useEffect(() => { callStateRef.current = callState }, [callState])

  // Sync agent settings on open
  useEffect(() => {
    if (open && agent) {
      interruptRef.current  = agent.interrupt_enabled ?? true
      endPhrasesRef.current = [] // agent.end_call_phrases || []
      maxDurRef.current     = agent.max_call_duration || 1800
      idleTimeoutRef.current = agent.silence_timeout || 8000
    }
    if (!open) stopAll()
  }, [open, agent])

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentText])

  // ── Helpers ────────────────────────────────────────────────────────────────
  const addMessage = (role: 'user' | 'agent', text: string) => {
    setMessages(prev => [...prev, { id: Date.now().toString(), role, text, timestamp: new Date() }])
    historyRef.current.push({ role, text })
  }


  const stopAll = () => {
    isActiveRef.current = false
    if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null }
    if (maxTimerRef.current)  { clearTimeout(maxTimerRef.current);  maxTimerRef.current = null }
    if (recognitionRef.current)  { try { recognitionRef.current.stop() } catch {} }
    if (dgWsRef.current)         { try { dgWsRef.current.close() } catch {}; dgWsRef.current = null }
    if (mediaRecRef.current)     { try { mediaRecRef.current.stop() } catch {}; mediaRecRef.current = null }
    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current = null }
    if (abortCtrlRef.current)    { abortCtrlRef.current.abort() }
    if (timerRef.current)        { clearInterval(timerRef.current); timerRef.current = null }
    cancelAnimationFrame(animFrameRef.current)
    if (streamRef.current)  { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null }
    if (audioCtxRef.current){ audioCtxRef.current.close().catch(() => {}); audioCtxRef.current = null }
    audioQueueRef.current = []
    isPlayingRef.current  = false
  }

  const startVolumeMonitor = (stream: MediaStream) => {
    const ctx    = new AudioContext()
    audioCtxRef.current = ctx
    const src    = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 256
    src.connect(analyser)
    analyserRef.current = analyser
    const tick = () => {
      if (!analyserRef.current) return
      const d = new Uint8Array(analyserRef.current.frequencyBinCount)
      analyserRef.current.getByteFrequencyData(d)
      setVolume(Math.min(100, Math.sqrt(d.reduce((a, b) => a + b * b, 0) / d.length) * 3))
      animFrameRef.current = requestAnimationFrame(tick)
    }
    animFrameRef.current = requestAnimationFrame(tick)
  }

  const stopAudioNow = useCallback(() => {
    if (drainResolveRef.current) { drainResolveRef.current(); drainResolveRef.current = null }
    drainGenRef.current++
    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current = null }
    audioQueueRef.current = []
    isPlayingRef.current  = false
  }, [])

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    if (idleTimeoutRef.current > 0 && isActiveRef.current) {
      idleTimerRef.current = setTimeout(() => {
        if (isActiveRef.current && callStateRef.current === 'listening') {
          streamRespRef.current('[The user has been silent. Briefly check in.]')
        }
      }, idleTimeoutRef.current)
    }
  }, [])
  useEffect(() => { resetIdleRef.current = resetIdleTimer }, [resetIdleTimer])

  const drainQueue = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return
    isPlayingRef.current = true
    const myGen = ++drainGenRef.current
    while (audioQueueRef.current.length > 0 && isActiveRef.current) {
      const item = audioQueueRef.current.shift()!
      try {
        const mime  = item.format === 'mp3' ? 'audio/mpeg' : `audio/${item.format}`
        const bytes = atob(item.audio_base64)
        const buf   = new Uint8Array(bytes.length)
        for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i)
        const url   = URL.createObjectURL(new Blob([buf], { type: mime }))
        const audio = new Audio(url)
        currentAudioRef.current = audio
        await new Promise<void>(resolve => {
          const done = () => { drainResolveRef.current = null; resolve() }
          drainResolveRef.current = done
          audio.onended = audio.onerror = audio.onabort = done
          audio.play().catch(done)
          setTimeout(done, 30000)
        })
      } catch {}
    }
    drainResolveRef.current = null
    isPlayingRef.current = false
    currentAudioRef.current = null
    if (myGen === drainGenRef.current && isActiveRef.current
        && callStateRef.current !== 'ended' && callStateRef.current !== 'processing') {
      setCallState('listening')
      callStateRef.current = 'listening'
      setTimeout(() => { if (isActiveRef.current) startSpeechRef.current() }, 150)
    }
  }, [])

  const endCall = useCallback(() => {
    stopAll()
    setCallState('ended')
    setLiveText('')
    setAgentText('')
    setSttMode('none')
  }, [])
  useEffect(() => { endCallRef.current = endCall }, [endCall])

  const streamResponse = useCallback(async (userText: string) => {
    if (!isActiveRef.current) return
    setCallState('processing')
    callStateRef.current = 'processing'
    setAgentText('')
    stopAudioNow()
    const token = localStorage.getItem('access_token') || ''
    try {
      const ctrl = new AbortController()
      abortCtrlRef.current = ctrl
      const res = await fetch(`${API_BASE}/api/v1/agents/${agentId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ message: userText, history: historyRef.current.slice(-10) }),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      setCallState('speaking')
      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let fullText = '', buffer = '', shouldEnd = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const ev = JSON.parse(raw)
            if (ev.type === 'sentence') {
              fullText += (fullText ? ' ' : '') + ev.text
              setAgentText(fullText)
              if (ev.audio_base64) {
                audioQueueRef.current.push({ audio_base64: ev.audio_base64, format: ev.audio_format || 'mp3' })
                drainQueue()
              }
            } else if (ev.type === 'done') {
              fullText  = ev.full_text || fullText
              shouldEnd = !!ev.end_call
            }
          } catch {}
        }
      }
      if (fullText.trim()) addMessage('agent', fullText.trim())
      setAgentText('')
      if (shouldEnd) {
        const check = setInterval(() => {
          if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
            clearInterval(check); setTimeout(() => endCallRef.current(), 800)
          }
        }, 200)
        setTimeout(() => { clearInterval(check); endCallRef.current() }, 8000)
        return
      }
      if (audioQueueRef.current.length === 0 && !isPlayingRef.current && isActiveRef.current) {
        setCallState('listening')
        callStateRef.current = 'listening'
        setTimeout(() => startSpeechRef.current(), 150)
      }
    } catch (e: any) {
      if (e?.name === 'AbortError') return
      toast.error(e?.message || 'Response failed')
      if (isActiveRef.current) { setCallState('listening'); callStateRef.current = 'listening'; setTimeout(() => startSpeechRef.current(), 150) }
    }
  }, [drainQueue, stopAudioNow, agentId])

  const startDeepgramSession = useCallback(() => {
    if (!isActiveRef.current) return
    if (dgWsRef.current?.readyState === WebSocket.OPEN) {
      setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current(); return
    }
    const token  = localStorage.getItem('access_token') || ''
    const wsBase = API_BASE.replace(/^http(s?)/, (_, s) => `ws${s}`)
    let ws: WebSocket
    try { ws = new WebSocket(`${wsBase}/api/v1/agents/${agentId}/stt?token=${encodeURIComponent(token)}`) }
    catch { dgAvailRef.current = false; setSttMode('webspeech'); startWebSpeechRef.current(); return }
    dgWsRef.current = ws
    ws.onmessage = (e) => {
      if (!isActiveRef.current) return
      try {
        const ev = JSON.parse(e.data)
        if (ev.type === 'ready') {
          if (!streamRef.current) return
          const mime = ['audio/webm;codecs=opus','audio/webm','audio/ogg'].find(m => MediaRecorder.isTypeSupported(m)) || ''
          try {
            const rec = new MediaRecorder(streamRef.current, mime ? { mimeType: mime } : {})
            mediaRecRef.current = rec
            rec.ondataavailable = ev2 => { if (ev2.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(ev2.data) }
            rec.start(100)
            setSttMode('deepgram'); setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current()
          } catch { ws.close(); dgAvailRef.current = false; setSttMode('webspeech'); startWebSpeechRef.current() }
        } else if (ev.type === 'transcript') {
          const { text, speech_final } = ev
          if (!text?.trim()) return
          resetIdleRef.current()
          setLiveText(text)
          const agentBusy = callStateRef.current === 'speaking' || callStateRef.current === 'processing'
          if (agentBusy && interruptRef.current) { stopAudioNow(); if (abortCtrlRef.current) { abortCtrlRef.current.abort(); abortCtrlRef.current = null }; setCallState('listening'); callStateRef.current = 'listening' }
          if (speech_final) {
            if (callStateRef.current === 'processing') return
            callStateRef.current = 'processing'
            if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
            setLiveText('')
            addMessage('user', text.trim())
            streamRespRef.current(text.trim())
          }
        } else if (ev.type === 'error') {
          // Deepgram unusable (bad/missing key). Don't retry it — onclose would loop forever.
          dgAvailRef.current = false
          setSttMode('webspeech')
          toast.error(`Speech-to-text unavailable: ${ev.message || 'unknown error'}`)
          ws.close()
        }
      } catch {}
    }
    ws.onerror  = () => { dgWsRef.current = null; dgAvailRef.current = false; setSttMode('webspeech'); if (isActiveRef.current) startWebSpeechRef.current() }
    ws.onclose  = () => {
      dgWsRef.current = null
      if (mediaRecRef.current) { try { mediaRecRef.current.stop() } catch {}; mediaRecRef.current = null }
      if (isActiveRef.current && callStateRef.current !== 'ended' && callStateRef.current !== 'idle') {
        if (dgAvailRef.current) setTimeout(() => { if (isActiveRef.current) startDgRef.current() }, 1000)
        else startWebSpeechRef.current()
      }
    }
  }, [agentId, stopAudioNow])

  const startWebSpeech = useCallback(() => {
    if (!isActiveRef.current) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      toast.error('Speech recognition unavailable — you can still type to test the agent.')
      // Leave the call usable in text-only mode; otherwise callState sticks and sendText is blocked.
      setSttMode('none'); setCallState('listening'); callStateRef.current = 'listening'
      return
    }
    const r = new SR()
    recognitionRef.current = r
    r.continuous = false; r.interimResults = true; r.lang = 'en-US'
    r.onstart = () => { setCallState('listening'); resetIdleRef.current() }
    r.onresult = (e: any) => {
      let interim = '', final = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) final += t; else interim += t
      }
      setLiveText(interim || final)
      if ((interim || final).trim()) resetIdleRef.current()
      const agentBusy = callStateRef.current === 'speaking' || callStateRef.current === 'processing'
      if (agentBusy && interruptRef.current && (interim || final).trim()) { stopAudioNow(); if (abortCtrlRef.current) { abortCtrlRef.current.abort(); abortCtrlRef.current = null }; setCallState('listening'); callStateRef.current = 'listening' }
      if (final.trim()) { intentStopRef.current = true; callStateRef.current = 'processing'; r.stop(); setLiveText(''); addMessage('user', final.trim()); streamRespRef.current(final.trim()) }
    }
    r.onerror = (e: any) => { if (e.error === 'no-speech' && isActiveRef.current && !intentStopRef.current) startWebSpeechRef.current() }
    r.onend   = () => { if (intentStopRef.current) { intentStopRef.current = false; return }; if (isActiveRef.current && callStateRef.current === 'listening') setTimeout(() => startSpeechRef.current(), 150) }
    try { r.start() } catch {}
  }, [stopAudioNow])

  const startListening = useCallback(() => {
    if (!isActiveRef.current) return
    if (dgWsRef.current?.readyState === WebSocket.OPEN) { setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current() }
    else if (dgAvailRef.current) startDgRef.current()
    else startWebSpeechRef.current()
  }, [])

  useEffect(() => { startSpeechRef.current     = startListening },      [startListening])
  useEffect(() => { startWebSpeechRef.current   = startWebSpeech },      [startWebSpeech])
  useEffect(() => { startDgRef.current          = startDeepgramSession }, [startDeepgramSession])
  useEffect(() => { streamRespRef.current       = streamResponse },       [streamResponse])

  const streamGreeting = async (text: string) => {
    try {
      const r = await apiClient.post<{ audio_base64: string; audio_format: string }>(
        `${API_ENDPOINTS.AGENT(agentId)}/speak`, { text }
      )
      const mime  = r.data.audio_format === 'mp3' ? 'audio/mpeg' : `audio/${r.data.audio_format}`
      const bytes = atob(r.data.audio_base64)
      const buf   = new Uint8Array(bytes.length)
      for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i)
      const audio = new Audio(URL.createObjectURL(new Blob([buf], { type: mime })))
      currentAudioRef.current = audio
      await audio.play()
      await new Promise<void>(r2 => { audio.onended = () => r2() })
    } catch {}
    if (isActiveRef.current) startDeepgramSession()
  }

  const startCall = async () => {
    setCallState('starting')
    setMessages([]); setAgentText(''); setLiveText(''); setElapsed(0); setSttMode('none')
    historyRef.current  = []
    isActiveRef.current = true
    dgAvailRef.current  = true
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      startVolumeMonitor(stream)
    } catch { toast.error('Microphone access denied.'); setCallState('idle'); return }
    timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000)
    if (maxDurRef.current > 0) {
      maxTimerRef.current = setTimeout(() => {
        if (isActiveRef.current) { toast.info('Max call duration reached.'); endCallRef.current() }
      }, maxDurRef.current * 1000)
    }
    if (agent.first_message) {
      setCallState('speaking')
      addMessage('agent', agent.first_message)
      await streamGreeting(agent.first_message)
    } else {
      startDeepgramSession()
    }
  }

  const sendText = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = textInput.trim()
    if (!text || callState === 'processing' || callState === 'speaking') return
    setTextInput('')
    stopAudioNow()
    addMessage('user', text)
    await streamResponse(text)
  }

  const isLive = callState !== 'idle' && callState !== 'ended'
  const st     = CALL_STATUS[callState]

  // Waveform bars driven by volume
  const bars = [0.4, 0.7, 1, 0.8, 0.5, 0.9, 0.6]

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black/30 backdrop-blur-sm transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />

      {/* Sliding panel */}
      <div className={`fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[480px] bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-out ${open ? 'translate-x-0' : 'translate-x-full'}`}>

        {/* Panel header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
              <PhoneCall className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">Live Test Call</p>
              <p className="text-xs text-slate-500">{agent.name}</p>
            </div>
          </div>
          <button onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
            <X className="h-4.5 w-4.5" />
          </button>
        </div>

        {/* Status bar */}
        <div className={`flex items-center justify-between px-5 py-2.5 border-b border-slate-100 flex-shrink-0 ${st.bar || 'bg-slate-50'}`}>
          <div className="flex items-center gap-2.5">
            {/* Waveform */}
            {isLive ? (
              <div className="flex items-end gap-0.5 h-4">
                {bars.map((h, i) => (
                  <div key={i}
                    className={`w-0.5 rounded-full transition-all duration-75 ${
                      callState === 'listening'  ? 'bg-emerald-500'
                      : callState === 'speaking' ? 'bg-blue-500'
                      : 'bg-slate-300'
                    }`}
                    style={{ height: `${Math.max(2, (volume / 100) * h * 16)}px` }}
                  />
                ))}
              </div>
            ) : <span className={`h-2 w-2 rounded-full ${st.dot}`} />}
            <span className="text-xs font-medium text-slate-700">{st.label}</span>
            {sttMode === 'deepgram' && isLive && (
              <span className="flex items-center gap-1 text-xs text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full font-medium">
                <Zap className="h-3 w-3" /> Deepgram
              </span>
            )}
          </div>
          {isLive && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-slate-500">{formatTime(elapsed)}</span>
              <span className="flex items-center gap-1 text-xs font-semibold text-red-600">
                <Radio className="h-3 w-3" /> LIVE
              </span>
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
          {messages.length === 0 && !isLive && (
            <div className="flex flex-col items-center justify-center h-full text-center text-slate-400 gap-4 py-8">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100">
                <PhoneCall className="h-8 w-8 text-slate-300" />
              </div>
              <div>
                <p className="font-semibold text-slate-600 text-base">Ready to test</p>
                <p className="text-sm mt-1 text-slate-400 max-w-xs">
                  Start a live call to test your agent with real voice or text input.
                </p>
              </div>
              <div className="flex flex-col gap-1.5 text-xs text-slate-400 bg-slate-50 rounded-xl p-3 w-full text-left">
                <div className="flex items-center gap-2"><Mic     className="h-3 w-3" /> Deepgram real-time STT</div>
                <div className="flex items-center gap-2"><Volume2 className="h-3 w-3" /> ElevenLabs TTS</div>
                <div className="flex items-center gap-2"><Wifi    className="h-3 w-3" /> Barge-in interruption</div>
              </div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'agent' && (
                <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 mr-2 mt-1">
                  <Bot className="h-3.5 w-3.5 text-blue-600" />
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : 'bg-slate-100 text-slate-800 rounded-bl-sm'
              }`}>
                <p className="text-sm leading-relaxed">{msg.text}</p>
                <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-200' : 'text-slate-400'}`}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))}

          {/* Live transcript bubble */}
          {liveText && (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-sm px-3.5 py-2.5 bg-blue-100 border border-blue-200">
                <p className="text-sm italic text-blue-700">{liveText}</p>
              </div>
            </div>
          )}

          {/* Agent streaming bubble */}
          {agentText && (
            <div className="flex justify-start items-start gap-2">
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100">
                <Bot className="h-3.5 w-3.5 text-blue-600" />
              </div>
              <div className="max-w-[80%] rounded-2xl rounded-bl-sm px-3.5 py-2.5 bg-slate-100">
                <p className="text-sm leading-relaxed text-slate-800">{agentText}</p>
                <div className="flex gap-0.5 mt-1.5">
                  {[0,150,300].map(d => <div key={d} className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay:`${d}ms` }} />)}
                </div>
              </div>
            </div>
          )}

          {callState === 'processing' && !agentText && (
            <div className="flex justify-start items-start gap-2">
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100">
                <Bot className="h-3.5 w-3.5 text-blue-600" />
              </div>
              <div className="rounded-2xl rounded-bl-sm px-4 py-3 bg-slate-100">
                <div className="flex gap-1">
                  {[0,150,300].map(d => <div key={d} className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay:`${d}ms` }} />)}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Stats strip (during call) */}
        {isLive && (
          <div className="flex items-center gap-4 px-5 py-2 border-t border-slate-100 bg-slate-50 text-xs text-slate-500 flex-shrink-0">
            <span>{messages.filter(m => m.role==='user').length} user turn{messages.filter(m=>m.role==='user').length!==1?'s':''}</span>
            <span>{messages.filter(m => m.role==='agent').length} agent turn{messages.filter(m=>m.role==='agent').length!==1?'s':''}</span>
            <span className="ml-auto font-mono">{formatTime(elapsed)}</span>
          </div>
        )}

        {/* Input + controls */}
        <div className="border-t border-slate-200 p-4 flex-shrink-0">
          {!isLive ? (
            <button
              onClick={startCall}
              className="flex w-full items-center justify-center gap-2 rounded-xl gradient-primary py-3 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm"
            >
              <Phone className="h-4 w-4" />
              {callState === 'ended' ? 'Start New Call' : 'Start Call'}
            </button>
          ) : (
            <div className="space-y-2.5">
              <form onSubmit={sendText} className="flex gap-2">
                <input
                  value={textInput}
                  onChange={e => setTextInput(e.target.value)}
                  placeholder={callState === 'listening' ? 'Speaking or type a message…' : 'Type a message…'}
                  disabled={callState === 'processing'}
                  className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-sm text-slate-800 placeholder:text-slate-400 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50 transition-all"
                />
                <button
                  type="submit"
                  disabled={!textInput.trim() || callState === 'processing'}
                  className="flex items-center justify-center h-10 w-10 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-all flex-shrink-0"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
              <button
                onClick={endCall}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-100 transition-all"
              >
                <PhoneOff className="h-4 w-4" /> End Call
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
