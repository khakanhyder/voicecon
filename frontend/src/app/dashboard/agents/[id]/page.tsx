'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Search, Wrench, Plus, Loader2, Trash2, MessageSquare, Database, Globe, Settings2, Sheet, Calendar, PhoneForwarded, PhoneOff, Hash, ArrowLeftRight, Voicemail, Workflow, X, PhoneCall, ToggleLeft, ToggleRight, Link2, Puzzle, Users } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import {
  AgentTabBar, AgentTabContent, AgentTabId, AGENT_TABS, AgentIdentityFields,
  AgentFormState, DEFAULT_FORM,
  STT_MODELS, STT_PROVIDERS,
  LLM_MODELS, LLM_PROVIDERS,
  TTS_VOICES, TTS_PROVIDERS,
} from '@/components/agents/AgentForm'
import { AgentWidgetTab } from '@/components/agents/AgentWidgetTab'
import { AssistantsRail } from '@/components/agents/AssistantsRail'
import { AgentCallsTab } from '@/components/agents/AgentCallsTab'
import { CallTestPanel, TestCallAgent } from '@/components/agents/CallTestPanel'

import { useConfirm } from '@/hooks/use-confirm'

// ── Tool types (mirrors tools page) ─────────────────────────────────────────

const TOOL_TYPE_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; category: string; color: string; bg: string }> = {
  workflow:             { label: 'Workflow',             icon: Workflow,       category: 'assistant',    color: 'text-indigo-600',  bg: 'bg-indigo-50' },
  transfer_call:        { label: 'Transfer Call',        icon: PhoneForwarded, category: 'phone_call',   color: 'text-emerald-600', bg: 'bg-emerald-50' },
  hang_up:              { label: 'Hang Up',              icon: PhoneOff,       category: 'phone_call',   color: 'text-emerald-600', bg: 'bg-emerald-50' },
  leave_voicemail:      { label: 'Leave Voicemail',      icon: Voicemail,      category: 'phone_call',   color: 'text-emerald-600', bg: 'bg-emerald-50' },
  dtmf:                 { label: 'DTMF',                 icon: Hash,           category: 'phone_call',   color: 'text-emerald-600', bg: 'bg-emerald-50' },
  send_sms:             { label: 'Send Text',            icon: MessageSquare,  category: 'phone_call',   color: 'text-emerald-600', bg: 'bg-emerald-50' },
  sip_request:          { label: 'SIP Request',          icon: ArrowLeftRight, category: 'phone_call',   color: 'text-emerald-600', bg: 'bg-emerald-50' },
  handoff:              { label: 'Handoff',              icon: ArrowLeftRight, category: 'assistant',    color: 'text-violet-600',  bg: 'bg-violet-50' },
  query_knowledge_base: { label: 'Query Knowledge Base', icon: Database,       category: 'assistant',    color: 'text-violet-600',  bg: 'bg-violet-50' },
  api_request:          { label: 'API Request',          icon: Globe,          category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
  mcp:                  { label: 'MCP',                  icon: Settings2,      category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
  slack:                { label: 'Slack',                icon: MessageSquare,  category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
  google_sheets:        { label: 'Google Sheets',        icon: Sheet,          category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
  google_calendar:      { label: 'Google Calendar',      icon: Calendar,       category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
  // These three were missing, so a tool of any of these types rendered with a
  // generic spanner and its raw slug ("connected_integration") as its label —
  // on the one screen where you pick which tools an agent may call.
  connected_integration: { label: 'Connected Integration', icon: Link2,        category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
  gohighlevel:          { label: 'GoHighLevel',           icon: Users,         category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
  custom_tool:          { label: 'Custom Tool',           icon: Puzzle,        category: 'integration',  color: 'text-blue-600',    bg: 'bg-blue-50' },
}

interface Tool { id: string; name: string; description: string | null; tool_type: string; category: string; is_active: boolean }
interface Assignment { id: string; agent_id: string; tool_id: string; tool: Tool; created_at: string }

// ── Create-tool form (workflow-backed is the primary path) ───────────────────

interface WorkflowOption { id: string; name: string }

/**
 * Create a tool from inside the agent, satisfying the requirement that users
 * build tools without leaving the agent. The workflow-backed tool is the
 * default and recommended path: agent → tool → workflow → apps.
 */
function CreateToolForm({
  onCreated,
  onCancel,
}: {
  onCreated: (tool: Tool) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [workflowId, setWorkflowId] = useState('')
  const [filler, setFiller] = useState('One moment while I take care of that.')
  const [workflows, setWorkflows] = useState<WorkflowOption[]>([])
  const [loadingWorkflows, setLoadingWorkflows] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiClient
      .get<{ workflows: WorkflowOption[] }>(API_ENDPOINTS.WORKFLOWS)
      .then((res) => setWorkflows(res.data.workflows || []))
      .catch(() => setWorkflows([]))
      .finally(() => setLoadingWorkflows(false))
  }, [])

  const canSave = name.trim() && description.trim() && workflowId && !saving

  const submit = async () => {
    if (!canSave) return
    setSaving(true)
    try {
      const res = await apiClient.post<Tool>(API_ENDPOINTS.TOOLS, {
        name: name.trim(),
        description: description.trim(),
        tool_type: 'workflow',
        config: { workflow_id: workflowId, filler_message: filler.trim() || undefined },
        is_active: true,
      })
      await onCreated(res.data)
      toast.success('Tool created and added to this agent')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-indigo-600" />
          <h4 className="text-sm font-semibold text-slate-800">New workflow tool</h4>
        </div>
        <button onClick={onCancel} className="rounded-md p-1 text-slate-400 hover:bg-white hover:text-slate-600">
          <X className="h-4 w-4" />
        </button>
      </div>

      <p className="text-xs text-slate-500">
        The agent calls this tool, which runs the workflow you pick. The workflow
        is what talks to your connected apps.
      </p>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-slate-600">Tool name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="book_appointment"
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-slate-600">
          When should the agent use it?
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          placeholder="Books an appointment for the caller. Use whenever they want to schedule, book, or reserve a time."
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
        />
        <p className="text-[11px] text-slate-400">
          The agent decides when to call the tool from this description — write it
          as the situations it covers.
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-slate-600">Runs this workflow</label>
        <select
          value={workflowId}
          onChange={(e) => setWorkflowId(e.target.value)}
          disabled={loadingWorkflows}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
        >
          <option value="">
            {loadingWorkflows ? 'Loading workflows…' : 'Select a workflow…'}
          </option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
        {!loadingWorkflows && workflows.length === 0 && (
          <p className="text-[11px] text-slate-400">
            No workflows yet.{' '}
            <Link href="/dashboard/workflows" className="underline">Create one</Link>{' '}
            first, then link it here.
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-slate-600">
          Holding line while it runs
        </label>
        <input
          value={filler}
          onChange={(e) => setFiller(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
        />
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-white">
          Cancel
        </button>
        <button
          onClick={submit}
          disabled={!canSave}
          className="flex items-center gap-1.5 rounded-lg gradient-primary px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          Create &amp; add
        </button>
      </div>
    </div>
  )
}

// ── Agent Knowledge Tab ──────────────────────────────────────────────────────

interface KnowledgeBaseOption {
  id: string
  name: string
  description: string | null
  document_count: number
}

function AgentKnowledgeTab({ agentId }: { agentId: string }) {
  const [available, setAvailable] = useState<KnowledgeBaseOption[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!agentId) return
    Promise.all([
      apiClient.get<KnowledgeBaseOption[]>(API_ENDPOINTS.KNOWLEDGE_BASES),
      apiClient.get<{ knowledge_base_id: string }[]>(API_ENDPOINTS.AGENT_KNOWLEDGE_BASES(agentId)),
    ])
      .then(([all, attached]) => {
        setAvailable(all.data || [])
        setSelected((attached.data || []).map((a) => a.knowledge_base_id))
      })
      .catch((e) => toast.error(getErrorMessage(e)))
      .finally(() => setLoading(false))
  }, [agentId])

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const save = async () => {
    setSaving(true)
    try {
      await apiClient.put(API_ENDPOINTS.AGENT_KNOWLEDGE_BASES(agentId), {
        knowledge_base_ids: selected,
        max_results: 3,
        min_similarity: 0.2,
        auto_inject: true,
      })
      toast.success(
        selected.length
          ? `Agent will answer from ${selected.length} knowledge base(s)`
          : 'Knowledge bases detached'
      )
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading knowledge bases...</p>

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold">Knowledge bases</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Attach a knowledge base and this agent looks up relevant passages on every caller
          question, answering from your documents instead of guessing.
        </p>
      </div>

      {available.length === 0 ? (
        <div className="rounded-md border p-6 text-center">
          <p className="text-sm text-muted-foreground mb-3">
            You haven&apos;t created a knowledge base yet.
          </p>
          <Link href="/dashboard/knowledge/new">
            <Button variant="outline" size="sm">Create one</Button>
          </Link>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {available.map((kb) => (
              <label
                key={kb.id}
                className="flex items-start gap-3 rounded-md border p-3 cursor-pointer hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={selected.includes(kb.id)}
                  onChange={() => toggle(kb.id)}
                />
                <div className="min-w-0">
                  <p className="font-medium">{kb.name}</p>
                  {kb.description && (
                    <p className="text-sm text-muted-foreground">{kb.description}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {kb.document_count} document(s)
                  </p>
                </div>
              </label>
            ))}
          </div>

          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save knowledge bases'}
          </Button>
        </>
      )}
    </div>
  )
}

// ── Agent Tools Tab ──────────────────────────────────────────────────────────

function AgentToolsTab({ agentId }: { agentId: string }) {
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [allTools, setAllTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [assigning, setAssigning] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    Promise.allSettled([
      apiClient.get<Assignment[]>(API_ENDPOINTS.AGENT_TOOLS(agentId)),
      apiClient.get<{ tools: Tool[]; total: number }>(API_ENDPOINTS.TOOLS),
    ]).then(([assignRes, toolsRes]) => {
      if (assignRes.status === 'fulfilled') {
        setAssignments(Array.isArray(assignRes.value.data) ? assignRes.value.data : [])
      }
      if (toolsRes.status === 'fulfilled') {
        setAllTools(toolsRes.value.data.tools || [])
      }
    }).finally(() => setLoading(false))
  }, [agentId])

  // Create a tool from within the agent, then attach it in one step.
  const handleCreated = async (tool: Tool) => {
    setAllTools((prev) => [tool, ...prev])
    const res = await apiClient.post<Assignment>(
      API_ENDPOINTS.AGENT_TOOL(agentId, tool.id),
      {}
    )
    setAssignments((prev) => [...prev, res.data])
    setCreating(false)
  }

  const assignedIds = new Set(assignments.map(a => a.tool_id))
  const unassigned = allTools.filter(t => !assignedIds.has(t.id) && t.is_active)

  const assign = async (toolId: string) => {
    setAssigning(toolId)
    try {
      const res = await apiClient.post<Assignment>(API_ENDPOINTS.AGENT_TOOL(agentId, toolId), {})
      setAssignments(prev => [...prev, res.data])
      toast.success('Tool added to agent')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setAssigning(null)
    }
  }

  const unassign = async (toolId: string) => {
    setAssigning(toolId)
    try {
      await apiClient.delete(API_ENDPOINTS.AGENT_TOOL(agentId, toolId))
      setAssignments(prev => prev.filter(a => a.tool_id !== toolId))
      toast.success('Tool removed from agent')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setAssigning(null)
    }
  }

  if (loading) return (
    <div className="space-y-3">
      {[1,2,3].map(i => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}
    </div>
  )

  return (
    <div className="space-y-5">
      {/* Create a tool without leaving the agent */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-slate-700">Tools</h3>
          <p className="text-xs text-slate-400">
            Tools let this agent trigger workflows and actions during a conversation.
          </p>
        </div>
        {!creating && (
          <button
            onClick={() => setCreating(true)}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg gradient-primary px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 sm:w-auto"
          >
            <Plus className="h-3.5 w-3.5" />
            New tool
          </button>
        )}
      </div>

      {creating && (
        <CreateToolForm onCreated={handleCreated} onCancel={() => setCreating(false)} />
      )}

      {/* Assigned tools */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">
          Assigned Tools
          {assignments.length > 0 && <span className="ml-2 rounded-full bg-blue-100 text-blue-700 text-xs px-2 py-0.5">{assignments.length}</span>}
        </h3>
        {assignments.length === 0 ? (
          <div className="rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 py-8 text-center">
            <Wrench className="h-8 w-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">No tools assigned yet</p>
            <p className="text-xs text-slate-400 mt-1">Add tools from below to give this agent capabilities</p>
          </div>
        ) : (
          <div className="space-y-2">
            {assignments.map(a => {
              const meta = TOOL_TYPE_META[a.tool.tool_type]
              const Icon = meta?.icon || Wrench
              return (
                <div key={a.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${meta?.bg || 'bg-slate-50'}`}>
                    <Icon className={`h-4 w-4 ${meta?.color || 'text-slate-500'}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{a.tool.name}</p>
                    <p className="text-xs text-slate-400">{meta?.label || a.tool.tool_type}</p>
                  </div>
                  <button
                    onClick={() => unassign(a.tool_id)}
                    disabled={assigning === a.tool_id}
                    className="flex flex-shrink-0 items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 transition-all disabled:opacity-50"
                  >
                    {assigning === a.tool_id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    Remove
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Available tools */}
      {unassigned.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Available Tools</h3>
          <div className="space-y-2">
            {unassigned.map(t => {
              const meta = TOOL_TYPE_META[t.tool_type]
              const Icon = meta?.icon || Wrench
              return (
                <div key={t.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${meta?.bg || 'bg-slate-100'}`}>
                    <Icon className={`h-4 w-4 ${meta?.color || 'text-slate-500'}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{t.name}</p>
                    <p className="text-xs text-slate-400">{meta?.label || t.tool_type}</p>
                  </div>
                  <button
                    onClick={() => assign(t.id)}
                    disabled={assigning === t.id}
                    className="flex flex-shrink-0 items-center gap-1 rounded-lg gradient-primary px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 transition-all disabled:opacity-50"
                  >
                    {assigning === t.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    Add
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {allTools.length === 0 && !creating && (
        <div className="rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm text-indigo-700">
          No tools yet. Click{' '}
          <button onClick={() => setCreating(true)} className="font-semibold underline hover:text-indigo-800">
            New tool
          </button>{' '}
          to create one and connect it to a workflow.
        </div>
      )}
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

const FORM_TABS: AgentTabId[] = ['basic', 'llm', 'stt', 'voice', 'conversation', 'advanced']

export default function AgentDetailPage() {
  const { confirm, ConfirmDialog } = useConfirm()
  const router  = useRouter()
  const params  = useParams()
  const agentId = params.id as string

  const [tab,      setTab]      = useState<AgentTabId>('basic')
  const [loading,  setLoading]  = useState(false)
  const [fetching, setFetching] = useState(true)
  const [search,   setSearch]   = useState('')
  const [form,     setForm]     = useState<AgentFormState>(DEFAULT_FORM)

  // Agent-level actions (activate / delete / test call) live beside the editor
  // now that this page is the only agent detail page.
  const [isActive,   setIsActive]   = useState(true)
  const [isToggling, setIsToggling] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [panelOpen,  setPanelOpen]  = useState(false)

  const set = (key: keyof AgentFormState, value: any) =>
    setForm(f => ({ ...f, [key]: value }))

  // Knowledge bases live on their own endpoint — load them alongside the agent
  // so the "Files" picker in the Model card starts in sync.
  useEffect(() => {
    if (!agentId) return
    apiClient.get<{ knowledge_base_id: string }[]>(API_ENDPOINTS.AGENT_KNOWLEDGE_BASES(agentId))
      // `|| []` only covers null/undefined; any other non-array response reached
      // `.map` and crashed the edit page with an unhandled TypeError.
      .then(r => setForm(f => ({
        ...f,
        knowledge_base_ids: Array.isArray(r.data) ? r.data.map(k => k.knowledge_base_id) : [],
      })))
      .catch(() => {/* picker just starts empty */})
  }, [agentId])

  useEffect(() => {
    if (!agentId) return
    apiClient.get<any>(API_ENDPOINTS.AGENT(agentId))
      .then(r => {
        const a = r.data
        // Normalize STT provider — fall back to deepgram if stored value is unknown
        const sttProvider = STT_PROVIDERS.some(p => p.value === a.stt_provider)
          ? (a.stt_provider || 'deepgram') : 'deepgram'
        const sttModels = STT_MODELS[sttProvider] || STT_MODELS.deepgram
        const sttModelFallback = sttModels[0]?.value || 'nova-2'
        const sttModel = sttModels.some(m => m.value === a.stt_model)
          ? (a.stt_model || sttModelFallback) : sttModelFallback

        // Normalize LLM provider — fall back to openai if stored value is unknown
        const llmProvider = LLM_PROVIDERS.some(p => p.value === a.llm_provider)
          ? (a.llm_provider || 'openai') : 'openai'
        const llmModels = LLM_MODELS[llmProvider] || LLM_MODELS.openai
        const llmModelFallback = llmModels[0]?.value || 'gpt-5.4-nano'
        const llmModel = llmModels.some(m => m.value === a.llm_model)
          ? (a.llm_model || llmModelFallback) : llmModelFallback

        // Normalize TTS provider — fall back to elevenlabs if stored value is unknown
        const ttsProvider = TTS_PROVIDERS.some(p => p.value === a.tts_provider)
          ? (a.tts_provider || 'elevenlabs') : 'elevenlabs'
        const ttsVoices = TTS_VOICES[ttsProvider] || TTS_VOICES.elevenlabs
        const ttsVoiceFallback = ttsVoices[0]?.value || '21m00Tcm4TlvDq8ikWAM'
        const ttsVoiceId = ttsVoices.some(v => v.value === a.tts_voice_id)
          ? (a.tts_voice_id || ttsVoiceFallback) : ttsVoiceFallback

        setIsActive(a.is_active ?? true)

        // Merge, so a knowledge-base response that already landed is kept.
        setForm(prev => ({
          ...prev,
          name:              a.name            || '',
          description:       a.description     || '',
          system_prompt:     a.system_prompt   || '',
          first_message:     a.first_message   || '',
          llm_provider:      llmProvider,
          llm_model:         llmModel,
          llm_temperature:   Number(a.llm_temperature)  || 0.7,
          llm_max_tokens:    a.llm_max_tokens  || 1000,
          llm_custom_url:    a.llm_custom_url  || '',
          tts_provider:      ttsProvider,
          tts_voice_id:      ttsVoiceId,
          tts_speed:         Number(a.tts_speed) || 1.0,
          tts_pitch:         Number(a.tts_pitch) || 1.0,
          stt_provider:      sttProvider,
          stt_model:         sttModel,
          stt_language:      a.stt_language    || 'en',
          interrupt_enabled: a.interrupt_enabled ?? true,
          interrupt_sensitivity: Number(a.interrupt_sensitivity) || 0.5,
          silence_timeout:   a.silence_timeout || 3000,
          max_call_duration: a.max_call_duration || 1800,
          background_noise_reduction: a.background_noise_reduction ?? true,
          sentiment_analysis_enabled: a.sentiment_analysis_enabled ?? false,
          emotion_detection_enabled:  a.emotion_detection_enabled  ?? false,
        }))
      })
      .catch(() => { toast.error('Failed to load agent'); router.push('/dashboard/agents') })
      .finally(() => setFetching(false))
  }, [agentId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) { toast.error('Agent name is required'); setTab('basic'); return }
    setLoading(true)
    try {
      await apiClient.patch(API_ENDPOINTS.AGENT(agentId), {
        name: form.name, description: form.description,
        system_prompt: form.system_prompt, first_message: form.first_message,
        llm:      { provider: form.llm_provider, model: form.llm_model, temperature: form.llm_temperature, max_tokens: form.llm_max_tokens },
        voice:    { provider: form.tts_provider, voice_id: form.tts_voice_id, speed: form.tts_speed, pitch: form.tts_pitch },
        stt:      { provider: form.stt_provider, model: form.stt_model, language: form.stt_language },
        settings: { interrupt_enabled: form.interrupt_enabled, interrupt_sensitivity: form.interrupt_sensitivity, silence_timeout: form.silence_timeout, max_call_duration: form.max_call_duration },
        advanced: { background_noise_reduction: form.background_noise_reduction, sentiment_analysis_enabled: form.sentiment_analysis_enabled, emotion_detection_enabled: form.emotion_detection_enabled },
      })
      // "Files" writes to the same attachment endpoint the Knowledge tab uses.
      await apiClient.put(API_ENDPOINTS.AGENT_KNOWLEDGE_BASES(agentId), {
        knowledge_base_ids: form.knowledge_base_ids,
        max_results: 3, min_similarity: 0.2, auto_inject: true,
      })
      toast.success('Agent updated')
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = async () => {
    setIsToggling(true)
    try {
      const r = await apiClient.patch<{ is_active: boolean }>(API_ENDPOINTS.AGENT(agentId), { is_active: !isActive })
      setIsActive(r.data.is_active)
      toast.success(`Agent ${r.data.is_active ? 'activated' : 'deactivated'}`)
    } catch (e) { toast.error(getErrorMessage(e)) }
    finally { setIsToggling(false) }
  }

  const handleDelete = async () => {
    const ok = await confirm({
      title: 'Delete Agent',
      description: 'Delete this agent? This cannot be undone.',
      confirmText: 'Delete',
      isDestructive: true,
    })
    if (!ok) return
    setIsDeleting(true)
    try {
      await apiClient.delete(API_ENDPOINTS.AGENT(agentId))
      toast.success('Agent deleted')
      router.push('/dashboard/agents')
    } catch (e) { toast.error(getErrorMessage(e)); setIsDeleting(false) }
  }

  if (fetching) return (
    <div className="space-y-5 animate-pulse">
      <div className="h-8 w-56 bg-slate-200 rounded-xl" />
      <div className="h-10 w-full bg-slate-100 rounded-xl" />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(300px,400px)]">
        <div className="h-96 bg-slate-100 rounded-2xl" />
        <div className="h-72 bg-slate-100 rounded-2xl" />
      </div>
    </div>
  )

  const isToolsTab = tab === 'tools'
  const isWidgetTab = tab === 'widget'
  const isKnowledgeTab = tab === 'knowledge'
  const isCallsTab = tab === 'calls'
  const isCustomTab = isToolsTab || isWidgetTab || isKnowledgeTab || isCallsTab
  const formTabIndex = FORM_TABS.indexOf(tab as any)
  const activeLabel = AGENT_TABS.find(t => t.id === tab)?.label ?? ''

  const testCallAgent: TestCallAgent = {
    name:              form.name,
    first_message:     form.first_message,
    interrupt_enabled: form.interrupt_enabled,
    silence_timeout:   form.silence_timeout,
    max_call_duration: form.max_call_duration,
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <Link href="/dashboard/agents" className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold text-slate-900 leading-tight">Assistant</h1>
              <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${
                isActive
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-slate-100 text-slate-500 border-slate-200'
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                {isActive ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="truncate text-sm text-slate-500">{form.name || 'Loading…'}</p>
          </div>
        </div>

        {/* Agent actions */}
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center xl:flex-shrink-0">
          <button
            type="button"
            onClick={() => setPanelOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#0d5a4c] sm:w-auto"
          >
            <PhoneCall className="h-4 w-4" /> Test Call
          </button>
          <Link href={`/dashboard/agents/${agentId}/test`} className="w-full sm:w-auto">
            <button type="button" className="w-full rounded-xl border border-[#0F6A59] px-4 py-2.5 text-sm font-medium text-[#0F6A59] transition-colors hover:bg-[#0F6A59]/5">
              Talk to Assistant
            </button>
          </Link>
          <button
            type="button"
            onClick={handleToggle}
            disabled={isToggling}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 disabled:opacity-50 sm:w-auto"
          >
            {isActive
              ? <ToggleRight className="h-4 w-4 text-emerald-600" />
              : <ToggleLeft className="h-4 w-4" />}
            {isToggling ? 'Updating…' : isActive ? 'Deactivate' : 'Activate'}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 transition-all hover:bg-red-100 disabled:opacity-50 sm:w-auto"
          >
            <Trash2 className="h-4 w-4" />
            {isDeleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {/* Step row + search */}
      <div className="flex flex-col gap-3 border-b border-slate-200 pb-3 lg:flex-row lg:items-center lg:justify-between">
        <AgentTabBar activeTab={tab} onChange={setTab} />
        <div className="relative w-full lg:w-60 flex-shrink-0">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by user, roles"
            className="w-full rounded-full border border-slate-200 bg-white py-2.5 pl-9 pr-4 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-3 focus:ring-[#0F6A59]/15"
          />
        </div>
      </div>

      {/* Editor + rail */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(300px,400px)]">
        <div className="min-w-0 space-y-5">
          {isToolsTab ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
              <AgentToolsTab agentId={agentId} />
            </div>
          ) : isKnowledgeTab ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
              <AgentKnowledgeTab agentId={agentId} />
            </div>
          ) : isWidgetTab ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
              <AgentWidgetTab agentId={agentId} />
            </div>
          ) : isCallsTab ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
              <AgentCallsTab agentId={agentId} />
            </div>
          ) : (
            <form id="agent-edit-form" onSubmit={handleSubmit} className="space-y-5">
              <AgentTabContent tab={tab} form={form} set={set} />

              {/* Step controls */}
              <div className="flex items-center gap-2">
                {formTabIndex > 0 && (
                  <button type="button" onClick={() => setTab(FORM_TABS[formTabIndex - 1])}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-all">
                    Previous
                  </button>
                )}
                {formTabIndex > -1 && formTabIndex < FORM_TABS.length - 1 && !isCustomTab && (
                  <button type="button" onClick={() => setTab(FORM_TABS[formTabIndex + 1])}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-all">
                    Next
                  </button>
                )}
              </div>
            </form>
          )}
        </div>

        <aside className="min-w-0 space-y-4">
          {!isCustomTab && <AgentIdentityFields form={form} set={set} />}

          <button
            type="submit"
            form="agent-edit-form"
            disabled={loading || isCustomTab}
            className="w-full rounded-xl bg-[#0F6A59] px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#0d5a4c] disabled:opacity-60"
          >
            {loading ? 'Saving…' : 'Save Changes'}
          </button>
          <Link href="/dashboard/agents" className="block">
            <button type="button" className="w-full rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-600 transition-all hover:bg-slate-50">
              Cancel
            </button>
          </Link>
          {isCustomTab && (
            <p className="text-center text-xs text-slate-400">
              {isCallsTab ? 'Call history is read-only' : `${activeLabel} saves on its own`}
            </p>
          )}

          <AssistantsRail activeId={agentId} filter={search} />
        </aside>
      </div>

      {/* Live test call — same drawer the old agent view page used */}
      <CallTestPanel
        agent={testCallAgent}
        agentId={agentId}
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
      />
      <ConfirmDialog />
    </div>
  )
}
