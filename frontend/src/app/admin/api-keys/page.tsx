'use client'

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  AudioLines,
  Brain,
  CheckCircle2,
  CreditCard,
  Database,
  ExternalLink,
  Eye,
  EyeOff,
  Globe,
  KeyRound,
  Mail,
  Mic,
  Phone,
  Plug,
  RotateCcw,
  Shield,
  Sparkles,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { adminApi, type CheckResult, type SettingEntry, type SettingGroup } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Callout,
  Dialog,
  PageHeader,
  Toggle,
  errorText,
  inputClass,
  timeAgo,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'

const ICONS: Record<string, LucideIcon> = {
  sparkles: Sparkles,
  brain: Brain,
  mic: Mic,
  audio: AudioLines,
  phone: Phone,
  card: CreditCard,
  mail: Mail,
  database: Database,
  key: KeyRound,
  plug: Plug,
  shield: Shield,
  globe: Globe,
}

function groupState(group: SettingGroup): 'configured' | 'partial' | 'empty' {
  // Judge a provider by its secrets; optional ids and URLs would make every
  // fully working provider look half-configured.
  const secrets = group.settings.filter((s) => s.is_secret)
  const pool = secrets.length ? secrets : group.settings
  const set = pool.filter((s) => s.source !== 'unset').length
  if (set === 0) return 'empty'
  return set === pool.length ? 'configured' : 'partial'
}

function SourceBadge({ entry }: { entry: SettingEntry }) {
  if (entry.source === 'database') return <Badge tone="brand">Dashboard</Badge>
  if (entry.source === 'environment') return <Badge tone="neutral">Environment</Badge>
  return <Badge tone="warning">Not set</Badge>
}

function SettingRow({ entry, encryptionReady }: { entry: SettingEntry; encryptionReady: boolean }) {
  const qc = useQueryClient()
  const initial = entry.is_secret ? '' : entry.value == null ? '' : String(entry.value)
  const [draft, setDraft] = useState(initial)
  const [editingSecret, setEditingSecret] = useState(false)
  const [reveal, setReveal] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  useEffect(() => {
    setDraft(entry.is_secret ? '' : entry.value == null ? '' : String(entry.value))
  }, [entry.value, entry.is_secret])

  const save = useMutation({
    mutationFn: (value: unknown) => adminApi.saveSetting(entry.key, value),
    onSuccess: () => {
      toast.success(`${entry.label} saved`)
      setEditingSecret(false)
      setReveal(false)
      qc.invalidateQueries({ queryKey: ['admin', 'settings'] })
      qc.invalidateQueries({ queryKey: ['admin', 'overview'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const reset = useMutation({
    mutationFn: () => adminApi.resetSetting(entry.key),
    onSuccess: () => {
      toast.success(`${entry.label} now uses the environment value`)
      setConfirmReset(false)
      qc.invalidateQueries({ queryKey: ['admin', 'settings'] })
      qc.invalidateQueries({ queryKey: ['admin', 'overview'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const dirty = draft.trim() !== initial.trim()
  const secretBlocked = entry.is_secret && !encryptionReady

  let control: React.ReactNode
  if (entry.kind === 'bool') {
    control = (
      <div className="flex items-center gap-3">
        <Toggle
          label={entry.label}
          checked={Boolean(entry.value)}
          disabled={save.isPending}
          onChange={(v) => save.mutate(v)}
        />
        <span className="text-sm text-slate-600">{entry.value ? 'On' : 'Off'}</span>
      </div>
    )
  } else if (entry.is_secret && !editingSecret && entry.source !== 'unset') {
    control = (
      <div className="flex flex-wrap items-center gap-2">
        <code className="rounded-md bg-slate-100 px-2.5 py-1.5 font-mono text-sm text-slate-700">{entry.hint ?? '••••'}</code>
        <AdminButton icon={KeyRound} disabled={secretBlocked} onClick={() => setEditingSecret(true)}>
          Replace
        </AdminButton>
      </div>
    )
  } else {
    const inputType = entry.is_secret && !reveal ? 'password' : entry.kind === 'int' ? 'number' : 'text'
    control = (
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault()
          if (draft.trim()) save.mutate(entry.kind === 'text' ? draft : draft.trim())
        }}
      >
        {entry.kind === 'choice' ? (
          <select value={draft} onChange={(e) => setDraft(e.target.value)} className={inputClass}>
            {!draft && <option value="">Select…</option>}
            {entry.choices.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        ) : entry.key === 'APPLE_PRIVATE_KEY' ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            placeholder="-----BEGIN PRIVATE KEY-----"
            className={cn(inputClass, 'h-auto py-2 font-mono text-xs')}
            autoComplete="off"
            spellCheck={false}
          />
        ) : (
          <div className="relative flex-1">
            <input
              type={inputType}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={entry.placeholder || (entry.is_secret ? 'Paste the new key' : '')}
              className={cn(inputClass, entry.is_secret && 'pr-9 font-mono')}
              autoComplete="off"
              spellCheck={false}
              disabled={secretBlocked}
            />
            {entry.is_secret && (
              <button
                type="button"
                aria-label={reveal ? 'Hide' : 'Show'}
                onClick={() => setReveal((r) => !r)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:text-slate-600"
              >
                {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            )}
          </div>
        )}
        <div className="flex gap-2">
          <AdminButton type="submit" variant="primary" loading={save.isPending} disabled={!draft.trim() || (!entry.is_secret && !dirty) || secretBlocked}>
            Save
          </AdminButton>
          {entry.is_secret && editingSecret && (
            <AdminButton variant="ghost" onClick={() => { setEditingSecret(false); setDraft(''); setReveal(false) }}>
              Cancel
            </AdminButton>
          )}
        </div>
      </form>
    )
  }

  return (
    <div data-setting={entry.key} className="grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] md:gap-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-slate-900">{entry.label}</p>
          <SourceBadge entry={entry} />
        </div>
        <p className="mt-0.5 font-mono text-[11px] text-slate-400">{entry.key}</p>
        {entry.description && <p className="mt-1 text-xs text-slate-500">{entry.description}</p>}
        {entry.error && <p className="mt-1 text-xs text-rose-600">{entry.error}</p>}
      </div>
      <div className="min-w-0">
        {control}
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400">
          {entry.source === 'database' && entry.updated_at && (
            <span>
              Changed {timeAgo(entry.updated_at)}
              {entry.updated_by ? ` by ${entry.updated_by}` : ''}
            </span>
          )}
          {entry.source === 'database' && (
            <button type="button" onClick={() => setConfirmReset(true)} className="inline-flex items-center gap-1 font-medium text-slate-500 hover:text-slate-800">
              <RotateCcw className="h-3 w-3" />
              {entry.has_env_value ? 'Use environment value' : 'Clear'}
            </button>
          )}
        </div>
      </div>

      <Dialog
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        title={entry.has_env_value ? `Use the environment value for ${entry.label}?` : `Clear ${entry.label}?`}
        description={
          entry.has_env_value
            ? `The dashboard value is removed and ${entry.key} from the server environment applies again, within about 15 seconds on every server.`
            : `There is no ${entry.key} in the server environment, so this leaves the setting empty.`
        }
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setConfirmReset(false)}>Cancel</AdminButton>
            <AdminButton variant="danger" loading={reset.isPending} onClick={() => reset.mutate()}>
              {entry.has_env_value ? 'Use environment value' : 'Clear'}
            </AdminButton>
          </>
        }
      />
    </div>
  )
}

function TestResult({ result }: { result: CheckResult }) {
  const tone = result.status === 'ok' ? 'success' : result.status === 'not_configured' ? 'warning' : 'danger'
  return (
    <Callout tone={tone} title={result.status === 'ok' ? 'Connection works' : result.status === 'not_configured' ? 'Not configured' : result.status === 'invalid' ? 'Credential rejected' : 'Check failed'}>
      {result.message}
      {result.latency_ms != null && <span className="ml-1 opacity-70">({result.latency_ms} ms)</span>}
    </Callout>
  )
}

export default function ApiKeysPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['admin', 'settings'], queryFn: adminApi.settings })
  const [selected, setSelected] = useState<string>('openai')
  const [results, setResults] = useState<Record<string, CheckResult>>({})

  const group = useMemo(() => data?.groups.find((g) => g.id === selected) ?? data?.groups[0], [data, selected])

  const test = useMutation({
    mutationFn: (provider: string) => adminApi.testProvider(provider),
    onSuccess: (result, provider) => setResults((r) => ({ ...r, [provider]: result })),
    onError: (e) => toast.error(errorText(e)),
  })

  const Icon = group ? ICONS[group.icon] ?? KeyRound : KeyRound

  return (
    <>
      <PageHeader
        title="API Keys & Providers"
        description={
          <>
            Keys saved here override the server&apos;s environment variables and take effect within about 15
            seconds on every server, with no redeploy. Secrets are encrypted at rest and never shown again after saving.
          </>
        }
      />

      {data && !data.encryption_ready && (
        <div className="mb-6">
          <Callout tone="danger" title="Secrets cannot be saved yet">
            The server has no ENCRYPTION_SECRET_KEY / ENCRYPTION_SALT, so it cannot store keys safely. Set both in the
            server environment and restart. Non-secret settings can still be changed.
          </Callout>
        </div>
      )}
      {error ? <Callout tone="danger" title="Could not load settings">{errorText(error)}</Callout> : null}

      <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <nav className="h-fit rounded-xl border border-slate-200 bg-white p-2 shadow-sm lg:sticky lg:top-0">
          {isLoading &&
            Array.from({ length: 8 }).map((_, i) => <div key={i} className="m-2 h-7 animate-pulse rounded bg-slate-100" />)}
          {data?.groups.map((g) => {
            const GIcon = ICONS[g.icon] ?? KeyRound
            const state = groupState(g)
            const active = group?.id === g.id
            return (
              <button
                key={g.id}
                type="button"
                onClick={() => setSelected(g.id)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  active ? 'bg-brand-50 font-medium text-brand-800' : 'text-slate-600 hover:bg-slate-50'
                )}
              >
                <GIcon className={cn('h-4 w-4 flex-shrink-0', active ? 'text-brand-600' : 'text-slate-400')} />
                <span className="flex-1 truncate">{g.label}</span>
                <span
                  title={state === 'configured' ? 'Configured' : state === 'partial' ? 'Partly configured' : 'Not configured'}
                  className={cn(
                    'h-2 w-2 flex-shrink-0 rounded-full',
                    state === 'configured' ? 'bg-emerald-500' : state === 'partial' ? 'bg-amber-400' : 'bg-slate-300'
                  )}
                />
              </button>
            )
          })}
        </nav>

        {group && (
          <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <header className="flex flex-col gap-4 border-b border-slate-100 px-6 py-5 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex min-w-0 gap-3">
                <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-slate-900">{group.label}</h2>
                  <p className="mt-0.5 text-sm text-slate-500">{group.description}</p>
                </div>
              </div>
              <div className="flex flex-shrink-0 gap-2">
                {group.docs_url && (
                  <a href={group.docs_url} target="_blank" rel="noreferrer noopener">
                    <AdminButton variant="ghost" icon={ExternalLink}>Get keys</AdminButton>
                  </a>
                )}
                {group.test && (
                  <AdminButton
                    icon={Zap}
                    loading={test.isPending && test.variables === group.test}
                    onClick={() => test.mutate(group.test!)}
                  >
                    Test connection
                  </AdminButton>
                )}
              </div>
            </header>

            {group.test && results[group.test] && (
              <div className="px-6 pt-4">
                <TestResult result={results[group.test]} />
              </div>
            )}

            <div className="divide-y divide-slate-100 px-6">
              {group.settings.map((entry) => (
                <SettingRow key={entry.key} entry={entry} encryptionReady={data?.encryption_ready ?? false} />
              ))}
            </div>

            <footer className="flex items-center gap-2 border-t border-slate-100 px-6 py-3 text-xs text-slate-500">
              <CheckCircle2 className="h-3.5 w-3.5 text-slate-400" />
              Order of precedence: dashboard value → server environment → built-in default. Every change is recorded in the audit log.
            </footer>
          </section>
        )}
      </div>
    </>
  )
}
