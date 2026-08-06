'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, Check, ChevronDown, Link2, Loader2, RefreshCw, Search } from 'lucide-react'

import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

/**
 * Names a thing inside a connected app — a Trello list, a Slack channel, a
 * calendar — without ever showing the user an internal id.
 *
 * Three ways to say which one, because no single control suits everybody:
 *
 *  - **From list**  the default. Pick "To Do" from a searchable dropdown.
 *  - **From link**  paste the URL of the board you already have open in
 *                   another tab. Frequently the fastest route, and it needs no
 *                   API round trip at all.
 *  - **By ID**      the escape hatch: expressions like `{{steps.x.id}}`, and
 *                   anything the other two modes cannot express.
 *
 * The stored value is always the id. The name is only ever presentation, and
 * is resolved on mount so reopening a workflow shows "To Do" rather than the
 * opaque string that was saved.
 */

type Mode = 'list' | 'url' | 'id'

interface ResourceItem {
  id: string
  name: string
  state?: string
  url?: string
}

interface ResourceResponse {
  resources: ResourceItem[]
  label?: string
  empty_hint?: string
  needs_parent?: string
}

const INPUT_CLASS =
  'h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60'

export function ResourceLocator({
  id,
  value,
  connectionId,
  kind,
  parentValue,
  parentLabel,
  supportsUrl = true,
  placeholder,
  onChange,
}: {
  id: string
  value: string
  connectionId?: string
  kind: string
  /** Id of the parent resource, for nested kinds (board -> list). */
  parentValue?: string
  parentLabel?: string
  supportsUrl?: boolean
  placeholder?: string
  onChange: (value: string) => void
}) {
  // An expression can never come from a dropdown, so a value that looks like
  // one starts in the mode that can actually represent it.
  const looksLikeExpression = typeof value === 'string' && value.includes('{{')
  const [mode, setMode] = useState<Mode>(looksLikeExpression ? 'id' : 'list')
  const [items, setItems] = useState<ResourceItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<{ message: string; code?: string } | null>(null)
  const [hint, setHint] = useState<string>('')
  const [needsParent, setNeedsParent] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [urlDraft, setUrlDraft] = useState('')
  const [urlError, setUrlError] = useState<string | null>(null)
  const [isResolvingUrl, setIsResolvingUrl] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  const load = useCallback(
    async (refresh = false) => {
      if (!connectionId) {
        setItems([])
        return
      }
      setIsLoading(true)
      setError(null)
      try {
        const res = await apiClient.get<ResourceResponse>(
          API_ENDPOINTS.INTEGRATION_CONNECTION_RESOURCES(connectionId, kind),
          { params: { ...(parentValue ? { parent: parentValue } : {}), ...(refresh ? { refresh: true } : {}) } },
        )
        setItems(res.data.resources ?? [])
        setHint(res.data.empty_hint ?? '')
        setNeedsParent(res.data.needs_parent ?? null)
      } catch (e: any) {
        const body = e?.response?.data?.detail
        setItems([])
        setError({
          message: typeof body === 'string' ? body : body?.detail ?? 'Could not load options',
          code: typeof body === 'object' ? body?.code : undefined,
        })
      } finally {
        setIsLoading(false)
      }
    },
    [connectionId, kind, parentValue],
  )

  // Nested kinds refetch when the parent changes, and a selection made under
  // the old parent is dropped — a list from a different board is not valid.
  const previousParent = useRef(parentValue)
  useEffect(() => {
    if (previousParent.current !== parentValue) {
      previousParent.current = parentValue
      if (value && !looksLikeExpression) onChange('')
    }
    if (mode === 'list') void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId, kind, parentValue, mode])

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const selected = useMemo(
    () => items.find((item) => item.id === value),
    [items, value],
  )

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) return items
    return items.filter((item) => item.name.toLowerCase().includes(needle))
  }, [items, search])

  async function resolveUrl() {
    if (!connectionId || !urlDraft.trim()) return
    setIsResolvingUrl(true)
    setUrlError(null)
    try {
      const res = await apiClient.post<{ id: string }>(
        API_ENDPOINTS.INTEGRATION_CONNECTION_RESOURCE_FROM_URL(connectionId, kind),
        { url: urlDraft },
      )
      onChange(res.data.id)
      setUrlDraft('')
      setMode('list')
      void load(true)
    } catch (e: any) {
      const body = e?.response?.data?.detail
      setUrlError(typeof body === 'string' ? body : body?.detail ?? 'That link was not recognised')
    } finally {
      setIsResolvingUrl(false)
    }
  }

  if (!connectionId) {
    return <p className="text-xs text-muted-foreground">Choose a connection first.</p>
  }

  const modes: { key: Mode; label: string }[] = [
    { key: 'list', label: 'From list' },
    ...(supportsUrl ? [{ key: 'url' as Mode, label: 'From link' }] : []),
    { key: 'id', label: 'By ID' },
  ]

  return (
    <div className="space-y-2" ref={boxRef}>
      <div className="flex gap-1 rounded-md bg-muted p-0.5">
        {modes.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setMode(m.key)}
            className={`flex-1 rounded px-2 py-1 text-[11px] font-medium transition-colors ${
              mode === m.key
                ? 'bg-background shadow-sm text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {mode === 'list' && (
        <>
          {needsParent ? (
            <p className="text-xs text-muted-foreground">
              Choose a {parentLabel ?? needsParent.replace(/s$/, '')} first.
            </p>
          ) : error ? (
            <div className="space-y-1.5 rounded-md border border-amber-200 bg-amber-50 p-2.5">
              <p className="flex items-start gap-1.5 text-xs text-amber-800">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                {error.message}
              </p>
              {error.code === 'disconnected' ? (
                <a
                  href="/dashboard/integrations"
                  className="inline-block text-xs font-medium text-amber-900 underline"
                >
                  Reconnect it
                </a>
              ) : (
                <button
                  type="button"
                  onClick={() => void load(true)}
                  className="text-xs font-medium text-amber-900 underline"
                >
                  Try again
                </button>
              )}
            </div>
          ) : (
            <div className="relative">
              <button
                type="button"
                id={id}
                onClick={() => setOpen((o) => !o)}
                disabled={isLoading}
                className={`${INPUT_CLASS} flex items-center justify-between text-left`}
              >
                <span className={selected || value ? '' : 'text-muted-foreground'}>
                  {isLoading ? (
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
                    </span>
                  ) : selected ? (
                    selected.name
                  ) : value ? (
                    // Saved id that no longer resolves. Say so plainly rather
                    // than rendering a raw id the user cannot interpret.
                    <span className="text-amber-700">No longer available — pick again</span>
                  ) : (
                    placeholder ?? 'Select…'
                  )}
                </span>
                <ChevronDown className="h-4 w-4 flex-shrink-0 opacity-50" />
              </button>

              {open && !isLoading && (
                <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-md border bg-background shadow-lg">
                  <div className="flex items-center gap-2 border-b px-2.5 py-1.5">
                    <Search className="h-3.5 w-3.5 flex-shrink-0 opacity-50" />
                    <input
                      autoFocus
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search…"
                      className="h-7 w-full bg-transparent text-sm outline-none"
                    />
                    <button
                      type="button"
                      title="Refresh"
                      onClick={() => void load(true)}
                      className="rounded p-1 hover:bg-muted"
                    >
                      <RefreshCw className="h-3 w-3 opacity-60" />
                    </button>
                  </div>
                  <div className="max-h-56 overflow-y-auto py-1">
                    {filtered.length === 0 ? (
                      <p className="px-3 py-4 text-center text-xs text-muted-foreground">
                        {items.length === 0 ? hint || 'Nothing found here yet.' : 'No matches.'}
                      </p>
                    ) : (
                      filtered.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => {
                            onChange(item.id)
                            setOpen(false)
                            setSearch('')
                          }}
                          className="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-muted"
                        >
                          <span className="truncate">{item.name}</span>
                          {item.id === value && (
                            <Check className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
                          )}
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {mode === 'url' && (
        <div className="space-y-1.5">
          <div className="flex gap-1.5">
            <div className="relative flex-1">
              <Link2 className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 opacity-50" />
              <input
                value={urlDraft}
                onChange={(e) => setUrlDraft(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void resolveUrl()}
                placeholder="Paste the link from your browser"
                className={`${INPUT_CLASS} pl-8`}
              />
            </div>
            <button
              type="button"
              onClick={() => void resolveUrl()}
              disabled={isResolvingUrl || !urlDraft.trim()}
              className="h-10 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {isResolvingUrl ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Use'}
            </button>
          </div>
          {urlError && <p className="text-xs text-destructive">{urlError}</p>}
          {value && !urlError && (
            <p className="text-xs text-muted-foreground">
              Currently set to <span className="font-mono">{value}</span>
            </p>
          )}
        </div>
      )}

      {mode === 'id' && (
        <div className="space-y-1.5">
          <input
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder="An ID, or an expression like {{steps.create.id}}"
            className={`${INPUT_CLASS} font-mono text-xs`}
          />
          <p className="text-xs text-muted-foreground">
            Leave blank to use this connection&apos;s default.
          </p>
        </div>
      )}
    </div>
  )
}
