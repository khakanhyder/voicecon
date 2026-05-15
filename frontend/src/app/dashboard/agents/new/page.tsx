'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

const LLM_MODELS: Record<string, { label: string; value: string }[]> = {
  openai: [
    { value: 'gpt-4o-mini',       label: 'GPT-4o Mini — ~300ms ⚡ Best for voice' },
    { value: 'gpt-4o',            label: 'GPT-4o — ~700ms  Smart + fast' },
    { value: 'gpt-4.1-mini',      label: 'GPT-4.1 Mini — ~350ms ⚡ Efficient' },
    { value: 'gpt-4.1',           label: 'GPT-4.1 — ~900ms  Latest flagship' },
    { value: 'gpt-4-turbo',       label: 'GPT-4 Turbo — ~1.2s  High quality' },
    { value: 'gpt-4',             label: 'GPT-4 — ~2s  Classic' },
    { value: 'gpt-3.5-turbo',     label: 'GPT-3.5 Turbo — ~200ms ⚡ Fastest/cheapest' },
    { value: 'o1-mini',           label: 'o1 Mini — ~4s  Reasoning (slow)' },
    { value: 'o3-mini',           label: 'o3 Mini — ~3s  Advanced reasoning' },
  ],
  anthropic: [
    { value: 'claude-haiku-4-5-20251001',    label: 'Claude Haiku 4.5 — ~400ms ⚡ Best for voice' },
    { value: 'claude-sonnet-4-6',            label: 'Claude Sonnet 4.6 — ~800ms  Balanced' },
    { value: 'claude-opus-4-6',              label: 'Claude Opus 4.6 — ~2s  Most powerful' },
    { value: 'claude-3-5-sonnet-20241022',   label: 'Claude 3.5 Sonnet — ~900ms  Proven' },
    { value: 'claude-3-haiku-20240307',      label: 'Claude 3 Haiku — ~350ms ⚡ Fast & cheap' },
    { value: 'claude-3-opus-20240229',       label: 'Claude 3 Opus — ~2.5s  Classic flagship' },
  ],
  groq: [
    { value: 'llama-4-scout-17b-16e-instruct',   label: 'Llama 4 Scout 17B — ~150ms ⚡ Fastest' },
    { value: 'llama-4-maverick-17b-128e-instruct', label: 'Llama 4 Maverick 17B — ~200ms ⚡ Best balance' },
    { value: 'llama3-8b-8192',               label: 'Llama 3 8B — ~100ms ⚡ Ultra-fast' },
    { value: 'llama3-70b-8192',              label: 'Llama 3 70B — ~300ms  High quality' },
    { value: 'mixtral-8x7b-32768',           label: 'Mixtral 8x7B — ~250ms  Good for chat' },
    { value: 'gemma2-9b-it',                 label: 'Gemma 2 9B — ~180ms ⚡ Efficient' },
  ],
}

const ELEVENLABS_VOICES = [
  { value: '21m00Tcm4TlvDq8ikWAM', label: 'Rachel (Female, calm)' },
  { value: 'AZnzlk1XvdvUeBnXmlld', label: 'Domi (Female, strong)' },
  { value: 'EXAVITQu4vr4xnSDxMaL', label: 'Bella (Female, soft)' },
  { value: 'ErXwobaYiN019PkySvjV', label: 'Antoni (Male, well-rounded)' },
  { value: 'MF3mGyEYCl7XYWbV9V6O', label: 'Elli (Female, emotional)' },
  { value: 'TxGEqnHWrfWFTfGW9XjX', label: 'Josh (Male, deep)' },
  { value: 'VR6AewLTigWG4xSOukaG', label: 'Arnold (Male, crisp)' },
  { value: 'pNInz6obpgDQGcFmaJgB', label: 'Adam (Male, narration)' },
  { value: 'yoZ06aMxZJJ28mfd3POQ', label: 'Sam (Male, raspy)' },
]

const STT_MODELS = [
  { value: 'nova-2', label: 'Nova 2 (Best accuracy)' },
  { value: 'nova', label: 'Nova (Fast)' },
  { value: 'enhanced', label: 'Enhanced' },
  { value: 'base', label: 'Base' },
]

export default function NewAgentPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('basic')

  const [form, setForm] = useState({
    name: '',
    description: '',
    system_prompt: '',
    first_message: 'Hello! How can I help you today?',
    // LLM
    llm_provider: 'openai',
    llm_model: 'gpt-4o-mini',
    llm_temperature: 0.7,
    llm_max_tokens: 1000,
    // TTS
    tts_provider: 'elevenlabs',
    tts_voice_id: '21m00Tcm4TlvDq8ikWAM',
    tts_speed: 1.0,
    tts_pitch: 1.0,
    // STT
    stt_provider: 'deepgram',
    stt_model: 'nova-2',
    stt_language: 'en',
    // Conversation
    interrupt_enabled: true,
    interrupt_sensitivity: 0.5,
    silence_timeout: 3000,
    max_call_duration: 1800,
    // Advanced
    background_noise_reduction: true,
    sentiment_analysis_enabled: false,
    emotion_detection_enabled: false,
  })

  const set = (key: string, value: any) => setForm(f => ({ ...f, [key]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      await apiClient.post(API_ENDPOINTS.AGENTS, {
        name: form.name,
        description: form.description,
        system_prompt: form.system_prompt,
        first_message: form.first_message,
        llm: {
          provider: form.llm_provider,
          model: form.llm_model,
          temperature: form.llm_temperature,
          max_tokens: form.llm_max_tokens,
        },
        voice: {
          provider: form.tts_provider,
          voice_id: form.tts_voice_id,
          speed: form.tts_speed,
          pitch: form.tts_pitch,
        },
        stt: {
          provider: form.stt_provider,
          model: form.stt_model,
          language: form.stt_language,
        },
        settings: {
          interrupt_enabled: form.interrupt_enabled,
          interrupt_sensitivity: form.interrupt_sensitivity,
          silence_timeout: form.silence_timeout,
          max_call_duration: form.max_call_duration,
        },
        advanced: {
          background_noise_reduction: form.background_noise_reduction,
          sentiment_analysis_enabled: form.sentiment_analysis_enabled,
          emotion_detection_enabled: form.emotion_detection_enabled,
        },
      })
      toast.success('Agent created successfully!')
      router.push('/dashboard/agents')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  const tabs = [
    { id: 'basic', label: '📋 Basic' },
    { id: 'llm', label: '🤖 AI Model' },
    { id: 'voice', label: '🔊 Voice' },
    { id: 'stt', label: '🎤 Speech' },
    { id: 'conversation', label: '💬 Conversation' },
    { id: 'advanced', label: '⚙️ Advanced' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Create New Agent</h1>
        <p className="text-muted-foreground">Configure your AI voice agent with full control</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 border-b overflow-x-auto">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${activeTab === t.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* BASIC */}
        {activeTab === 'basic' && (
          <div className="rounded-lg border bg-card p-6 space-y-4">
            <h2 className="text-xl font-semibold">Basic Information</h2>
            <div className="space-y-2">
              <Label htmlFor="name">Agent Name *</Label>
              <Input id="name" placeholder="Customer Support Agent" value={form.name}
                onChange={e => set('name', e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" placeholder="What does this agent do?" value={form.description}
                onChange={e => set('description', e.target.value)} rows={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="systemPrompt">System Prompt *</Label>
              <Textarea id="systemPrompt"
                placeholder="You are a helpful voice assistant. Be concise, friendly, and professional..."
                value={form.system_prompt}
                onChange={e => set('system_prompt', e.target.value)} rows={6} required />
              <p className="text-xs text-muted-foreground">Defines agent personality and instructions</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="firstMessage">First Message</Label>
              <Input id="firstMessage" value={form.first_message}
                onChange={e => set('first_message', e.target.value)}
                placeholder="Hello! How can I help you today?" />
              <p className="text-xs text-muted-foreground">Opening greeting when the call starts</p>
            </div>
          </div>
        )}

        {/* LLM */}
        {activeTab === 'llm' && (
          <div className="rounded-lg border bg-card p-6 space-y-6">
            <h2 className="text-xl font-semibold">AI Model Configuration</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>LLM Provider</Label>
                <Select value={form.llm_provider}
                  onValueChange={v => { set('llm_provider', v); set('llm_model', LLM_MODELS[v][0].value) }}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="anthropic">Anthropic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Model</Label>
                <Select value={form.llm_model} onValueChange={v => set('llm_model', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(LLM_MODELS[form.llm_provider] || []).map(m => (
                      <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Temperature: <span className="text-primary font-bold">{form.llm_temperature}</span></Label>
              <input type="range" min="0" max="2" step="0.1"
                value={form.llm_temperature}
                onChange={e => set('llm_temperature', parseFloat(e.target.value))}
                className="w-full accent-primary" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0 - Deterministic</span><span>1 - Balanced</span><span>2 - Creative</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Max Tokens: <span className="text-primary font-bold">{form.llm_max_tokens}</span></Label>
              <input type="range" min="100" max="4000" step="100"
                value={form.llm_max_tokens}
                onChange={e => set('llm_max_tokens', parseInt(e.target.value))}
                className="w-full accent-primary" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>100 (Short)</span><span>4000 (Long)</span>
              </div>
            </div>
          </div>
        )}

        {/* VOICE (TTS) */}
        {activeTab === 'voice' && (
          <div className="rounded-lg border bg-card p-6 space-y-6">
            <h2 className="text-xl font-semibold">Voice / Text-to-Speech</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>TTS Provider</Label>
                <Select value={form.tts_provider} onValueChange={v => set('tts_provider', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="elevenlabs">ElevenLabs ✅</SelectItem>
                    <SelectItem value="openai">OpenAI TTS</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Voice</Label>
                <Select value={form.tts_voice_id} onValueChange={v => set('tts_voice_id', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ELEVENLABS_VOICES.map(v => (
                      <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Speech Speed: <span className="text-primary font-bold">{form.tts_speed}x</span></Label>
              <input type="range" min="0.5" max="2.0" step="0.1"
                value={form.tts_speed}
                onChange={e => set('tts_speed', parseFloat(e.target.value))}
                className="w-full accent-primary" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0.5x (Slow)</span><span>1.0x (Normal)</span><span>2.0x (Fast)</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Pitch: <span className="text-primary font-bold">{form.tts_pitch}</span></Label>
              <input type="range" min="0.5" max="2.0" step="0.1"
                value={form.tts_pitch}
                onChange={e => set('tts_pitch', parseFloat(e.target.value))}
                className="w-full accent-primary" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0.5 (Low)</span><span>1.0 (Normal)</span><span>2.0 (High)</span>
              </div>
            </div>
          </div>
        )}

        {/* STT */}
        {activeTab === 'stt' && (
          <div className="rounded-lg border bg-card p-6 space-y-6">
            <h2 className="text-xl font-semibold">Speech Recognition (STT)</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>STT Provider</Label>
                <Select value={form.stt_provider} onValueChange={v => set('stt_provider', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="deepgram">Deepgram ✅</SelectItem>
                    <SelectItem value="whisper">OpenAI Whisper</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Model</Label>
                <Select value={form.stt_model} onValueChange={v => set('stt_model', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {STT_MODELS.map(m => (
                      <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Language</Label>
                <Select value={form.stt_language} onValueChange={v => set('stt_language', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="es">Spanish</SelectItem>
                    <SelectItem value="fr">French</SelectItem>
                    <SelectItem value="de">German</SelectItem>
                    <SelectItem value="it">Italian</SelectItem>
                    <SelectItem value="pt">Portuguese</SelectItem>
                    <SelectItem value="nl">Dutch</SelectItem>
                    <SelectItem value="ja">Japanese</SelectItem>
                    <SelectItem value="ko">Korean</SelectItem>
                    <SelectItem value="zh">Chinese</SelectItem>
                    <SelectItem value="ar">Arabic</SelectItem>
                    <SelectItem value="hi">Hindi</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        )}

        {/* CONVERSATION */}
        {activeTab === 'conversation' && (
          <div className="rounded-lg border bg-card p-6 space-y-6">
            <h2 className="text-xl font-semibold">Conversation Settings</h2>

            <div className="flex items-center justify-between rounded-lg border p-4">
              <div>
                <p className="font-medium">Allow Interruptions</p>
                <p className="text-sm text-muted-foreground">User can interrupt agent mid-sentence</p>
              </div>
              <button type="button" onClick={() => set('interrupt_enabled', !form.interrupt_enabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${form.interrupt_enabled ? 'bg-primary' : 'bg-muted'}`}>
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${form.interrupt_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>

            {form.interrupt_enabled && (
              <div className="space-y-2">
                <Label>Interrupt Sensitivity: <span className="text-primary font-bold">{form.interrupt_sensitivity}</span></Label>
                <input type="range" min="0" max="1" step="0.1"
                  value={form.interrupt_sensitivity}
                  onChange={e => set('interrupt_sensitivity', parseFloat(e.target.value))}
                  className="w-full accent-primary" />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>0 (Low)</span><span>1 (High)</span>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label>Silence Timeout: <span className="text-primary font-bold">{form.silence_timeout}ms</span></Label>
              <input type="range" min="500" max="10000" step="500"
                value={form.silence_timeout}
                onChange={e => set('silence_timeout', parseInt(e.target.value))}
                className="w-full accent-primary" />
              <p className="text-xs text-muted-foreground">How long before agent responds after user stops speaking</p>
            </div>

            <div className="space-y-2">
              <Label>Max Call Duration: <span className="text-primary font-bold">{Math.floor(form.max_call_duration / 60)} min</span></Label>
              <input type="range" min="60" max="7200" step="60"
                value={form.max_call_duration}
                onChange={e => set('max_call_duration', parseInt(e.target.value))}
                className="w-full accent-primary" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>1 min</span><span>120 min</span>
              </div>
            </div>
          </div>
        )}

        {/* ADVANCED */}
        {activeTab === 'advanced' && (
          <div className="rounded-lg border bg-card p-6 space-y-4">
            <h2 className="text-xl font-semibold">Advanced Features</h2>

            {[
              { key: 'background_noise_reduction', label: 'Background Noise Reduction', desc: 'Filter out background noise from audio' },
              { key: 'sentiment_analysis_enabled', label: 'Sentiment Analysis', desc: 'Detect user sentiment during calls' },
              { key: 'emotion_detection_enabled', label: 'Emotion Detection', desc: 'Detect user emotions from voice' },
            ].map(({ key, label, desc }) => (
              <div key={key} className="flex items-center justify-between rounded-lg border p-4">
                <div>
                  <p className="font-medium">{label}</p>
                  <p className="text-sm text-muted-foreground">{desc}</p>
                </div>
                <button type="button" onClick={() => set(key, !(form as any)[key])}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${(form as any)[key] ? 'bg-primary' : 'bg-muted'}`}>
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${(form as any)[key] ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-4">
          <Button type="submit" size="lg" disabled={isLoading}>
            {isLoading ? 'Creating...' : 'Create Agent'}
          </Button>
          <Button type="button" variant="outline" size="lg"
            onClick={() => router.push('/dashboard/agents')} disabled={isLoading}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  )
}
