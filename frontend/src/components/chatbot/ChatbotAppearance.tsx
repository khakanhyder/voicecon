'use client'

import type { ChatbotConfig } from '@/lib/chatbots'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const inputClass =
  'h-11 w-full min-w-0 rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 disabled:bg-slate-50 disabled:text-slate-500'
const labelClass = 'mb-1.5 block text-[13px] font-semibold text-slate-700'
const selectTriggerClass =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors hover:border-slate-300 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 data-[state=open]:border-[#0F6A59] data-[state=open]:ring-2 data-[state=open]:ring-[#0F6A59]/15 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500'

function Field({
  id, label, value, onChange, hint, disabled, maxLength = 120,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  hint?: string
  disabled?: boolean
  maxLength?: number
}) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className={labelClass}>{label}</label>
      <input id={id} value={value} maxLength={maxLength} disabled={disabled} onChange={(e) => onChange(e.target.value)} className={inputClass} />
      {hint && <p className="mt-1.5 text-[12px] text-slate-500">{hint}</p>}
    </div>
  )
}

/** Branding fields for a chatbot, with a live preview beside them. */
export function ChatbotAppearance({
  config,
  onChange,
  disabled,
}: {
  config: ChatbotConfig
  onChange: (config: ChatbotConfig) => void
  disabled?: boolean
}) {
  const set = <K extends keyof ChatbotConfig>(key: K, value: ChatbotConfig[K]) =>
    onChange({ ...config, [key]: value })

  return (
    <div className="flex flex-col gap-6 xl:flex-row">
      <div className="min-w-0 flex-1 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="cb-title" label="Header title" value={config.title} onChange={(v) => set('title', v)} disabled={disabled} />
          <Field id="cb-subtitle" label="Subtitle" value={config.subtitle} onChange={(v) => set('subtitle', v)} disabled={disabled} />
        </div>
        <Field
          id="cb-greeting"
          label="Greeting message"
          value={config.greeting}
          onChange={(v) => set('greeting', v)}
          hint="The first message visitors see when they open the chat."
          disabled={disabled}
          maxLength={300}
        />
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="min-w-0">
            <label htmlFor="cb-accent" className={labelClass}>Accent color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                aria-label="Pick accent color"
                value={/^#[0-9a-f]{6}$/i.test(config.accent_color) ? config.accent_color : '#0F6A59'}
                onChange={(e) => set('accent_color', e.target.value)}
                disabled={disabled}
                className="h-11 w-12 flex-shrink-0 cursor-pointer rounded-xl border border-slate-200 bg-white p-1"
              />
              <input
                id="cb-accent"
                value={config.accent_color}
                onChange={(e) => set('accent_color', e.target.value)}
                disabled={disabled}
                maxLength={9}
                className={`${inputClass} font-mono text-[13px]`}
              />
            </div>
          </div>
          <div className="min-w-0">
            <label htmlFor="cb-position" className={labelClass}>Position</label>
            <Select
              value={config.position}
              onValueChange={(value) => set('position', value as ChatbotConfig['position'])}
              disabled={disabled}
            >
              <SelectTrigger id="cb-position" className={selectTriggerClass}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent searchable={false}>
                <SelectItem value="bottom-right">Bottom right</SelectItem>
                <SelectItem value="bottom-left">Bottom left</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Field id="cb-launcher" label="Launcher label" value={config.launcher_text} onChange={(v) => set('launcher_text', v)} disabled={disabled} maxLength={30} />
        </div>
      </div>

      <div className="w-full shrink-0 xl:w-[320px]">
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">Preview</p>
        <ChatbotPreview config={config} />
      </div>
    </div>
  )
}

/** A static mock of the embedded chat, updating live as the branding changes. */
export function ChatbotPreview({ config }: { config: ChatbotConfig }) {
  const accent = config.accent_color || '#0F6A59'
  const side = config.position === 'bottom-left' ? 'left' : 'right'
  return (
    <div className="relative h-[440px] overflow-hidden rounded-2xl border border-slate-200 bg-[radial-gradient(circle_at_top,_#f8fafc,_#eef2f5)]">
      <div className="absolute bottom-16 w-[272px] max-w-[calc(100%-24px)] overflow-hidden rounded-2xl bg-white shadow-xl" style={{ [side]: 12 }}>
        <div className="px-4 py-3 text-white" style={{ background: accent }}>
          <p className="text-sm font-semibold">{config.title || 'Chat with us'}</p>
          {config.subtitle && <p className="text-[11px] opacity-85">{config.subtitle}</p>}
        </div>
        <div className="space-y-2 bg-slate-50 p-3">
          <div className="max-w-[85%] rounded-xl rounded-bl-sm border border-slate-100 bg-white px-3 py-2 text-xs text-slate-700">
            {config.greeting || 'Hi! How can I help?'}
          </div>
          <div className="ml-auto max-w-[85%] rounded-xl rounded-br-sm px-3 py-2 text-xs text-white" style={{ background: accent }}>
            I have a question about pricing.
          </div>
        </div>
        <div className="flex gap-2 border-t border-slate-100 p-2.5">
          <div className="h-8 flex-1 rounded-lg border border-slate-200 bg-white" />
          <div className="h-8 rounded-lg px-3 text-xs font-medium leading-8 text-white" style={{ background: accent }}>Send</div>
        </div>
      </div>
      <div
        className="absolute bottom-3 rounded-full px-4 py-2 text-xs font-semibold text-white shadow-lg"
        style={{ background: accent, [side]: 12 }}
      >
        {config.launcher_text || 'Chat'}
      </div>
    </div>
  )
}
