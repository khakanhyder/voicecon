'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

interface Connection {
  id: string
  name: string
  connector_name?: string
  status?: string
}

interface ConnectorAction {
  name: string
  description?: string
}

const SELECT_CLASS =
  'h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60'

/**
 * Picks one of the organization's connected integrations.
 *
 * The 22 connectors the backend can execute are only reachable from the
 * builder through this field.
 */
export function ConnectionField({
  id,
  value,
  onChange,
}: {
  id: string
  value: string
  onChange: (value: string) => void
}) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    apiClient
      .get<{ connections: Connection[] }>(API_ENDPOINTS.INTEGRATION_CONNECTIONS)
      .then((res) => {
        if (!cancelled) setConnections(res.data.connections ?? [])
      })
      .catch(() => {
        if (!cancelled) setError('Could not load connections')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (isLoading) {
    return (
      <div className="flex h-10 items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading connections…
      </div>
    )
  }

  if (error) return <p className="text-sm text-destructive">{error}</p>

  if (connections.length === 0) {
    return (
      <p className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
        No apps connected yet. Connect one in Integrations, then pick it here.
      </p>
    )
  }

  return (
    <select
      id={id}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className={SELECT_CLASS}
    >
      <option value="">Select a connection…</option>
      {connections.map((connection) => (
        <option key={connection.id} value={connection.id}>
          {connection.name}
          {connection.connector_name ? ` (${connection.connector_name})` : ''}
        </option>
      ))}
    </select>
  )
}

/**
 * Picks an action available on the chosen connection.
 *
 * Options are refetched whenever the connection changes, and the current
 * selection is cleared if it is not valid for the new connector.
 */
export function ConnectionActionField({
  id,
  value,
  connectionId,
  onChange,
}: {
  id: string
  value: string
  connectionId?: string
  onChange: (value: string) => void
}) {
  const [actions, setActions] = useState<ConnectorAction[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!connectionId) {
      setActions([])
      return
    }

    let cancelled = false
    setIsLoading(true)

    apiClient
      .get<{ actions: ConnectorAction[] }>(
        API_ENDPOINTS.INTEGRATION_CONNECTION_ACTIONS(connectionId)
      )
      .then((res) => {
        if (cancelled) return
        const list = res.data.actions ?? []
        setActions(list)
        // Switching connectors invalidates an action from the old one.
        if (value && !list.some((a) => a.name === value)) onChange('')
      })
      .catch(() => {
        if (!cancelled) setActions([])
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
    // `value`/`onChange` intentionally omitted: refetch only on connection change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId])

  if (!connectionId) {
    return (
      <p className="text-xs text-muted-foreground">Choose a connection first.</p>
    )
  }

  if (isLoading) {
    return (
      <div className="flex h-10 items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading actions…
      </div>
    )
  }

  if (actions.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No actions available for this connection.
      </p>
    )
  }

  return (
    <select
      id={id}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className={SELECT_CLASS}
    >
      <option value="">Select an action…</option>
      {actions.map((action) => (
        <option key={action.name} value={action.name}>
          {action.description ? `${action.name} — ${action.description}` : action.name}
        </option>
      ))}
    </select>
  )
}
