'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, KeyRound, Loader2, Pause, Play, Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { useConfirm } from '@/hooks/use-confirm'
import { PhoneDialog } from '@/components/phone-numbers/PhoneDialog'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface BuiltinVoice {
  value: string
  label: string
  gender: string
  style: string
}

interface CustomVoice {
  id: string
  provider: string
  voice_id: string
  name: string
  category: string | null
  description: string | null
  labels: Record<string, string>
  uses_own_key: boolean
}

interface ProviderField {
  key: string
  label: string
  required: boolean
  secret: boolean
  placeholder: string
  help: string
}

interface VoiceProvider {
  slug: string
  label: string
  fields: ProviderField[]
}

interface VoiceRef {
  provider: string
  voice_id: string
  api_key?: string
}

interface CheckedVoice {
  name: string | null
  category: string | null
  description: string | null
  labels: Record<string, string>
}

// ── Preview player ────────────────────────────────────────────────────────────

type PreviewStatus = 'loading' | 'playing' | 'paused'

/** The API answers a failed audio request with JSON, which arrives as a Blob. */
async function previewErrorMessage(error: unknown): Promise<string> {
  const data = (error as { response?: { data?: unknown } })?.response?.data
  if (data instanceof Blob) {
    try {
      const detail = JSON.parse(await data.text())?.detail
      if (typeof detail === 'string' && detail) return detail
    } catch {
      // Not JSON; fall through to the generic message.
    }
    return 'This voice could not be played. Please try again.'
  }
  return getErrorMessage(error)
}

/**
 * One audio element for the whole picker, so starting a preview always stops
 * the one before it. Samples are kept for the life of the picker: replaying a
 * voice costs nothing.
 */
function useVoicePreview() {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const samples = useRef(new Map<string, string>())
  // Bumped on every new request, so a slow response for a voice the person
  // has already moved on from is dropped instead of starting to play.
  const request = useRef(0)
  const [active, setActive] = useState<{ key: string; status: PreviewStatus } | null>(null)

  useEffect(() => {
    const audio = new Audio()
    audio.preload = 'auto'
    const onEnded = () => setActive(null)
    audio.addEventListener('ended', onEnded)
    audioRef.current = audio
    const urls = samples.current
    return () => {
      request.current += 1
      audio.removeEventListener('ended', onEnded)
      audio.pause()
      audio.removeAttribute('src')
      urls.forEach(url => URL.revokeObjectURL(url))
      urls.clear()
    }
  }, [])

  const stop = useCallback(() => {
    request.current += 1
    audioRef.current?.pause()
    setActive(null)
  }, [])

  const toggle = useCallback(async (key: string, ref: VoiceRef, options: { keep?: boolean } = {}) => {
    const audio = audioRef.current
    if (!audio) return

    if (active?.key === key) {
      if (active.status === 'playing') {
        audio.pause()
        setActive({ key, status: 'paused' })
        return
      }
      if (active.status === 'paused') {
        try {
          await audio.play()
          setActive({ key, status: 'playing' })
        } catch {
          setActive(null)
        }
        return
      }
      // Still loading: a second click cancels.
      request.current += 1
      setActive(null)
      return
    }

    audio.pause()
    const mine = ++request.current
    setActive({ key, status: 'loading' })
    try {
      let url = samples.current.get(key)
      if (!url) {
        const res = await apiClient.post(API_ENDPOINTS.VOICE_PREVIEW, ref, { responseType: 'blob' })
        if (mine !== request.current) return
        url = URL.createObjectURL(res.data as Blob)
        if (options.keep !== false) samples.current.set(key, url)
      }
      audio.src = url
      audio.currentTime = 0
      await audio.play()
      if (mine !== request.current) {
        audio.pause()
        return
      }
      setActive({ key, status: 'playing' })
    } catch (error) {
      if (mine !== request.current) return
      setActive(null)
      toast.error(await previewErrorMessage(error))
    }
  }, [active])

  const statusOf = (key: string): PreviewStatus | 'idle' => (active?.key === key ? active.status : 'idle')

  return { toggle, stop, statusOf }
}

type VoicePreview = ReturnType<typeof useVoicePreview>

function PreviewButton({ name, status, onClick }: {
  name: string; status: PreviewStatus | 'idle'; onClick: () => void
}) {
  const label =
    status === 'playing' ? `Pause ${name}` : status === 'loading' ? `Loading ${name}` : `Play ${name}`
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={status === 'playing' ? 'Pause' : status === 'loading' ? 'Loading' : 'Listen'}
      className={`flex h-10 w-10 max-sm:h-11 max-sm:w-11 flex-shrink-0 items-center justify-center rounded-full outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[#0F6A59]/40 ${
        status === 'idle'
          ? 'bg-[#0F6A59]/10 text-[#0F6A59] hover:bg-[#0F6A59]/20'
          : 'bg-[#0F6A59] text-white'
      }`}
    >
      {status === 'loading' ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : status === 'playing' ? (
        <Pause className="h-4 w-4" fill="currentColor" />
      ) : (
        <Play className="ml-0.5 h-4 w-4" fill="currentColor" />
      )}
    </button>
  )
}

// ── Voice card ────────────────────────────────────────────────────────────────

function VoiceCard({ name, meta, badge, selected, status, onPreview, onSelect, onDelete }: {
  name: string
  meta: string
  badge?: React.ReactNode
  selected: boolean
  status: PreviewStatus | 'idle'
  onPreview: () => void
  onSelect: () => void
  onDelete?: () => void
}) {
  return (
    <div
      className={`flex items-center gap-3 rounded-xl border p-3 transition-colors ${
        selected
          ? 'border-[#0F6A59] bg-[#0F6A59]/[0.04] ring-1 ring-[#0F6A59]'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      <PreviewButton name={name} status={status} onClick={onPreview} />
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className="min-w-0 flex-1 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-[#0F6A59]/40"
      >
        <span className="flex items-center gap-1.5">
          <span className="truncate font-poppins text-[14px] font-semibold text-slate-900">{name}</span>
          {badge}
        </span>
        <span className="block truncate text-xs text-slate-500">
          {status === 'playing' ? 'Playing sample…' : status === 'loading' ? 'Loading sample…' : meta}
        </span>
      </button>
      {selected ? (
        <span className="flex flex-shrink-0 items-center gap-1 rounded-full bg-[#0F6A59] px-2.5 py-1 text-xs font-semibold text-white">
          <Check className="h-3 w-3" /> Selected
        </span>
      ) : (
        <button
          type="button"
          onClick={onSelect}
          className="flex-shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition-colors hover:border-[#0F6A59] hover:text-[#0F6A59]"
        >
          Select
        </button>
      )}
      {onDelete && (
        <button
          type="button"
          onClick={onDelete}
          aria-label={`Remove ${name}`}
          title="Remove from library"
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

function SectionHeading({ title, count, action }: { title: string; count?: number; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h3 className="font-poppins text-[14px] font-bold text-[#000000]">
        {title}
        {count !== undefined && <span className="ml-2 text-xs font-medium text-slate-400">{count}</span>}
      </h3>
      {action}
    </div>
  )
}

function customVoiceMeta(voice: { category: string | null; labels: Record<string, string> }): string {
  const parts = [voice.category, voice.labels?.gender, voice.labels?.accent]
    .filter((p): p is string => !!p)
    .map(p => p.charAt(0).toUpperCase() + p.slice(1))
  return parts.length ? parts.join(' · ') : 'Custom voice'
}

// ── Add custom voice ──────────────────────────────────────────────────────────

const FIELD_CLASS =
  'h-[45px] w-full rounded-xl border border-slate-200 bg-white px-3 font-poppins text-[14px] text-[#000000] outline-none transition-colors placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15'

const DRAFT_KEY = 'draft'

function AddCustomVoiceDialog({ open, onClose, providers, initialVoiceId, preview, onSaved }: {
  open: boolean
  onClose: () => void
  providers: VoiceProvider[]
  initialVoiceId: string
  preview: VoicePreview
  onSaved: (voice: CustomVoice) => void
}) {
  const [slug, setSlug] = useState('')
  const [values, setValues] = useState<Record<string, string>>({})
  const [name, setName] = useState('')
  const [checking, setChecking] = useState(false)
  const [saving, setSaving] = useState(false)
  const [checked, setChecked] = useState<CheckedVoice | null>(null)
  const [error, setError] = useState('')

  const provider = providers.find(p => p.slug === slug) ?? providers[0]
  const { stop } = preview

  useEffect(() => {
    if (!open) return
    setSlug(providers[0]?.slug ?? '')
    setValues({ voice_id: initialVoiceId })
    setName('')
    setChecked(null)
    setError('')
    // Reset only when the dialog opens, not when its inputs change identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  if (!provider) return null

  const ref: VoiceRef = {
    provider: provider.slug,
    voice_id: (values.voice_id ?? '').trim(),
    ...(values.api_key?.trim() ? { api_key: values.api_key.trim() } : {}),
  }
  const missing = provider.fields.some(f => f.required && !(values[f.key] ?? '').trim())
  const busy = checking || saving

  const close = () => {
    stop()
    onClose()
  }

  // Anything checked or heard belongs to the values it was checked with.
  const edit = (key: string, value: string) => {
    setValues(v => ({ ...v, [key]: value }))
    setChecked(null)
    setError('')
    stop()
  }

  const check = async () => {
    setChecking(true)
    setError('')
    try {
      const { data } = await apiClient.post<CheckedVoice>(API_ENDPOINTS.CUSTOM_VOICE_CHECK, ref)
      setChecked(data)
      setName(data.name ?? '')
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setChecking(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setError('')
    try {
      const { data } = await apiClient.post<CustomVoice>(API_ENDPOINTS.CUSTOM_VOICES, {
        ...ref,
        name: name.trim(),
      })
      stop()
      onSaved(data)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <PhoneDialog
      open={open}
      onClose={close}
      busy={busy}
      size="md"
      title="Add custom voice"
      description="Use a voice from your own provider account, such as one you cloned."
      icon={<Plus className="h-5 w-5" />}
      footer={
        <>
          <button
            type="button"
            onClick={close}
            disabled={busy}
            className="inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </button>
          {checked ? (
            <button
              type="button"
              onClick={save}
              disabled={busy || !name.trim()}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white hover:bg-[#0c5a4b] disabled:opacity-50"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save voice
            </button>
          ) : (
            <button
              type="button"
              onClick={check}
              disabled={busy || missing}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white hover:bg-[#0c5a4b] disabled:opacity-50"
            >
              {checking && <Loader2 className="h-4 w-4 animate-spin" />}
              {checking ? 'Checking…' : 'Check voice'}
            </button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="block font-poppins text-[14px] font-bold text-[#000000]">Provider</label>
          {providers.length > 1 ? (
            <select
              value={provider.slug}
              onChange={e => {
                setSlug(e.target.value)
                setValues({})
                setChecked(null)
                setError('')
                stop()
              }}
              className={FIELD_CLASS}
            >
              {providers.map(p => <option key={p.slug} value={p.slug}>{p.label}</option>)}
            </select>
          ) : (
            <div className="flex h-[45px] items-center rounded-xl border border-slate-200 bg-slate-50 px-3 font-poppins text-sm text-[#000000]">
              {provider.label}
            </div>
          )}
        </div>

        {provider.fields.map(f => (
          <div key={f.key} className="space-y-1.5">
            <label htmlFor={`voice-field-${f.key}`} className="block font-poppins text-[14px] font-bold text-[#000000]">
              {f.label}
              {f.required
                ? <span className="text-red-500"> *</span>
                : <span className="ml-1.5 text-xs font-medium text-slate-400">Optional</span>}
            </label>
            <input
              id={`voice-field-${f.key}`}
              type={f.secret ? 'password' : 'text'}
              value={values[f.key] ?? ''}
              onChange={e => edit(f.key, e.target.value)}
              placeholder={f.placeholder}
              autoComplete={f.secret ? 'new-password' : 'off'}
              spellCheck={false}
              className={`${FIELD_CLASS} ${f.secret ? '' : 'font-mono text-[13px]'}`}
            />
            {f.help && (
              <p className="flex items-start gap-1.5 text-xs leading-relaxed text-slate-500">
                {f.secret && <KeyRound className="mt-0.5 h-3 w-3 flex-shrink-0" />}
                {f.help}
              </p>
            )}
          </div>
        ))}

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {checked && (
          <div className="space-y-3 rounded-xl border border-[#0F6A59]/30 bg-[#0F6A59]/[0.04] p-3">
            <div className="flex items-center gap-3">
              <PreviewButton
                name={checked.name ?? 'this voice'}
                status={preview.statusOf(DRAFT_KEY)}
                onClick={() => preview.toggle(DRAFT_KEY, ref, { keep: false })}
              />
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 text-[13px] font-semibold text-[#0F6A59]">
                  <ShieldCheck className="h-4 w-4" /> Voice found
                </p>
                <p className="truncate text-xs text-slate-600">
                  {checked.name ? `${checked.name} · ${customVoiceMeta(checked)}` : 'Listen to make sure it is the right one.'}
                </p>
              </div>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="voice-field-name" className="block font-poppins text-[14px] font-bold text-[#000000]">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                id="voice-field-name"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Front desk voice"
                maxLength={255}
                className={FIELD_CLASS}
              />
              <p className="text-xs text-slate-500">How this voice appears in your library.</p>
            </div>
          </div>
        )}
      </div>
    </PhoneDialog>
  )
}

// ── Voice selection ───────────────────────────────────────────────────────────

export function VoiceSelection({ provider, voiceId, builtinVoices, onSelect }: {
  provider: string
  voiceId: string
  builtinVoices: BuiltinVoice[]
  onSelect: (voiceId: string) => void
}) {
  const preview = useVoicePreview()
  const { confirm, ConfirmDialog } = useConfirm()
  const [customVoices, setCustomVoices] = useState<CustomVoice[]>([])
  const [providers, setProviders] = useState<VoiceProvider[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [adding, setAdding] = useState(false)
  const [prefill, setPrefill] = useState('')

  const load = useCallback(async () => {
    setLoadError('')
    try {
      const { data } = await apiClient.get(API_ENDPOINTS.VOICES)
      setCustomVoices(data.custom_voices ?? [])
      setProviders(data.providers ?? [])
      setLoaded(true)
    } catch (e) {
      setLoadError(getErrorMessage(e))
    }
  }, [])

  useEffect(() => { load() }, [load])

  const mine = customVoices.filter(v => v.provider === provider)
  const canAdd = providers.length > 0
  // A voice saved on the assistant that is in neither list: set through the
  // API, or left over from before the library existed.
  const unlisted =
    loaded && !!voiceId &&
    !builtinVoices.some(v => v.value === voiceId) &&
    !mine.some(v => v.voice_id === voiceId)

  const openAdd = (voiceIdToAdd = '') => {
    preview.stop()
    setPrefill(voiceIdToAdd)
    setAdding(true)
  }

  const remove = async (voice: CustomVoice) => {
    const ok = await confirm({
      title: `Remove ${voice.name}?`,
      description: 'It will be removed from your voice library. You can add it again later.',
      confirmText: 'Remove',
    })
    if (!ok) return
    try {
      await apiClient.delete(API_ENDPOINTS.CUSTOM_VOICE(voice.id))
      preview.stop()
      setCustomVoices(list => list.filter(v => v.id !== voice.id))
      if (voice.voice_id === voiceId && builtinVoices[0]) onSelect(builtinVoices[0].value)
      toast.success(`${voice.name} removed`)
    } catch (e) {
      toast.error(getErrorMessage(e))
    }
  }

  const addButton = canAdd && (
    <button
      type="button"
      onClick={() => openAdd()}
      className="inline-flex items-center gap-1.5 rounded-full border border-[#0F6A59] px-3 py-1.5 text-xs font-semibold text-[#0F6A59] transition-colors hover:bg-[#0F6A59] hover:text-white"
    >
      <Plus className="h-3.5 w-3.5" /> Add Custom Voice
    </button>
  )

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <SectionHeading title="Built-in Voices" count={builtinVoices.length} />
        <div className="grid gap-3 lg:grid-cols-2">
          {builtinVoices.map(v => (
            <VoiceCard
              key={v.value}
              name={v.label}
              meta={`${v.gender} · ${v.style}`}
              selected={v.value === voiceId}
              status={preview.statusOf(v.value)}
              onPreview={() => preview.toggle(v.value, { provider, voice_id: v.value })}
              onSelect={() => onSelect(v.value)}
            />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeading title="My Custom Voices" count={loaded ? mine.length : undefined} action={addButton} />

        {loadError && (
          <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-700">
            <span>Your custom voices could not be loaded. {loadError}</span>
            <button type="button" onClick={load} className="flex-shrink-0 font-semibold underline">Try again</button>
          </div>
        )}

        {unlisted && (
          <div className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 sm:flex-row sm:items-center">
            <PreviewButton
              name="current voice"
              status={preview.statusOf(voiceId)}
              onClick={() => preview.toggle(voiceId, { provider, voice_id: voiceId })}
            />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-amber-900">This assistant uses a voice that is not in your library</p>
              <p className="truncate font-mono text-xs text-amber-800">{voiceId}</p>
            </div>
            {canAdd && (
              <button
                type="button"
                onClick={() => openAdd(voiceId)}
                className="flex-shrink-0 rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-100"
              >
                Add to library
              </button>
            )}
          </div>
        )}

        {!loaded && !loadError ? (
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-4 text-[13px] text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading your voices…
          </div>
        ) : mine.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {mine.map(v => (
              <VoiceCard
                key={v.id}
                name={v.name}
                meta={customVoiceMeta(v)}
                badge={
                  <span className="flex-shrink-0 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                    Custom
                  </span>
                }
                selected={v.voice_id === voiceId}
                status={preview.statusOf(v.voice_id)}
                onPreview={() => preview.toggle(v.voice_id, { provider: v.provider, voice_id: v.voice_id })}
                onSelect={() => onSelect(v.voice_id)}
                onDelete={() => remove(v)}
              />
            ))}
          </div>
        ) : loaded && (
          <div className="rounded-xl border border-dashed border-slate-300 px-4 py-6 text-center">
            <p className="text-[13px] font-semibold text-slate-700">No custom voices yet</p>
            <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-500">
              Add a voice from your own provider account, such as a cloned voice, and it will appear here.
            </p>
          </div>
        )}
      </section>

      <AddCustomVoiceDialog
        open={adding}
        onClose={() => setAdding(false)}
        providers={providers}
        initialVoiceId={prefill}
        preview={preview}
        onSaved={voice => {
          setAdding(false)
          setCustomVoices(list => [voice, ...list.filter(v => v.id !== voice.id)])
          onSelect(voice.voice_id)
          toast.success(`${voice.name} added and selected`)
        }}
      />
      <ConfirmDialog />
    </div>
  )
}
