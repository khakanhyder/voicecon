'use client'

import { Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'

export interface Calculation {
  name?: string
  left?: string
  operator?: string
  right?: string
}

const OPERATORS = [
  { value: 'add', label: '+' },
  { value: 'subtract', label: '−' },
  { value: 'multiply', label: '×' },
  { value: 'divide', label: '÷' },
  { value: 'modulo', label: 'remainder' },
  { value: 'percent_of', label: '% of' },
]

/**
 * Ordered calculation list for the Calculate node.
 *
 * Rows run top to bottom and each result is published straight away, so a later
 * row can use an earlier one by name — subtotal, then tax, then total, in one
 * node rather than three.
 */
export function CalculationsField({
  value,
  onChange,
}: {
  value: Calculation[] | undefined
  onChange: (value: Calculation[]) => void
}) {
  const rows = value || []

  const update = (index: number, patch: Partial<Calculation>) => {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }

  const remove = (index: number) => {
    onChange(rows.filter((_, i) => i !== index))
  }

  const add = () => {
    onChange([
      ...rows,
      { name: `result_${rows.length + 1}`, left: '', operator: 'add', right: '' },
    ])
  }

  return (
    <div className="space-y-3">
      {rows.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No calculations yet. Each result becomes available to later steps by name.
        </p>
      )}

      {rows.map((row, index) => (
        <div key={index} className="space-y-1.5 rounded-md border p-2.5">
          <div className="flex items-center gap-1.5">
            <Input
              value={row.name ?? ''}
              placeholder="total"
              onChange={(e) => update(index, { name: e.target.value })}
              className="h-8 flex-1 text-xs font-medium"
            />
            <button
              type="button"
              onClick={() => remove(index)}
              title="Remove calculation"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="flex items-center gap-1.5">
            <Input
              value={row.left ?? ''}
              placeholder="{{price}}"
              onChange={(e) => update(index, { left: e.target.value })}
              className="h-8 flex-1 text-xs"
            />

            <select
              value={row.operator ?? 'add'}
              onChange={(e) => update(index, { operator: e.target.value })}
              className="h-8 w-24 shrink-0 rounded-md border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            >
              {OPERATORS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </select>

            <Input
              value={row.right ?? ''}
              placeholder="{{quantity}}"
              onChange={(e) => update(index, { right: e.target.value })}
              className="h-8 flex-1 text-xs"
            />
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:border-primary hover:text-primary"
      >
        <Plus className="h-3.5 w-3.5" />
        Add calculation
      </button>
    </div>
  )
}
