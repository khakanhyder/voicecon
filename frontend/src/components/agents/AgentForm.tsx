'use client'

import { useEffect, useId, useRef, useState } from 'react'
import {
  FileText, Cpu, Volume2, Mic, MessageSquare, Settings, Wrench, BookOpen, ChevronUp, ChevronDown, Check, Phone,
} from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { VoiceSelection } from './VoiceSelection'

// ── LLM Providers & Models ────────────────────────────────────────────────────

export const LLM_PROVIDERS = [
  { value: 'openai',      label: 'OpenAI',         badge: 'Popular' },
  { value: 'anthropic',   label: 'Anthropic',      badge: 'Claude' },
]

export const LLM_MODELS: Record<string, { label: string; value: string; latency: string }[]> = {
  openai: [
    // ── GPT-5.5 series (latest flagship, Apr 2026) ──
    { value: 'gpt-5.5',             label: 'GPT-5.5',            latency: '~600ms · Latest flagship' },
    { value: 'gpt-5.5-pro',         label: 'GPT-5.5 Pro',        latency: '~900ms · Most powerful' },
    // ── GPT-5.4 series (Mar 2026) ──
    { value: 'gpt-5.4-nano',        label: 'GPT-5.4 Nano',       latency: '~180ms · Fastest GPT-5 · Best for voice' },
    { value: 'gpt-5.4-mini',        label: 'GPT-5.4 Mini',       latency: '~320ms · Fast GPT-5' },
    { value: 'gpt-5.4',             label: 'GPT-5.4',            latency: '~700ms · High quality' },
    { value: 'gpt-5.4-pro',         label: 'GPT-5.4 Pro',        latency: '~900ms · Premium' },
    // ── GPT-5.2 series (Dec 2025) ──
    { value: 'gpt-5.2',             label: 'GPT-5.2',            latency: '~650ms · Balanced' },
    { value: 'gpt-5.2-pro',         label: 'GPT-5.2 Pro',        latency: '~900ms · Premium' },
    // ── GPT-5.1 series (Nov 2025) ──
    { value: 'gpt-5.1',             label: 'GPT-5.1',            latency: '~600ms · Reliable' },
    // ── GPT-5 base (Aug 2025) ──
    { value: 'gpt-5',               label: 'GPT-5',              latency: '~700ms · Original GPT-5' },
    { value: 'gpt-5-mini',          label: 'GPT-5 Mini',         latency: '~350ms · Fast GPT-5' },
    { value: 'gpt-5-nano',          label: 'GPT-5 Nano',         latency: '~200ms · Lightweight GPT-5' },
    { value: 'gpt-5-pro',           label: 'GPT-5 Pro',          latency: '~950ms · Premium GPT-5' },
    // ── GPT-4.1 series (Apr 2025) ──
    { value: 'gpt-4.1-nano',        label: 'GPT-4.1 Nano',       latency: '~150ms · Ultra-fast' },
    { value: 'gpt-4.1-mini',        label: 'GPT-4.1 Mini',       latency: '~300ms · Fast' },
    { value: 'gpt-4.1',             label: 'GPT-4.1',            latency: '~700ms · 1M ctx' },
    // ── GPT-4o series ──
    { value: 'gpt-4o-mini',         label: 'GPT-4o Mini',        latency: '~350ms · Reliable' },
    { value: 'gpt-4o',              label: 'GPT-4o',             latency: '~800ms · Multimodal' },
    // ── Reasoning models (not ideal for voice due to latency) ──
    { value: 'o4-mini',             label: 'o4-mini',            latency: '~3s    · Fast reasoning' },
    { value: 'o3',                  label: 'o3',                 latency: '~8s    · Advanced reasoning' },
    { value: 'o3-mini',             label: 'o3-mini',            latency: '~4s    · Efficient reasoning' },
    { value: 'o1-pro',              label: 'o1-pro',             latency: '~15s   · Deep reasoning' },
    { value: 'o1',                  label: 'o1',                 latency: '~10s   · Reasoning' },
    { value: 'o1-mini',             label: 'o1-mini',            latency: '~4s    · Reasoning' },
    // ── Legacy ──
    { value: 'gpt-4',               label: 'GPT-4',              latency: '~1.5s  · Legacy' },
    { value: 'gpt-4-turbo',         label: 'GPT-4 Turbo',        latency: '~1.2s  · Legacy' },
    { value: 'gpt-4-turbo-preview', label: 'GPT-4 Turbo Preview',latency: '~1.2s  · Legacy' },
    { value: 'gpt-3.5-turbo',       label: 'GPT-3.5 Turbo',      latency: '~200ms · Legacy' },
    { value: 'gpt-3.5-turbo-16k',   label: 'GPT-3.5 Turbo 16k', latency: '~250ms · Legacy' },
  ],
  anthropic: [
    { value: 'claude-haiku-4-5-20251001',  label: 'Claude Haiku 4.5',    latency: '~400ms · Best for voice' },
    { value: 'claude-sonnet-4-6',          label: 'Claude Sonnet 4.6',   latency: '~800ms · Balanced' },
    { value: 'claude-opus-4-6',            label: 'Claude Opus 4.6',     latency: '~2s    · Most powerful' },
    { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet',   latency: '~900ms · Proven' },
    { value: 'claude-3-5-haiku-20241022',  label: 'Claude 3.5 Haiku',    latency: '~350ms · Fast' },
    { value: 'claude-3-haiku-20240307',    label: 'Claude 3 Haiku',      latency: '~350ms · Economic' },
  ],
}

// ── TTS Providers & Voices ────────────────────────────────────────────────────

export const TTS_PROVIDERS = [
  { value: 'elevenlabs',  label: 'ElevenLabs',  badge: 'Popular · Voice cloning' },
]

export const TTS_VOICES: Record<string, { value: string; label: string; gender: string; style: string }[]> = {
  elevenlabs: [
    { value: '21m00Tcm4TlvDq8ikWAM', label: 'Rachel',  gender: 'Female', style: 'Calm' },
    { value: 'AZnzlk1XvdvUeBnXmlld', label: 'Domi',    gender: 'Female', style: 'Strong' },
    { value: 'EXAVITQu4vr4xnSDxMaL', label: 'Bella',   gender: 'Female', style: 'Soft' },
    { value: 'ErXwobaYiN019PkySvjV',  label: 'Antoni',  gender: 'Male',   style: 'Well-rounded' },
    { value: 'MF3mGyEYCl7XYWbV9V6O', label: 'Elli',    gender: 'Female', style: 'Emotional' },
    { value: 'TxGEqnHWrfWFTfGW9XjX', label: 'Josh',    gender: 'Male',   style: 'Deep' },
    { value: 'VR6AewLTigWG4xSOukaG', label: 'Arnold',  gender: 'Male',   style: 'Crisp' },
    { value: 'pNInz6obpgDQGcFmaJgB', label: 'Adam',    gender: 'Male',   style: 'Narration' },
    { value: 'yoZ06aMxZJJ28mfd3POQ', label: 'Sam',     gender: 'Male',   style: 'Raspy' },
    { value: 'jBpfuIE2acCO8z3wKNLl', label: 'Gigi',    gender: 'Female', style: 'Childlike' },
    { value: 'jsCqWAovK2LkecY7zXl4', label: 'Freya',   gender: 'Female', style: 'Warm' },
    { value: 'onwK4e9ZLuTAKqWW03F9', label: 'Daniel',  gender: 'Male',   style: 'Deep · British' },
  ],
}

// Backward compat export
export const ELEVENLABS_VOICES = TTS_VOICES.elevenlabs

// ── STT Providers & Models ────────────────────────────────────────────────────

export const STT_PROVIDERS = [
  { value: 'deepgram',      label: 'Deepgram',       badge: 'Popular · Real-time' },
]

export const STT_MODELS: Record<string, { value: string; label: string; desc: string }[]> = {
  deepgram: [
    { value: 'nova-3',   label: 'Nova 3',   desc: 'Best accuracy' },
    { value: 'nova-2',   label: 'Nova 2',   desc: 'Recommended' },
    { value: 'nova',     label: 'Nova',     desc: 'Fast' },
    { value: 'enhanced', label: 'Enhanced', desc: 'Balanced' },
    { value: 'base',     label: 'Base',     desc: 'Lightweight' },
  ],
}

export const LANGUAGES = [
  { value: 'en',    label: 'English' },
  { value: 'en-US', label: 'English (US)' },
  { value: 'en-GB', label: 'English (UK)' },
  { value: 'en-AU', label: 'English (AU)' },
  { value: 'es',    label: 'Spanish' },
  { value: 'es-MX', label: 'Spanish (Mexico)' },
  { value: 'fr',    label: 'French' },
  { value: 'fr-CA', label: 'French (Canada)' },
  { value: 'de',    label: 'German' },
  { value: 'it',    label: 'Italian' },
  { value: 'pt',    label: 'Portuguese' },
  { value: 'pt-BR', label: 'Portuguese (Brazil)' },
  { value: 'nl',    label: 'Dutch' },
  { value: 'pl',    label: 'Polish' },
  { value: 'ja',    label: 'Japanese' },
  { value: 'ko',    label: 'Korean' },
  { value: 'zh',    label: 'Chinese (Mandarin)' },
  { value: 'zh-TW', label: 'Chinese (Traditional)' },
  { value: 'ar',    label: 'Arabic' },
  { value: 'hi',    label: 'Hindi' },
  { value: 'ru',    label: 'Russian' },
  { value: 'tr',    label: 'Turkish' },
  { value: 'sv',    label: 'Swedish' },
  { value: 'da',    label: 'Danish' },
  { value: 'fi',    label: 'Finnish' },
  { value: 'no',    label: 'Norwegian' },
]

// ── Tab config ─────────────────────────────────────────────────────────────────

export const AGENT_TABS = [
  { id: 'basic',        label: 'Prompt',         icon: FileText },
  { id: 'llm',          label: 'LLM Selection',  icon: Cpu },
  { id: 'stt',          label: 'Transcriber',    icon: Mic },
  { id: 'voice',        label: 'Voice Selection',icon: Volume2 },
  { id: 'tools',        label: 'Tools',          icon: Wrench },
  { id: 'conversation', label: 'Conversation',   icon: MessageSquare },
  { id: 'advanced',     label: 'Advanced',       icon: Settings },
  { id: 'knowledge',    label: 'Knowledge base', icon: BookOpen },
  { id: 'calls',        label: 'Call History',   icon: Phone },
] as const

export type AgentTabId = typeof AGENT_TABS[number]['id']

// ── Form state type ───────────────────────────────────────────────────────────

export interface AgentFormState {
  name: string
  description: string
  system_prompt: string
  first_message: string
  llm_provider: string
  llm_model: string
  llm_temperature: number
  llm_max_tokens: number
  llm_custom_url: string
  tts_provider: string
  tts_voice_id: string
  tts_speed: number
  tts_pitch: number
  stt_provider: string
  stt_model: string
  stt_language: string
  interrupt_enabled: boolean
  interrupt_sensitivity: number
  silence_timeout: number
  max_call_duration: number
  background_noise_reduction: boolean
  sentiment_analysis_enabled: boolean
  emotion_detection_enabled: boolean
  /** Knowledge bases the agent answers from — the "Files" picker. */
  knowledge_base_ids: string[]
}

export const DEFAULT_FORM: AgentFormState = {
  name: '', description: '', system_prompt: '',
  first_message: 'Hello! How can I help you today?',
  llm_provider: 'openai', llm_model: 'gpt-5.4-nano', llm_temperature: 0.7, llm_max_tokens: 1000, llm_custom_url: '',
  tts_provider: 'elevenlabs', tts_voice_id: '21m00Tcm4TlvDq8ikWAM', tts_speed: 1.0, tts_pitch: 1.0,
  stt_provider: 'deepgram', stt_model: 'nova-2', stt_language: 'en',
  interrupt_enabled: true, interrupt_sensitivity: 0.5,
  silence_timeout: 3000, max_call_duration: 1800,
  background_noise_reduction: true, sentiment_analysis_enabled: false, emotion_detection_enabled: false,
  knowledge_base_ids: [],
}

// ── UI helpers ────────────────────────────────────────────────────────────────

/**
 * Slider with the value shown in a bordered box to the right of the label,
 * matching the Temperature control in the design.
 */
function SliderField({ label, value, min, max, step, format, onChange, hints }: {
  label: string; value: number; min: number; max: number; step: number
  format?: (v: number) => string; onChange: (v: number) => void
  hints?: [string, string, string?]
}) {
  const id = useId()
  const display = format ? format(value) : String(value)
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor={id} className="text-[15px] font-semibold text-[#000000] font-poppins flex items-center gap-2">
          {label} <span aria-hidden="true" className="flex h-[14px] w-[14px] items-center justify-center rounded-full border border-slate-400 text-slate-500 text-[9px] font-bold leading-none">i</span>
        </Label>
        <span className="min-w-[50px] rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-center text-[13px] font-medium text-[#000000] font-poppins">
          {display}
        </span>
      </div>
      {/* The input fills the whole row, so the 2px track is only what is drawn:
          the area that takes a tap or a drag is as tall as the row. */}
      <div className="relative flex h-6 items-center max-sm:h-11">
        <div className="absolute w-full h-[2px] bg-slate-200 rounded-full" />
        <div className="absolute h-[2px] bg-[#106959] rounded-full" style={{ width: `${pct}%` }} />
        <input id={id} type="range" min={min} max={max} step={step} value={value}
          aria-valuetext={display}
          onChange={e => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value))}
          className="absolute inset-0 h-full w-full appearance-none cursor-pointer bg-transparent"
          style={{ WebkitAppearance: 'none' }}
        />
      </div>
      {hints && (
        <div className="flex justify-between text-xs text-slate-400">
          <span>{hints[0]}</span>{hints[2] && <span>{hints[2]}</span>}<span>{hints[1]}</span>
        </div>
      )}
    </div>
  )
}

function Toggle({ enabled, onChange, label }: { enabled: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    // The button is the tap area; the 36x20 track inside it is only the drawing.
    <button type="button" role="switch" aria-checked={enabled} aria-label={label} onClick={() => onChange(!enabled)}
      className="group inline-flex flex-shrink-0 items-center justify-center rounded-full focus:outline-none max-sm:min-w-[44px]">
      <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors group-focus-visible:ring-2 group-focus-visible:ring-[#0F6A59]/40 group-focus-visible:ring-offset-2 ${enabled ? 'bg-[#0F6A59]' : 'bg-slate-300'}`}>
        <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0.5'}`}/>
      </span>
    </button>
  )
}

/**
 * Collapsible white card with a title, sub-caption and chevron — the "Model"
 * panel in the design.
 */
function SectionCard({ title, subtitle, icon: Icon, children, hint }: {
  title: string; subtitle?: string; icon?: React.ElementType; hint?: string; children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden mt-4">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className="flex w-full items-start justify-between gap-3 px-4 pt-5 pb-4 text-left sm:px-6"
      >
        <div className="flex min-w-0 items-start gap-2.5">
          {Icon && <Icon className="mt-1 h-5 w-5 flex-shrink-0 text-[#0F6A59]" />}
          <div>
            <h2 className="text-[17px] font-bold text-[#000000] font-poppins leading-tight sm:text-[20px]">{title}</h2>
            {subtitle && <p className="mt-1 text-[12px] font-medium text-[#000000] font-poppins">{subtitle}</p>}
          </div>
        </div>
        <div className="flex flex-shrink-0 items-center gap-3">
          {hint && <span className="hidden text-xs text-slate-400 sm:inline">{hint}</span>}
          <ChevronUp className={`h-6 w-6 flex-shrink-0 text-[#106959] transition-transform ${open ? '' : 'rotate-180'}`} />
        </div>
      </button>
      {open && <div className="space-y-6 px-4 pb-6 sm:px-6">{children}</div>}
    </div>
  )
}

/**
 * "Files" picker from the design — selects which knowledge bases the agent
 * answers from. Multi-select, because an agent can hold several; the Knowledge
 * tab edits the same attachment list.
 */
function KnowledgeBaseSelect({ id, value, onChange }: { id?: string; value: string[]; onChange: (ids: string[]) => void }) {
  const [options, setOptions] = useState<{ id: string; name: string }[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    apiClient.get<{ id: string; name: string }[]>(API_ENDPOINTS.KNOWLEDGE_BASES)
      // `|| []` only guards null/undefined. Anything else non-array — an error
      // envelope, a gateway's HTML page — reached `options.filter` below and
      // took the whole agent form down with an unhandled TypeError.
      .then(r => setOptions(Array.isArray(r.data) ? r.data : []))
      .catch(() => setOptions([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const selectedNames = options.filter(o => value.includes(o.id)).map(o => o.name)
  const label = loading
    ? 'Loading…'
    : selectedNames.length === 0 ? 'Select File'
    : selectedNames.length === 1 ? selectedNames[0]
    : `${selectedNames.length} files selected`

  const toggle = (id: string) =>
    onChange(value.includes(id) ? value.filter(v => v !== id) : [...value, id])

  return (
    <div className="relative" ref={boxRef}>
      <button
        id={id}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
        className="flex h-[42px] w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-[14px] font-poppins text-[#000000] outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15"
      >
        <span className={selectedNames.length ? 'text-[#000000] font-medium' : 'text-slate-500 font-medium'}>{label}</span>
        <ChevronDown className="h-5 w-5 flex-shrink-0 text-[#106959]" />
      </button>

      {open && (
        <div role="listbox" aria-multiselectable="true" className="absolute z-30 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-slate-200 bg-white p-1 shadow-lg">
          {options.length === 0 ? (
            <p className="px-3 py-2.5 text-sm text-slate-400">No knowledge bases yet</p>
          ) : (
            options.map(o => (
              <button
                key={o.id}
                type="button"
                role="option"
                aria-selected={value.includes(o.id)}
                onClick={() => toggle(o.id)}
                className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              >
                <span className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border ${
                  value.includes(o.id) ? 'border-[#0F6A59] bg-[#0F6A59] text-white' : 'border-slate-300'
                }`}>
                  {value.includes(o.id) && <Check className="h-3 w-3" />}
                </span>
                <span className="truncate">{o.name}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Assistant name and description. These live in the side rail next to the
 * "Create Assistant" action, matching the design.
 */
export function AgentIdentityFields({ form, set }: {
  form: AgentFormState; set: (key: keyof AgentFormState, value: any) => void
}) {
  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="space-y-2">
        <Label htmlFor="agent-name" className="text-[14px] font-bold text-[#000000] font-poppins block">Assistant Name <span aria-hidden="true" className="text-red-500">*</span></Label>
        <Input
          id="agent-name"
          placeholder="e.g. Riley"
          value={form.name}
          onChange={e => set('name', e.target.value)}
          required
          className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-3 text-[14px]"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="agent-description" className="text-[14px] font-bold text-[#000000] font-poppins block mt-1">Description</Label>
        <Textarea
          id="agent-description"
          placeholder="What does this assistant do?"
          value={form.description}
          onChange={e => set('description', e.target.value)}
          rows={3}
          className="w-full rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-3 py-2 text-[14px]"
        />
      </div>
    </div>
  )
}

function ProviderBadge({ badge }: { badge: string }) {
  if (!badge) return null
  return <span className="ml-2 rounded bg-[#0F6A59]/10 px-1.5 py-0.5 text-xs font-medium text-[#0F6A59]">{badge}</span>
}

// ── Tab content ───────────────────────────────────────────────────────────────

export function AgentTabContent({ tab, form, set }: {
  tab: AgentTabId; form: AgentFormState; set: (key: keyof AgentFormState, value: any) => void
}) {

  if (tab === 'basic') {
    return (
      <div className="flex w-full flex-col">
        <SectionCard title="Model" subtitle="Configure the behaviour of the assistant">
          <div className="grid gap-x-6 gap-y-6 lg:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            {/* Left column */}
            <div className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="agent-first-message" className="text-[15px] font-bold text-[#000000] font-poppins block">First Message</Label>
                <Input
                  id="agent-first-message"
                  value={form.first_message} 
                  onChange={e => set('first_message', e.target.value)} 
                  placeholder="Thank you for calling Wellness Partners..."
                  className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-4 py-2"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="agent-system-prompt" className="text-[15px] font-bold text-[#000000] font-poppins block mt-4">System Prompt</Label>
                <Textarea
                  id="agent-system-prompt"
                  placeholder="You are a helpful voice assistant."
                  value={form.system_prompt} 
                  onChange={e => set('system_prompt', e.target.value)}
                  rows={13} required
                  className="w-full rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-4 py-3 leading-relaxed text-[13px]"
                />
              </div>
            </div>

            {/* Right column */}
            <div className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="agent-prompt-provider" className="text-[15px] font-bold text-[#000000] font-poppins block">Provider</Label>
                <Select value={form.llm_provider || 'openai'} onValueChange={v => { set('llm_provider', v); set('llm_model', (LLM_MODELS[v] || LLM_MODELS.openai)[0]?.value || 'gpt-5.4-nano') }}>
                  <SelectTrigger id="agent-prompt-provider" className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-4 font-medium"><SelectValue/></SelectTrigger>
                  <SelectContent>
                    {LLM_PROVIDERS.map(p => (
                      <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="agent-prompt-model" className="text-[15px] font-bold text-[#000000] font-poppins block">Model</Label>
                <Select value={form.llm_model || (LLM_MODELS[form.llm_provider] || [])[0]?.value || ''} onValueChange={v => set('llm_model', v)}>
                  <SelectTrigger id="agent-prompt-model" className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-4 font-medium"><SelectValue/></SelectTrigger>
                  <SelectContent>
                    {(LLM_MODELS[form.llm_provider] || []).map(m => (
                      <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="agent-files" className="text-[15px] font-bold text-[#000000] font-poppins block">Files</Label>
                <KnowledgeBaseSelect
                  id="agent-files"
                  value={form.knowledge_base_ids}
                  onChange={ids => set('knowledge_base_ids', ids)}
                />
              </div>

              <div className="pt-2">
                 <SliderField label="Temperature" value={form.llm_temperature} min={0} max={2} step={0.1}
                 format={v => v.toFixed(1)} onChange={v => set('llm_temperature', v)}/>
              </div>

              <div className="space-y-2 pt-2">
                <Label htmlFor="agent-max-tokens" className="text-[15px] font-bold text-[#000000] font-poppins flex items-center gap-2">
                  Max Token <span aria-hidden="true" className="flex h-[14px] w-[14px] items-center justify-center rounded-full border border-slate-400 text-slate-500 text-[9px] font-bold leading-none">i</span>
                </Label>
                <Input
                  id="agent-max-tokens"
                  type="number" min={100} max={4000} step={50}
                  value={form.llm_max_tokens}
                  onChange={e => set('llm_max_tokens', parseInt(e.target.value) || 0)}
                  className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-4 font-medium"
                />
              </div>
            </div>
          </div>
        </SectionCard>
      </div>
    )
  }

  if (tab === 'llm') return (
    <div className="flex w-full flex-col">
      <SectionCard title="LLM Selection" subtitle="Pick the model that powers the conversation" icon={Cpu} hint={`${LLM_PROVIDERS.length} providers`}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="agent-llm-provider" className="text-[14px] font-bold text-[#000000] font-poppins block">Provider</Label>
          <Select value={form.llm_provider || 'openai'} onValueChange={v => { set('llm_provider', v); set('llm_model', (LLM_MODELS[v] || LLM_MODELS.openai)[0]?.value || 'gpt-5.4-nano') }}>
            <SelectTrigger id="agent-llm-provider" className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
            <SelectContent>
              {LLM_PROVIDERS.map(p => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}{p.badge && <ProviderBadge badge={p.badge}/>}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="agent-llm-model" className="text-[14px] font-bold text-[#000000] font-poppins block">Model</Label>
          <Select value={form.llm_model || (LLM_MODELS[form.llm_provider] || [])[0]?.value || ''} onValueChange={v => set('llm_model', v)}>
            <SelectTrigger id="agent-llm-model" className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
            <SelectContent>
              {(LLM_MODELS[form.llm_provider] || []).map(m => (
                <SelectItem key={m.value} value={m.value}>
                  <div><span className="font-medium">{m.label}</span><span className="ml-2 text-xs text-slate-400">{m.latency}</span></div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {form.llm_provider === 'custom' && (
        <div className="space-y-2">
          <Label htmlFor="agent-llm-custom-url" className="text-[14px] font-bold text-[#000000] font-poppins block">Custom LLM Endpoint URL</Label>
          <Input id="agent-llm-custom-url" value={form.llm_custom_url} onChange={e => set('llm_custom_url', e.target.value)}
            placeholder="https://your-llm-server.com/v1" className="font-mono text-sm"/>
          <p className="text-xs text-slate-400">Must be OpenAI-compatible (chat completions endpoint)</p>
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        <SliderField label="Temperature" value={form.llm_temperature} min={0} max={2} step={0.1}
          format={v => v.toFixed(1)} onChange={v => set('llm_temperature', v)}
          hints={['0 · Deterministic', '2 · Creative', '1 · Balanced']}/>
        <SliderField label="Max Token" value={form.llm_max_tokens} min={100} max={4000} step={100}
          format={v => String(v)} onChange={v => set('llm_max_tokens', v)}
          hints={['100 · Short', '4000 · Long']}/>
      </div>
    </SectionCard>
    </div>
  )

  if (tab === 'voice') {
    const provider = form.tts_provider || 'elevenlabs'
    const currentVoices = TTS_VOICES[provider] || TTS_VOICES.elevenlabs

    return (
    <div className="flex w-full flex-col">
      <SectionCard title="Voice Selection" subtitle="Choose how the assistant sounds" icon={Volume2}>
        <div className="space-y-2">
          <p className="text-[14px] font-bold leading-none text-[#000000] font-poppins">Provider</p>
          <div className="flex h-[45px] w-full items-center rounded-xl border border-slate-200 bg-slate-50 px-3 font-poppins text-sm text-[#000000] sm:max-w-sm">
            <span>{TTS_PROVIDERS[0].label}</span><span className="ml-2 text-xs text-slate-400">{TTS_PROVIDERS[0].badge}</span>
          </div>
        </div>

        <VoiceSelection
          provider={provider}
          voiceId={form.tts_voice_id}
          builtinVoices={currentVoices}
          onSelect={v => set('tts_voice_id', v)}
        />

        <div className="grid gap-5 sm:grid-cols-2">
          <SliderField label="Speech Speed" value={form.tts_speed} min={0.5} max={2.0} step={0.1}
            format={v => `${v.toFixed(1)}x`} onChange={v => set('tts_speed', v)}
            hints={['0.5x · Slow', '2.0x · Fast', '1.0x · Normal']}/>
          <SliderField label="Pitch" value={form.tts_pitch} min={0.5} max={2.0} step={0.1}
            format={v => v.toFixed(1)} onChange={v => set('tts_pitch', v)}
            hints={['0.5 · Low', '2.0 · High', '1.0 · Normal']}/>
        </div>
      </SectionCard>
      </div>
    )
  }

  if (tab === 'stt') {
    const sttModels = STT_MODELS[form.stt_provider] || STT_MODELS.deepgram
    const defaultSttModel = sttModels[0]?.value || 'nova-2'
    return (
    <div className="flex w-full flex-col">
      <SectionCard title="Transcriber" subtitle="Speech-to-text engine for incoming audio" icon={Mic}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-2">
            <p className="text-[14px] font-bold leading-none text-[#000000] font-poppins">Provider</p>
            <div className="flex h-[45px] w-full items-center rounded-xl border border-slate-200 bg-slate-50 px-3 font-poppins text-sm text-[#000000]">
              <span>{STT_PROVIDERS[0].label}</span><span className="ml-2 text-xs text-slate-400">{STT_PROVIDERS[0].badge}</span>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-stt-model" className="text-[14px] font-bold text-[#000000] font-poppins block">Model</Label>
            <Select value={form.stt_model || defaultSttModel} onValueChange={v => set('stt_model', v)}>
              <SelectTrigger id="agent-stt-model" className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
              <SelectContent>
                {sttModels.map(m => (
                  <SelectItem key={m.value} value={m.value}>
                    <div className="flex items-center gap-2"><span>{m.label}</span><span className="text-xs text-slate-400">{m.desc}</span></div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-stt-language" className="text-[14px] font-bold text-[#000000] font-poppins block">Language</Label>
            <Select value={form.stt_language} onValueChange={v => set('stt_language', v)}>
              <SelectTrigger id="agent-stt-language" className="w-full h-[45px] rounded-xl border border-slate-200 bg-white outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
              <SelectContent>
                {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
      </SectionCard>
      </div>
    )
  }

  if (tab === 'conversation') return (
    <div className="flex w-full flex-col">
      <SectionCard title="Conversation" subtitle="Turn-taking and call limits" icon={MessageSquare}>
      <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-800">Allow Interruptions (Barge-in)</p>
          <p className="text-xs text-slate-400 mt-0.5">User can speak while agent is talking</p>
        </div>
        <Toggle label="Allow interruptions" enabled={form.interrupt_enabled} onChange={v => set('interrupt_enabled', v)}/>
      </div>
      {form.interrupt_enabled && (
        <SliderField label="Interrupt Sensitivity" value={form.interrupt_sensitivity} min={0} max={1} step={0.1}
          format={v => v.toFixed(1)} onChange={v => set('interrupt_sensitivity', v)}
          hints={['0 · Low', '1 · High']}/>
      )}
      <SliderField label="Silence Timeout" value={form.silence_timeout} min={500} max={10000} step={500}
        format={v => v < 1000 ? `${v}ms` : `${(v/1000).toFixed(1)}s`}
        onChange={v => set('silence_timeout', v)} hints={['500ms', '10s']}/>
      <p className="text-xs text-slate-400 -mt-2">How long to wait after user stops speaking before responding.</p>
      <SliderField label="Max Call Duration" value={form.max_call_duration} min={60} max={7200} step={60}
        format={v => `${Math.floor(v/60)}m`} onChange={v => set('max_call_duration', v)} hints={['1m', '120m']}/>
    </SectionCard>
    </div>
  )

  if (tab === 'advanced') return (
    <div className="flex w-full flex-col">
      <SectionCard title="Advanced" subtitle="Extra signal processing and analysis" icon={Settings}>
      {[
        { key: 'background_noise_reduction', label: 'Background Noise Reduction', desc: 'Filter background noise from audio input' },
        { key: 'sentiment_analysis_enabled', label: 'Sentiment Analysis',          desc: 'Detect user sentiment in real-time during calls' },
        { key: 'emotion_detection_enabled',  label: 'Emotion Detection',           desc: 'Analyze emotional tone from voice patterns' },
      ].map(({ key, label, desc }) => (
        <div key={key} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-800">{label}</p>
            <p className="text-xs text-slate-400 mt-0.5">{desc}</p>
          </div>
          <Toggle label={label} enabled={(form as any)[key]} onChange={v => set(key as keyof AgentFormState, v)}/>
        </div>
      ))}
    </SectionCard>
    </div>
  )

  return null
}

// ── Tab nav bar ───────────────────────────────────────────────────────────────

/**
 * Step row from the design — the active step is a solid green pill, the rest
 * are plain text.
 */
export function AgentTabBar({
  activeTab,
  onChange,
  hidden = [],
}: {
  activeTab: AgentTabId
  onChange: (tab: AgentTabId) => void
  /** Tabs that can't apply here (e.g. Call History before the agent exists). */
  hidden?: AgentTabId[]
}) {
  return (
    <div className="-mx-1 flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {AGENT_TABS.filter(({ id }) => !hidden.includes(id)).map(({ id, label }) => {
        const active = activeTab === id
        return (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            title={label}
            className={`whitespace-nowrap rounded-3xl px-3 py-2 text-[14px] font-poppins transition-colors sm:px-4 sm:text-[15px] ${
              active
                ? 'bg-[#106959] font-semibold text-white'
                : 'font-medium text-[#000000] hover:bg-slate-100'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
