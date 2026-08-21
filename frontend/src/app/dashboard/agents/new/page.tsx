'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Search } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  AgentTabBar, AgentTabContent, AgentTabId, AgentIdentityFields,
  AgentFormState, DEFAULT_FORM, AGENT_TABS,
} from '@/components/agents/AgentForm'
import { AssistantsRail } from '@/components/agents/AssistantsRail'

// Tabs that hold create-time form fields. Tools, Knowledge and the Chat Widget
// attach to an agent that already exists, so they stay on the edit screen.
const FORM_TABS: AgentTabId[] = ['basic', 'llm', 'stt', 'voice', 'conversation', 'advanced']

export default function NewAgentPage() {
  const router    = useRouter()
  const [tab,     setTab]     = useState<AgentTabId>('basic')
  const [loading, setLoading] = useState(false)
  const [search,  setSearch]  = useState('')
  const [form,    setForm]    = useState<AgentFormState>(DEFAULT_FORM)

  const set = (key: keyof AgentFormState, value: any) =>
    setForm(f => ({ ...f, [key]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim())          { toast.error('Agent name is required'); setTab('basic'); return }
    if (!form.system_prompt.trim()) { toast.error('System prompt is required'); setTab('basic'); return }
    setLoading(true)
    try {
      const res = await apiClient.post<{ id: string }>(API_ENDPOINTS.AGENTS, {
        name: form.name, description: form.description,
        system_prompt: form.system_prompt, first_message: form.first_message,
        llm:      { provider: form.llm_provider, model: form.llm_model, temperature: form.llm_temperature, max_tokens: form.llm_max_tokens },
        voice:    { provider: form.tts_provider, voice_id: form.tts_voice_id, speed: form.tts_speed, pitch: form.tts_pitch },
        stt:      { provider: form.stt_provider, model: form.stt_model, language: form.stt_language },
        settings: { interrupt_enabled: form.interrupt_enabled, interrupt_sensitivity: form.interrupt_sensitivity, silence_timeout: form.silence_timeout, max_call_duration: form.max_call_duration },
        advanced: { background_noise_reduction: form.background_noise_reduction, sentiment_analysis_enabled: form.sentiment_analysis_enabled, emotion_detection_enabled: form.emotion_detection_enabled },
      })
      // Knowledge bases attach to an agent that already exists, so the "Files"
      // selection is applied right after creation.
      if (form.knowledge_base_ids.length) {
        try {
          await apiClient.put(API_ENDPOINTS.AGENT_KNOWLEDGE_BASES(res.data.id), {
            knowledge_base_ids: form.knowledge_base_ids,
            max_results: 3, min_similarity: 0.2, auto_inject: true,
          })
        } catch {
          toast.warning('Agent created, but the selected files could not be attached')
        }
      }
      toast.success('Agent created successfully')
      router.push(`/dashboard/agents/${res.data.id}`)
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const tabIndex = FORM_TABS.indexOf(tab)
  const activeLabel = AGENT_TABS.find(t => t.id === tab)?.label ?? ''

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/dashboard/agents" className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-xl font-semibold text-slate-900">Assistant</h1>
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
          {tabIndex === -1 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center">
              <p className="text-sm font-medium text-slate-700">{activeLabel} is configured after the assistant exists</p>
              <p className="mt-1 text-sm text-slate-400">Create the assistant first, then open it to set this up.</p>
            </div>
          ) : (
            <AgentTabContent tab={tab} form={form} set={set} />
          )}

          {/* Step controls */}
          <div className="flex items-center gap-2">
            {tabIndex > 0 && (
              <button type="button" onClick={() => setTab(FORM_TABS[tabIndex - 1])}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-all hover:bg-slate-50">
                Previous
              </button>
            )}
            {tabIndex > -1 && tabIndex < FORM_TABS.length - 1 && (
              <button type="button" onClick={() => setTab(FORM_TABS[tabIndex + 1])}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-all hover:bg-slate-50">
                Next
              </button>
            )}
          </div>
        </div>

        <aside className="min-w-0 space-y-4">
          <AgentIdentityFields form={form} set={set} />

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-[#0F6A59] px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#0d5a4c] disabled:opacity-60"
          >
            {loading ? 'Creating…' : 'Create Assistant'}
          </button>
          <Link href="/dashboard/agents" className="block">
            <button type="button" className="w-full rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-600 transition-all hover:bg-slate-50">
              Cancel
            </button>
          </Link>

          <AssistantsRail filter={search} />
        </aside>
      </div>
    </form>
  )
}
