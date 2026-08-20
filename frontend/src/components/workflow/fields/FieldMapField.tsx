'use client'

import { Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'

/** One step of a transform chain, as stored when a field has more than one. */
export interface ChainStep {
  name: string
  args?: string
}

/**
 * One computed field. A row is stored as a plain string when no transform is
 * chosen, so a workflow built before transforms existed round-trips unchanged.
 *
 * `transform` widens to a list only when a second transform is added, so a
 * single-transform field keeps the shape it has always had on disk.
 */
export interface FieldSpec {
  source?: string
  transform?: string | ChainStep[]
  args?: string
  default?: string
}

export type FieldMap = Record<string, string | FieldSpec>

interface TransformOption {
  value: string
  label: string
  /** Label for the argument box; absent means the transform takes no argument. */
  arg?: string
  argPlaceholder?: string
  group: string
}

/**
 * The transforms offered in the builder.
 *
 * Deliberately a subset of DataMapper's registry: every entry here takes at
 * most one argument that a non-technical user can be asked for in a single box.
 * Transforms whose argument is itself a mini-format are left out rather than
 * dressed up — they are the ones that would send someone looking for a code
 * editor, and the honest answer for those is a Webhook step.
 */
const TRANSFORMS: TransformOption[] = [
  { value: '', label: 'No transform — use as-is', group: '' },

  {
    value: 'sum',
    label: 'Sum of',
    arg: 'Field to add up',
    argPlaceholder: 'amount (leave blank for a plain number list)',
    group: 'Numbers',
  },
  {
    value: 'average',
    label: 'Average of',
    arg: 'Field to average',
    argPlaceholder: 'amount',
    group: 'Numbers',
  },
  {
    value: 'max_value',
    label: 'Largest of',
    arg: 'Field to compare',
    argPlaceholder: 'amount',
    group: 'Numbers',
  },
  {
    value: 'min_value',
    label: 'Smallest of',
    arg: 'Field to compare',
    argPlaceholder: 'amount',
    group: 'Numbers',
  },
  { value: 'round', label: 'Round', arg: 'Decimal places', argPlaceholder: '2', group: 'Numbers' },
  { value: 'floor', label: 'Round down', group: 'Numbers' },
  { value: 'ceil', label: 'Round up', group: 'Numbers' },
  { value: 'abs', label: 'Absolute value', group: 'Numbers' },

  {
    value: 'format_currency',
    label: 'Format as money',
    arg: 'Currency',
    argPlaceholder: 'USD',
    group: 'Formatting',
  },
  {
    value: 'format_number',
    label: 'Format as number',
    arg: 'Decimal places',
    argPlaceholder: '2',
    group: 'Formatting',
  },
  {
    value: 'format_date',
    label: 'Format as date',
    arg: 'Pattern',
    argPlaceholder: '%d %b %Y',
    group: 'Formatting',
  },
  {
    value: 'add_days',
    label: 'Add days to date',
    arg: 'Days',
    argPlaceholder: '7',
    group: 'Formatting',
  },
  {
    value: 'add_hours',
    label: 'Add hours to date',
    arg: 'Hours',
    argPlaceholder: '2',
    group: 'Formatting',
  },

  { value: 'uppercase', label: 'UPPERCASE', group: 'Text' },
  { value: 'lowercase', label: 'lowercase', group: 'Text' },
  { value: 'capitalize', label: 'Capitalise first letter', group: 'Text' },
  { value: 'title', label: 'Title Case', group: 'Text' },
  { value: 'trim', label: 'Remove extra spaces', group: 'Text' },
  {
    value: 'truncate',
    label: 'Shorten to',
    arg: 'Characters',
    argPlaceholder: '100',
    group: 'Text',
  },

  { value: 'count', label: 'Count items', group: 'Lists' },
  { value: 'array_first', label: 'First item', group: 'Lists' },
  { value: 'array_last', label: 'Last item', group: 'Lists' },
  {
    value: 'array_join',
    label: 'Join into text',
    arg: 'Separator',
    argPlaceholder: ', ',
    group: 'Lists',
  },
  {
    value: 'pluck',
    label: 'Extract field from each',
    arg: 'Field name',
    argPlaceholder: 'sku',
    group: 'Lists',
  },

  { value: 'to_int', label: 'To whole number', group: 'Convert' },
  { value: 'to_float', label: 'To decimal number', group: 'Convert' },
  { value: 'to_string', label: 'To text', group: 'Convert' },
]

const GROUPS = ['Numbers', 'Formatting', 'Text', 'Lists', 'Convert']

/** Transforms that move a date rather than present one. */
const DATE_TRANSFORMS = new Set(['add_days', 'add_hours'])

/** Transforms that turn a date into something readable. */
const DATE_PRESENTERS = new Set(['format_date', 'to_string'])

function optionFor(transform: string | undefined): TransformOption | undefined {
  return TRANSFORMS.find((t) => t.value === (transform || ''))
}

/** Read a row in either storage shape. */
function toSpec(value: string | FieldSpec): FieldSpec {
  return typeof value === 'string' ? { source: value } : value || {}
}

/**
 * A field's transforms as an ordered list, whichever way they were stored.
 *
 * Chains exist because one transform cannot both work a value out and present
 * it: Add hours hands back a date object, and it takes Format as date after it
 * to become something a caller can be told.
 */
export function chainOf(spec: FieldSpec): ChainStep[] {
  const raw = spec.transform
  if (!raw) return []
  if (typeof raw === 'string') return [{ name: raw, args: spec.args }]
  return raw.filter((step) => step && step.name)
}

/** Store a chain in the narrowest shape that holds it. */
export function fromChain(chain: ChainStep[]): Pick<FieldSpec, 'transform' | 'args'> {
  const steps = chain.filter((step) => step.name)
  if (steps.length === 0) return {}
  // One transform keeps the original two-key shape, so nothing that predates
  // chains is rewritten just by being opened.
  if (steps.length === 1) {
    return steps[0].args
      ? { transform: steps[0].name, args: steps[0].args }
      : { transform: steps[0].name }
  }
  return {
    transform: steps.map((step) =>
      step.args ? { name: step.name, args: step.args } : { name: step.name }
    ),
  }
}

/**
 * Editable list of computed fields for the Set Fields node.
 *
 * Each row is: a name, the value it comes from, and an optional transform with
 * one argument. This is what replaced the Code node — the arithmetic and
 * formatting people used to write Python for is reachable from two dropdowns.
 */
export function FieldMapField({
  value,
  onChange,
}: {
  value: FieldMap | undefined
  onChange: (value: FieldMap) => void
}) {
  const entries = Object.entries(value || {})

  const write = (next: [string, string | FieldSpec][]) => {
    onChange(Object.fromEntries(next))
  }

  const rename = (index: number, name: string) => {
    // Rebuild from the list so key order stays stable while typing.
    write(entries.map(([k, v], i) => (i === index ? [name, v] : [k, v])))
  }

  const update = (index: number, patch: Partial<FieldSpec>) => {
    write(
      entries.map(([k, v], i) => {
        if (i !== index) return [k, v]

        const spec = { ...toSpec(v), ...patch }

        // Collapse back to a plain string when there is nothing but a source.
        // Keeps untouched pre-existing workflows byte-identical on save.
        if (!spec.transform && !spec.default) return [k, spec.source ?? '']

        const clean: FieldSpec = { source: spec.source ?? '' }
        if (spec.transform) clean.transform = spec.transform
        if (spec.args) clean.args = spec.args
        if (spec.default) clean.default = spec.default
        return [k, clean]
      })
    )
  }

  /** Replace one position in a field's transform chain. */
  const setStep = (index: number, position: number, patch: Partial<ChainStep>) => {
    const chain = chainOf(toSpec(entries[index][1]))
    const next = [...chain]
    const current = next[position] ?? { name: '' }
    next[position] = { ...current, ...patch }

    // Clearing a transform drops its argument, and drops everything after it:
    // a chain with a hole in the middle is not a chain.
    if (patch.name === '') next.length = position
    else if (patch.name && patch.name !== current.name) next[position].args = ''

    // `args: undefined` from the spread would survive a JSON round trip as a
    // key, so rebuild through fromChain rather than patching in place.
    update(index, { transform: undefined, args: undefined, ...fromChain(next) })
  }

  const remove = (index: number) => {
    write(entries.filter((_, i) => i !== index))
  }

  const add = () => {
    write([...entries, [`field_${entries.length + 1}`, '']])
  }

  return (
    <div className="space-y-3">
      {entries.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No fields yet. Each field you add becomes available to later steps by name.
        </p>
      )}

      {entries.map(([name, raw], index) => {
        const spec = toSpec(raw)
        const chain = chainOf(spec)
        // One empty slot is offered after the last chosen transform, so a
        // second step is one click away and never more than that.
        const slots = [...chain, { name: '', args: '' }].slice(0, 3)

        return (
          <div key={index} className="space-y-1.5 rounded-md border p-2.5">
            <div className="flex items-center gap-1.5">
              <Input
                value={name}
                placeholder="total"
                onChange={(e) => rename(index, e.target.value)}
                className="h-8 flex-1 text-xs font-medium"
              />
              <button
                type="button"
                onClick={() => remove(index)}
                title="Remove field"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            <Input
              value={spec.source ?? ''}
              placeholder="value or {{trigger.orders}}"
              onChange={(e) => update(index, { source: e.target.value })}
              className="h-8 text-xs"
            />

            {slots.map((step, position) => {
              const option = optionFor(step.name)
              // The follow-on slot only appears once the one before it is set.
              if (position > 0 && !chain[position - 1]?.name) return null

              return (
                <div key={position} className="flex items-center gap-1.5">
                  {position > 0 && (
                    <span className="shrink-0 text-[11px] text-muted-foreground">
                      then
                    </span>
                  )}
                  <select
                    value={step.name}
                    onChange={(e) =>
                      // Dropping the transform drops its argument too, so a
                      // stale "amount" cannot ride along into an unrelated one.
                      setStep(index, position, { name: e.target.value })
                    }
                    className="h-8 flex-1 rounded-md border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    <option value="">
                      {position === 0 ? 'No transform — use as-is' : 'then… (optional)'}
                    </option>
                    {GROUPS.map((group) => (
                      <optgroup key={group} label={group}>
                        {TRANSFORMS.filter((t) => t.group === group).map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>

                  {option?.arg && (
                    <Input
                      value={step.args ?? ''}
                      placeholder={option.argPlaceholder ?? option.arg}
                      onChange={(e) => setStep(index, position, { args: e.target.value })}
                      className="h-8 flex-1 text-xs"
                      title={option.arg}
                    />
                  )}
                </div>
              )
            })}

            {chainOf(spec).some((step) => DATE_TRANSFORMS.has(step.name)) &&
              !DATE_PRESENTERS.has(chain[chain.length - 1]?.name ?? '') && (
                <p className="text-[11px] text-muted-foreground">
                  Add “Format as date” after this to choose how it reads.
                </p>
              )}
          </div>
        )
      })}

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
