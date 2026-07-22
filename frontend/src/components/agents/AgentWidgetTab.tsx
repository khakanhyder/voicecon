'use client'

import { useEffect, useState } from 'react'
import { Check, Copy, Loader2, MessageSquare, Power } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

interface WidgetConfig {
  title: string
  subtitle: string
  greeting: string
  accent_color: string
  position: 'bottom-right' | 'bottom-left'
  launcher_text: string
}

interface WidgetState {
  exists: boolean
  enabled?: boolean
  public_key?: string
  config?: WidgetConfig
  embed_snippet?: string
}

const DEFAULTS: WidgetConfig = {
  title: 'Chat with us',
  subtitle: 'We usually reply in a few seconds',
  greeting: 'Hi! How can I help you today?',
  accent_color: '#4f46e5',
  position: 'bottom-right',
  launcher_text: 'Chat',
}

/**
 * Chat Widget tab — enable a text channel for this agent, brand it, and copy
 * the embed snippet. Same agent, same brain; the widget just delivers it as
 * text on the customer's website.
 */
export function AgentWidgetTab({ agentId }: { agentId: string }) {
  const [state, setState] = useState<WidgetState | null>(null)
  const [config, setConfig] = useState<WidgetConfig>(DEFAULTS)
  const [enabled, setEnabled] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    apiClient
      .get<WidgetState>(API_ENDPOINTS.AGENT_WIDGET(agentId))
      .then((res) => {
        setState(res.data)
        if (res.data.exists) {
          setConfig({ ...DEFAULTS, ...(res.data.config || {}) })
          setEnabled(res.data.enabled ?? true)
        }
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [agentId])

  const save = async () => {
    setSaving(true)
    try {
      const res = await apiClient.put<WidgetState & { public_key: string; embed_snippet: string }>(
        API_ENDPOINTS.AGENT_WIDGET(agentId),
        { enabled, config }
      )
      setState({ ...res.data, exists: true })
      toast.success(state?.exists ? 'Widget updated' : 'Chat widget enabled')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const copyEmbed = () => {
    if (!state?.embed_snippet) return
    navigator.clipboard.writeText(state.embed_snippet)
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  const set = <K extends keyof WidgetConfig>(key: K, value: WidgetConfig[K]) =>
    setConfig((c) => ({ ...c, [key]: value }))

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    )
  }

  return (
    // Flex (not grid) so the settings column can shrink below its content —
    // grid tracks don't shrink without min-w-0 and were overflowing the card.
    // Side-by-side only on xl; stacks on desktop-narrow, tablet, and mobile.
    <div className="flex flex-col gap-6 xl:flex-row">
      {/* Settings */}
      <div className="min-w-0 flex-1 space-y-5">
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50">
              <MessageSquare className="h-4 w-4 text-indigo-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-800">Chat widget</p>
              <p className="text-xs text-slate-400">
                A text version of this agent for your website.
              </p>
            </div>
          </div>
          <button
            onClick={() => setEnabled((v) => !v)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${
              enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
            }`}
          >
            <Power className="h-3.5 w-3.5" />
            {enabled ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="Header title" value={config.title} onChange={(v) => set('title', v)} />
          <TextField label="Subtitle" value={config.subtitle} onChange={(v) => set('subtitle', v)} />
        </div>

        <TextField
          label="Greeting message"
          value={config.greeting}
          onChange={(v) => set('greeting', v)}
          hint="The first message the visitor sees when they open the widget."
        />

        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
          <div className="min-w-0 space-y-1.5">
            <label className="text-xs font-medium text-slate-600">Accent color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={config.accent_color}
                onChange={(e) => set('accent_color', e.target.value)}
                className="h-9 w-12 cursor-pointer rounded border border-slate-200"
              />
              <input
                value={config.accent_color}
                onChange={(e) => set('accent_color', e.target.value)}
                className="h-9 flex-1 rounded-lg border border-slate-200 px-2 text-sm outline-none"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-600">Position</label>
            <select
              value={config.position}
              onChange={(e) => set('position', e.target.value as WidgetConfig['position'])}
              className="h-9 w-full rounded-lg border border-slate-200 px-2 text-sm outline-none"
            >
              <option value="bottom-right">Bottom right</option>
              <option value="bottom-left">Bottom left</option>
            </select>
          </div>
          <TextField label="Launcher label" value={config.launcher_text} onChange={(v) => set('launcher_text', v)} />
        </div>

        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-2 rounded-lg gradient-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          {state?.exists ? 'Save changes' : 'Enable widget'}
        </button>

        {/* Embed snippet */}
        {state?.exists && state.embed_snippet && (
          <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-700">Install on your website</p>
              <button
                onClick={copyEmbed}
                className="flex items-center gap-1.5 rounded-lg bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-100"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Paste this into the <code className="rounded bg-slate-200 px-1">&lt;head&gt;</code> of any page.
            </p>
            {/* The snippet is one long line; wrap it so it never forces the
                card wider, while still being copyable verbatim. */}
            <pre className="max-w-full whitespace-pre-wrap break-all rounded-lg bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100">
              {state.embed_snippet}
            </pre>
          </div>
        )}
      </div>

      {/* Live preview — full width when stacked, fixed rail when side-by-side */}
      <div className="w-full shrink-0 xl:w-[300px]">
        <p className="mb-2 text-xs font-medium text-slate-500">Preview</p>
        <WidgetPreview config={config} />
      </div>
    </div>
  )
}

function TextField({
  label, value, onChange, hint,
}: {
  label: string; value: string; onChange: (v: string) => void; hint?: string
}) {
  return (
    <div className="min-w-0 space-y-1.5">
      <label className="text-xs font-medium text-slate-600">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full min-w-0 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:ring-2 focus:ring-indigo-200"
      />
      {hint && <p className="text-[11px] text-slate-400">{hint}</p>}
    </div>
  )
}

/** A static mock of how the widget renders, updating live as you edit. */
function WidgetPreview({ config }: { config: WidgetConfig }) {
  return (
    <div className="relative h-[420px] overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-b from-slate-50 to-slate-100">
      <div
        className="absolute bottom-4 w-[280px] overflow-hidden rounded-2xl bg-white shadow-xl"
        style={{ [config.position === 'bottom-left' ? 'left' : 'right']: 16 } as any}
      >
        <div className="px-4 py-3 text-white" style={{ background: config.accent_color }}>
          <p className="text-sm font-semibold">{config.title || 'Chat with us'}</p>
          {config.subtitle && <p className="text-[11px] opacity-85">{config.subtitle}</p>}
        </div>
        <div className="space-y-2 bg-slate-50 p-3">
          <div className="max-w-[85%] rounded-xl rounded-bl-sm border border-slate-100 bg-white px-3 py-2 text-xs text-slate-700">
            {config.greeting || 'Hi! How can I help?'}
          </div>
          <div
            className="ml-auto max-w-[85%] rounded-xl rounded-br-sm px-3 py-2 text-xs text-white"
            style={{ background: config.accent_color }}
          >
            I have a question about pricing.
          </div>
        </div>
        <div className="flex gap-2 border-t border-slate-100 p-2.5">
          <div className="h-8 flex-1 rounded-lg border border-slate-200 bg-white" />
          <div className="h-8 rounded-lg px-3 text-xs font-medium leading-8 text-white" style={{ background: config.accent_color }}>
            Send
          </div>
        </div>
      </div>
    </div>
  )
}
