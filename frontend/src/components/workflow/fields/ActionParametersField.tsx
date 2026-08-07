'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

import { ExpressionInput, type DataPath } from './ExpressionInput'
import { KeyValueField } from './KeyValueField'
import { ResourceLocator } from './ResourceLocator'

/**
 * Renders an integration action's parameters as real, typed fields.
 *
 * Previously every action showed the same generic key/value editor: the author
 * had to know that "Create Trello Card" wanted a key called `list_id`, and
 * then go and find the id to put in it. The backend has always described these
 * parameters properly — names, types, which are required — so this reads that
 * schema and builds the form from it.
 *
 * Parameters marked `x-resource` become a {@link ResourceLocator}: a dropdown
 * of names, a paste-a-link box, or a raw id. Everything else is an expression
 * input, so `{{steps.previous.value}}` still works anywhere.
 *
 * If the schema cannot be loaded — an unknown connector, an offline backend —
 * it falls back to the old key/value editor rather than blocking the user.
 */

interface ParamSpec {
  type?: string
  title?: string
  description?: string
  'x-resource'?: string
  'x-depends-on'?: string
  'x-ui-only'?: boolean
  'x-runtime'?: boolean
}

interface ActionSchema {
  action: string
  label?: string
  description?: string
  parameters?: {
    properties?: Record<string, ParamSpec>
    required?: string[]
  }
}

export function ActionParametersField({
  value,
  connectionId,
  action,
  dataPaths,
  onChange,
}: {
  value: Record<string, any> | undefined
  connectionId?: string
  action?: string
  dataPaths: DataPath[]
  onChange: (value: Record<string, any>) => void
}) {
  const [schemas, setSchemas] = useState<ActionSchema[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!connectionId) {
      setSchemas(null)
      return
    }
    let cancelled = false
    setIsLoading(true)
    apiClient
      .get<{ actions: ActionSchema[] }>(
        API_ENDPOINTS.INTEGRATION_CONNECTION_ACTIONS(connectionId),
      )
      .then((res) => !cancelled && setSchemas(res.data.actions ?? []))
      .catch(() => !cancelled && setSchemas(null))
      .finally(() => !cancelled && setIsLoading(false))
    return () => {
      cancelled = true
    }
  }, [connectionId])

  const schema = useMemo(
    () => schemas?.find((s) => s.action === action),
    [schemas, action],
  )

  const params = value ?? {}
  const set = (name: string, next: any) => onChange({ ...params, [name]: next })

  // Changing a step's action leaves the previous action's fields behind in the
  // same parameters object — switch "Create Trello Card" to "Comment on Trello
  // Card" and `board_id` is still in there, invisible, because the form only
  // renders the new action's fields. At run time the connector is called with
  // every key, and one it does not declare is a hard TypeError. So once the
  // schema for the *current* action is known, drop what it does not describe.
  // Only when the schema is actually loaded: with no schema the generic
  // key/value editor is in charge and every key is meaningful.
  const stale = useMemo(() => {
    const properties = schema?.parameters?.properties
    if (!properties) return []
    return Object.keys(params).filter((key) => !(key in properties))
  }, [schema, params])

  // Keyed on the names, not the array, so a fresh `params` object identity on
  // every render cannot turn this into a render loop.
  const staleKey = stale.join(',')
  useEffect(() => {
    if (!staleKey) return
    const pruned = { ...params }
    staleKey.split(',').forEach((key) => delete pruned[key])
    onChange(pruned)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [staleKey])

  if (!action) {
    return <p className="text-xs text-muted-foreground">Choose an action first.</p>
  }

  if (isLoading) {
    return (
      <div className="flex h-10 items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading parameters…
      </div>
    )
  }

  // No schema for this action: keep the generic editor so nothing is
  // unreachable just because the registry has not caught up.
  const properties = schema?.parameters?.properties
  if (!properties || Object.keys(properties).length === 0) {
    return <KeyValueField value={value} onChange={onChange} />
  }

  const required = new Set(schema?.parameters?.required ?? [])

  return (
    <div className="space-y-3.5">
      {Object.entries(properties).map(([name, spec]) => {
        const label = spec.title ?? name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
        const resourceKind = spec['x-resource']
        const dependsOn = spec['x-depends-on']

        return (
          <div key={name} className="space-y-1.5">
            <label className="block text-xs font-medium" htmlFor={`param-${name}`}>
              {label}
              {required.has(name) && <span className="ml-0.5 text-destructive">*</span>}
              {spec['x-ui-only'] && (
                <span className="ml-1.5 font-normal text-muted-foreground">
                  (used to find the next field)
                </span>
              )}
            </label>

            {resourceKind ? (
              <ResourceLocator
                id={`param-${name}`}
                kind={resourceKind}
                value={(params[name] as string) ?? ''}
                connectionId={connectionId}
                parentValue={dependsOn ? (params[dependsOn] as string) : undefined}
                parentLabel={dependsOn ? properties[dependsOn]?.title : undefined}
                onChange={(next) => set(name, next)}
              />
            ) : (
              <ExpressionInput
                id={`param-${name}`}
                multiline={name === 'description' || name === 'message' || name === 'content'}
                value={(params[name] as string) ?? ''}
                placeholder={spec.description}
                dataPaths={dataPaths}
                onChange={(next) => set(name, next)}
              />
            )}

            {spec.description && !resourceKind && (
              <p className="text-[11px] text-muted-foreground">{spec.description}</p>
            )}
            {spec['x-runtime'] && (
              <p className="text-[11px] text-muted-foreground">
                Usually comes from an earlier step, e.g.{' '}
                <span className="font-mono">{'{{steps.create_card.id}}'}</span>
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
