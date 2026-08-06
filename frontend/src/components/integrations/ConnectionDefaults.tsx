'use client'

import { useEffect, useState } from 'react'
import { Check, Loader2, Settings2 } from 'lucide-react'
import { toast } from 'sonner'

import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { ResourceLocator } from '@/components/workflow/fields/ResourceLocator'

/**
 * Asks once where this connection should send things, and remembers.
 *
 * This is the part that makes resource pickers invisible for most people. A
 * customer with a single Trello board answers "which list should cards go to?"
 * here, and no workflow they build afterwards ever asks again — every action
 * that leaves the field blank falls back to what was chosen here.
 *
 * It also means moving the team's cards to a different list is one change in
 * one place, instead of an edit to every workflow that ever created one.
 */

interface Ask {
  kind: string
  key: string
  prompt: string
}

interface DefaultsPayload {
  connector_name: string
  defaults: Record<string, string>
  asks: Ask[]
}

export function ConnectionDefaults({
  connectionId,
  onSaved,
}: {
  connectionId: string
  onSaved?: () => void
}) {
  const [payload, setPayload] = useState<DefaultsPayload | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    apiClient
      .get<DefaultsPayload>(API_ENDPOINTS.INTEGRATION_CONNECTION_DEFAULTS(connectionId))
      .then((res) => {
        if (cancelled) return
        setPayload(res.data)
        setDraft(res.data.defaults ?? {})
      })
      .catch(() => !cancelled && setPayload(null))
      .finally(() => !cancelled && setIsLoading(false))
    return () => {
      cancelled = true
    }
  }, [connectionId])

  async function save() {
    setIsSaving(true)
    try {
      await apiClient.put(API_ENDPOINTS.INTEGRATION_CONNECTION_DEFAULTS(connectionId), {
        defaults: draft,
      })
      toast.success('Saved. Workflows will use this unless they say otherwise.')
      onSaved?.()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Could not save')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading…
      </div>
    )
  }

  // Nothing configurable for this connector — say so rather than showing an
  // empty panel that looks broken.
  if (!payload || payload.asks.length === 0) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        {payload?.connector_name ?? 'This integration'} has nothing to preset — actions
        carry everything they need.
      </p>
    )
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-start gap-2">
        <Settings2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">Where things go by default</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Set this once and your workflows won&apos;t have to ask. Any workflow can
            still override it.
          </p>
        </div>
      </div>

      {payload.asks.map((ask, index) => {
        // A nested resource reads its parent from the answer above it, so
        // choosing a board immediately narrows the list dropdown beneath it.
        const parentAsk = index > 0 ? payload.asks[index - 1] : undefined
        return (
          <div key={ask.key} className="space-y-1.5">
            <label className="block text-xs font-medium">{ask.prompt}</label>
            <ResourceLocator
              id={`default-${ask.key}`}
              kind={ask.kind}
              connectionId={connectionId}
              value={draft[ask.key] ?? ''}
              parentValue={parentAsk ? draft[parentAsk.key] : undefined}
              parentLabel={parentAsk?.kind.replace(/s$/, '')}
              onChange={(next) => setDraft((d) => ({ ...d, [ask.key]: next }))}
            />
          </div>
        )
      })}

      <button
        type="button"
        onClick={() => void save()}
        disabled={isSaving}
        className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
      >
        {isSaving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Check className="h-3.5 w-3.5" />
        )}
        Save defaults
      </button>
    </div>
  )
}
