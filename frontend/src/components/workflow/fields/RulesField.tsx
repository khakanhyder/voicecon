'use client'

import { Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'

export interface Rule {
  label?: string
  variable?: string
  operator?: string
  value?: string
}

const OPERATORS = [
  { value: 'equals', label: 'equals' },
  { value: 'not_equals', label: 'does not equal' },
  { value: 'contains', label: 'contains' },
  { value: 'starts_with', label: 'starts with' },
  { value: 'greater_than', label: 'is greater than' },
  { value: 'less_than', label: 'is less than' },
  { value: 'is_empty', label: 'is empty' },
  { value: 'is_not_empty', label: 'is not empty' },
]

const NO_VALUE = new Set(['is_empty', 'is_not_empty'])

/**
 * Ordered rule list for the Switch node.
 *
 * Each rule adds an output handle to the node; the first match wins at
 * runtime, and anything unmatched leaves through "else".
 */
export function RulesField({
  value,
  onChange,
}: {
  value: Rule[] | undefined
  onChange: (value: Rule[]) => void
}) {
  const rules = value || []

  const update = (index: number, patch: Partial<Rule>) => {
    onChange(rules.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }

  const remove = (index: number) => {
    onChange(rules.filter((_, i) => i !== index))
  }

  const add = () => {
    onChange([
      ...rules,
      { label: `Rule ${rules.length + 1}`, operator: 'equals', variable: '', value: '' },
    ])
  }

  return (
    <div className="space-y-3">
      {rules.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No rules yet. Everything will take the “else” output.
        </p>
      )}

      {rules.map((rule, index) => (
        <div key={index} className="space-y-1.5 rounded-md border p-2.5">
          <div className="flex items-center gap-1.5">
            <Input
              value={rule.label ?? ''}
              placeholder={`Rule ${index + 1}`}
              onChange={(e) => update(index, { label: e.target.value })}
              className="h-8 flex-1 text-xs font-medium"
            />
            <button
              type="button"
              onClick={() => remove(index)}
              title="Remove rule"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <Input
            value={rule.variable ?? ''}
            placeholder="trigger.plan"
            onChange={(e) => update(index, { variable: e.target.value })}
            className="h-8 text-xs"
          />

          <div className="flex gap-1.5">
            <select
              value={rule.operator ?? 'equals'}
              onChange={(e) => update(index, { operator: e.target.value })}
              className="h-8 flex-1 rounded-md border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            >
              {OPERATORS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </select>

            {!NO_VALUE.has(rule.operator ?? 'equals') && (
              <Input
                value={rule.value ?? ''}
                placeholder="value"
                onChange={(e) => update(index, { value: e.target.value })}
                className="h-8 flex-1 text-xs"
              />
            )}
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:border-primary hover:text-primary"
      >
        <Plus className="h-3.5 w-3.5" />
        Add rule
      </button>
    </div>
  )
}
