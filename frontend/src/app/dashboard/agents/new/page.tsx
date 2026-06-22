'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Bot } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  AgentTabBar, AgentTabContent, AgentTabId,
  AgentFormState, DEFAULT_FORM,
} from '@/components/agents/AgentForm'

export default function NewAgentPage() {
  const router    = useRouter()
  const [tab,     setTab]     = useState<AgentTabId>('basic')
  const [loading, setLoading] = useState(false)
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
      toast.success('Agent created successfully')
      router.push(`/dashboard/agents/${res.data.id}`)
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/agents" className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl gradient-primary shadow">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Create Agent</h1>
            <p className="text-sm text-slate-500">Configure your AI voice agent</p>
          </div>
        </div>
      </div>

      {/* Form card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <AgentTabBar activeTab={tab} onChange={setTab} />
        <form onSubmit={handleSubmit}>
          <div className="p-5">
            <AgentTabContent tab={tab} form={form} set={set} />
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-5 py-4 border-t border-slate-100 bg-slate-50">
            <div className="flex gap-2">
              {/* Step prev/next */}
              {(['basic','llm','voice','stt','conversation','advanced'] as AgentTabId[]).indexOf(tab) > 0 && (
                <button type="button" onClick={() => {
                  const idx = (['basic','llm','voice','stt','conversation','advanced'] as AgentTabId[]).indexOf(tab)
                  setTab((['basic','llm','voice','stt','conversation','advanced'] as AgentTabId[])[idx - 1])
                }} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-all">
                  Previous
                </button>
              )}
              {tab !== 'advanced' && (
                <button type="button" onClick={() => {
                  const tabs: AgentTabId[] = ['basic','llm','voice','stt','conversation','advanced']
                  setTab(tabs[tabs.indexOf(tab) + 1])
                }} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-all">
                  Next
                </button>
              )}
            </div>
            <div className="flex gap-2">
              <Link href="/dashboard/agents">
                <button type="button" className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-all">
                  Cancel
                </button>
              </Link>
              <button
                type="submit"
                disabled={loading}
                className="flex items-center gap-2 rounded-lg gradient-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm disabled:opacity-60"
              >
                {loading ? 'Creating…' : 'Create Agent'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
