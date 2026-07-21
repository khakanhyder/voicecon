'use client'

import { Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'

export interface WorkflowInput {
  name: string
  type?: string
  description?: string
  required?: boolean
}

const TYPES = ['string', 'number', 'boolean']

/**
 * Declares the inputs a workflow expects.
 *
 * These become the parameter schema when the workflow is exposed to a voice
 * agent as a tool — the description is what the model uses to decide what to
 * extract from the caller, so it is worth writing properly.
 */
export function InputsField({
  value,
  onChange,
}: {
  value: WorkflowInput[] | undefined
  onChange: (value: WorkflowInput[]) => void
}) {
  const inputs = value || []

  const update = (index: number, patch: Partial<WorkflowInput>) => {
    onChange(inputs.map((v, i) => (i === index ? { ...v, ...patch } : v)))
  }

  const remove = (index: number) => onChange(inputs.filter((_, i) => i !== index))

  const add = () =>
    onChange([
      ...inputs,
      { name: '', type: 'string', description: '', required: true },
    ])

  return (
    <div className="space-y-3">
      {inputs.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No inputs. Add one to let a voice agent call this workflow with
          parameters.
        </p>
      )}

      {inputs.map((input, index) => (
        <div key={index} className="space-y-1.5 rounded-md border p-2.5">
          <div className="flex items-center gap-1.5">
            <Input
              value={input.name}
              placeholder="customer_name"
              onChange={(e) => update(index, { name: e.target.value })}
              className="h-8 flex-1 font-mono text-xs"
            />
            <select
              value={input.type ?? 'string'}
              onChange={(e) => update(index, { type: e.target.value })}
              className="h-8 w-24 rounded-md border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            >
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => remove(index)}
              title="Remove input"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <Input
            value={input.description ?? ''}
            placeholder="The customer's full name"
            onChange={(e) => update(index, { description: e.target.value })}
            className="h-8 text-xs"
          />

          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={input.required ?? false}
              onChange={(e) => update(index, { required: e.target.checked })}
              className="h-3.5 w-3.5 rounded border"
            />
            Required
          </label>
        </div>
      ))}

      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:border-primary hover:text-primary"
      >
        <Plus className="h-3.5 w-3.5" />
        Add input
      </button>
    </div>
  )
}
