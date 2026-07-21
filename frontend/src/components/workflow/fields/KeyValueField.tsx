'use client'

import { Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'

/**
 * Editable list of key -> value pairs.
 *
 * Replaces raw JSON textareas for parameters and field mappings: the old
 * builder shipped malformed JSON straight to the server with no feedback.
 */
export function KeyValueField({
  value,
  onChange,
  keyPlaceholder = 'name',
  valuePlaceholder = 'value or {{expression}}',
}: {
  value: Record<string, any> | undefined
  onChange: (value: Record<string, any>) => void
  keyPlaceholder?: string
  valuePlaceholder?: string
}) {
  const entries = Object.entries(value || {})

  const rename = (index: number, name: string) => {
    // Rebuild from the entry list so key order stays stable while typing.
    const next = entries.map(([k, v], i) => (i === index ? [name, v] : [k, v]))
    onChange(Object.fromEntries(next))
  }

  const setValue = (key: string, next: string) => {
    onChange({ ...(value || {}), [key]: next })
  }

  const remove = (key: string) => {
    const next = { ...(value || {}) }
    delete next[key]
    onChange(next)
  }

  const add = () => {
    const base = 'field'
    let name = base
    let n = 1
    while (name in (value || {})) name = `${base}_${++n}`
    onChange({ ...(value || {}), [name]: '' })
  }

  return (
    <div className="space-y-2">
      {entries.length === 0 && (
        <p className="text-xs text-muted-foreground">No fields yet.</p>
      )}

      {entries.map(([key, val], index) => (
        <div key={index} className="flex items-center gap-1.5">
          <Input
            value={key}
            placeholder={keyPlaceholder}
            onChange={(e) => rename(index, e.target.value)}
            className="h-9 flex-1 font-mono text-xs"
          />
          <Input
            value={typeof val === 'string' ? val : JSON.stringify(val)}
            placeholder={valuePlaceholder}
            onChange={(e) => setValue(key, e.target.value)}
            className="h-9 flex-[1.4] text-xs"
          />
          <button
            type="button"
            onClick={() => remove(key)}
            title="Remove field"
            className="flex h-9 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}

      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:border-primary hover:text-primary"
      >
        <Plus className="h-3.5 w-3.5" />
        Add field
      </button>
    </div>
  )
}
