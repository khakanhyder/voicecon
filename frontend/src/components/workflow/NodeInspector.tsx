'use client'

import { useState } from 'react'
import { Copy, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  getDescriptor,
  isFieldVisible,
  type FieldDescriptor,
} from '@/lib/workflow/nodeTypes'
import type { FlowNode, NodeSettings } from '@/lib/workflow/graph'
import { ConnectionActionField, ConnectionField } from './fields/ConnectionFields'
import { KeyValueField } from './fields/KeyValueField'
import { RulesField } from './fields/RulesField'
import { InputsField } from './fields/InputsField'
import dynamic from 'next/dynamic'
const CodeEditor = dynamic(
  () => import('./fields/CodeEditor').then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className="h-[240px] rounded-md border bg-muted/40" /> }
)
import {
  DataPicker,
  ExpressionInput,
  type DataPath,
} from './fields/ExpressionInput'
import { cn } from '@/lib/utils'

// Starter snippets, kept in sync with the Python default in the descriptor.
const PY_STARTER =
  '# `input` holds trigger, steps and vars.\n'
  + '# Return data by assigning `result`.\n'
  + 'result = {\n'
  + '    "example": input["trigger"],\n'
  + '}\n'

const JS_STARTER =
  '// `input` holds trigger, steps and vars.\n'
  + '// Return data by assigning `result`.\n'
  + 'result = {\n'
  + '  example: input.trigger,\n'
  + '}\n'

interface NodeInspectorProps {
  node: FlowNode
  onChangeName: (name: string) => void
  onChangeConfig: (config: Record<string, any>) => void
  onChangeSettings: (settings: NodeSettings) => void
  /** Values this node may reference, for autocomplete and the data picker. */
  dataPaths: DataPath[]
  onDuplicate: () => void
  onDelete: () => void
  onClose: () => void
}

/**
 * Configuration panel for the selected node.
 *
 * Fields are rendered from the type descriptor, so this component never needs
 * a per-type branch.
 */
export function NodeInspector({
  node,
  onChangeName,
  onChangeConfig,
  onChangeSettings,
  dataPaths,
  onDuplicate,
  onDelete,
  onClose,
}: NodeInspectorProps) {
  const [tab, setTab] = useState<'parameters' | 'settings'>('parameters')
  const descriptor = getDescriptor(node.data.nodeType)
  const config = node.data.config || {}
  const settings = node.data.settings || {}
  const isTrigger = node.data.nodeType === 'trigger'

  const setField = (name: string, value: unknown) => {
    const next = { ...config, [name]: value }

    // When the Code node's language changes and the editor still holds the
    // untouched starter snippet, swap it for the other language's starter so a
    // JavaScript user doesn't stare at Python (and vice versa).
    if (name === 'language' && node.data.nodeType === 'code') {
      const current = String(config.code ?? '').trim()
      if (!current || current === PY_STARTER.trim() || current === JS_STARTER.trim()) {
        next.code = value === 'javascript' ? JS_STARTER : PY_STARTER
      }
    }

    onChangeConfig(next)
  }

  return (
    <aside className="flex w-[360px] shrink-0 flex-col border-l bg-card">
      <div className="flex items-start justify-between gap-2 border-b p-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{descriptor.label}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {descriptor.description}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground hover:bg-accent"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {!isTrigger && (
        <div className="flex gap-1 border-b px-3 py-2">
          {(['parameters', 'settings'] as const).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors',
                tab === key
                  ? 'bg-accent text-foreground'
                  : 'text-muted-foreground hover:bg-accent/60'
              )}
            >
              {key}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {tab === 'parameters' || isTrigger ? (
          <>
            <div className="space-y-2">
              <Label htmlFor="node-name">Step name</Label>
              <Input
                id="node-name"
                value={node.data.label}
                onChange={(e) => onChangeName(e.target.value)}
              />
            </div>

            {descriptor.fields
              .filter((field) => isFieldVisible(field, config))
              .map((field) => (
                <FieldControl
                  key={field.name}
                  field={field}
                  value={config[field.name]}
                  dependsOnValue={
                    field.dependsOn ? config[field.dependsOn] : undefined
                  }
                  dataPaths={dataPaths}
                  onChange={(value) => setField(field.name, value)}
                />
              ))}

            {descriptor.fields.length > 0 && dataPaths.length > 0 && (
              <DataPicker
                dataPaths={dataPaths}
                onPick={(path) => {
                  // Append to the first expression-capable field so a picked
                  // value always lands somewhere visible.
                  const target = descriptor.fields.find((f) =>
                    ['text', 'textarea'].includes(f.type)
                  )
                  if (!target) return
                  const current = String(config[target.name] ?? '')
                  setField(target.name, `${current}{{${path}}}`)
                }}
              />
            )}

            {isTrigger && (
              <p className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                How this workflow is triggered (webhook, schedule, call ended)
                is set in the workflow settings.
              </p>
            )}
          </>
        ) : (
          <SettingsTab settings={settings} onChange={onChangeSettings} />
        )}
      </div>

      {!isTrigger && (
        <div className="space-y-2 border-t p-4">
          <Button variant="outline" className="w-full" onClick={onDuplicate}>
            <Copy className="mr-2 h-4 w-4" />
            Duplicate step
          </Button>
          <Button variant="destructive" className="w-full" onClick={onDelete}>
            <Trash2 className="mr-2 h-4 w-4" />
            Delete step
          </Button>
        </div>
      )}
    </aside>
  )
}

/**
 * Per-node execution settings.
 *
 * These override the workflow-wide defaults, so a single flaky HTTP call can
 * retry without forcing the whole workflow to continue-on-error.
 */
function SettingsTab({
  settings,
  onChange,
}: {
  settings: NodeSettings
  onChange: (settings: NodeSettings) => void
}) {
  const retry = settings.retry || {}

  const setRetry = (patch: Partial<NonNullable<NodeSettings['retry']>>) =>
    onChange({ ...settings, retry: { ...retry, ...patch } })

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="on-error">If this step fails</Label>
        <select
          id="on-error"
          value={settings.on_error ?? ''}
          onChange={(e) =>
            onChange({
              ...settings,
              on_error: (e.target.value || undefined) as NodeSettings['on_error'],
            })
          }
          className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">Use workflow default</option>
          <option value="stop">Stop the workflow</option>
          <option value="continue">Continue to the next step</option>
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="timeout">Timeout (seconds)</Label>
        <Input
          id="timeout"
          type="number"
          min={0}
          placeholder="No timeout"
          value={settings.timeout_seconds ?? ''}
          onChange={(e) =>
            onChange({
              ...settings,
              timeout_seconds:
                e.target.value === '' ? undefined : Number(e.target.value),
            })
          }
        />
        <p className="text-[11px] text-muted-foreground">
          Stops a step that hangs instead of blocking the whole run.
        </p>
      </div>

      <div className="space-y-3 rounded-md border p-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={retry.enabled ?? false}
            onChange={(e) => setRetry({ enabled: e.target.checked })}
            className="h-4 w-4 rounded border"
          />
          Retry on failure
        </label>

        {retry.enabled && (
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="max-tries" className="text-xs">
                Max retries
              </Label>
              <Input
                id="max-tries"
                type="number"
                min={0}
                value={retry.max_tries ?? 3}
                onChange={(e) => setRetry({ max_tries: Number(e.target.value) })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="retry-delay" className="text-xs">
                Delay (s)
              </Label>
              <Input
                id="retry-delay"
                type="number"
                min={0}
                value={retry.delay_seconds ?? 5}
                onChange={(e) =>
                  setRetry({ delay_seconds: Number(e.target.value) })
                }
              />
            </div>
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="backoff" className="text-xs">
                Backoff
              </Label>
              <select
                id="backoff"
                value={retry.backoff ?? 'fixed'}
                onChange={(e) =>
                  setRetry({
                    backoff: e.target.value as 'fixed' | 'exponential',
                  })
                }
                className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="fixed">Fixed delay</option>
                <option value="exponential">Exponential backoff</option>
              </select>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function FieldControl({
  field,
  value,
  dependsOnValue,
  dataPaths,
  onChange,
}: {
  field: FieldDescriptor
  value: unknown
  dependsOnValue?: unknown
  dataPaths: DataPath[]
  onChange: (value: unknown) => void
}) {
  const id = `field-${field.name}`

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {field.label}
        {field.required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>

      {field.type === 'connection' ? (
        <ConnectionField
          id={id}
          value={(value as string) ?? ''}
          onChange={onChange}
        />
      ) : field.type === 'connectionAction' ? (
        <ConnectionActionField
          id={id}
          value={(value as string) ?? ''}
          connectionId={dependsOnValue as string | undefined}
          onChange={onChange}
        />
      ) : field.type === 'keyValue' ? (
        <KeyValueField
          value={value as Record<string, any> | undefined}
          onChange={onChange}
        />
      ) : field.type === 'rules' ? (
        <RulesField value={value as any} onChange={onChange} />
      ) : field.type === 'inputs' ? (
        <InputsField value={value as any} onChange={onChange} />
      ) : field.type === 'code' ? (
        <CodeEditor
          value={(value as string) ?? ''}
          language={(dependsOnValue as string) || 'python'}
          onChange={onChange}
        />
      ) : field.type === 'textarea' ? (
        <ExpressionInput
          id={id}
          multiline
          value={(value as string) ?? ''}
          placeholder={field.placeholder}
          dataPaths={dataPaths}
          onChange={onChange}
        />
      ) : field.type === 'text' ? (
        <ExpressionInput
          id={id}
          value={(value as string) ?? ''}
          placeholder={field.placeholder}
          dataPaths={dataPaths}
          onChange={onChange}
        />
      ) : field.type === 'json' ? (
        <Textarea
          id={id}
          rows={field.type === 'json' ? 4 : 3}
          className={field.type === 'json' ? 'font-mono text-xs' : undefined}
          value={(value as string) ?? ''}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : field.type === 'select' ? (
        <select
          id={id}
          value={(value as string) ?? field.default ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
        >
          {field.options?.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : field.type === 'number' ? (
        <Input
          id={id}
          type="number"
          value={(value as number) ?? ''}
          placeholder={field.placeholder}
          onChange={(e) =>
            onChange(e.target.value === '' ? '' : Number(e.target.value))
          }
        />
      ) : (
        <Input
          id={id}
          value={(value as string) ?? ''}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {field.help && (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {field.help}
        </p>
      )}
    </div>
  )
}
