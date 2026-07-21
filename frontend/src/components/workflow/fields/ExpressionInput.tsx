'use client'

import { useMemo, useRef, useState } from 'react'
import { Braces, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FlowNode } from '@/lib/workflow/graph'

export interface DataPath {
  path: string
  label: string
  hint?: string
}

/**
 * Build the list of values a node can reference.
 *
 * Sources, in the order a user thinks about them:
 *   - the trigger payload
 *   - variables published by upstream Ask / AI / Set Fields steps
 *   - each upstream step's raw output under steps.<id>
 *   - loop variables, when the node sits inside a loop body
 */
export function buildDataPaths(
  nodes: FlowNode[],
  currentNodeId: string,
  insideLoop: boolean
): DataPath[] {
  const paths: DataPath[] = [
    { path: 'trigger', label: 'trigger', hint: 'The whole trigger payload' },
  ]

  if (insideLoop) {
    paths.push(
      { path: 'loop.item', label: 'loop.item', hint: 'Current item' },
      { path: 'loop.index', label: 'loop.index', hint: 'Zero-based position' },
      { path: 'loop.length', label: 'loop.length', hint: 'Total items' }
    )
  }

  for (const node of nodes) {
    if (node.id === currentNodeId || node.data.nodeType === 'trigger') continue

    const config = node.data.config || {}

    // Ask and AI steps publish their answer at the top level.
    if (typeof config.variable === 'string' && config.variable.trim()) {
      paths.push({
        path: config.variable.trim(),
        label: config.variable.trim(),
        hint: `From "${node.data.label}"`,
      })
    }

    // Set Fields publishes one variable per configured field.
    if (node.data.nodeType === 'transform') {
      for (const key of Object.keys(config.transformations || {})) {
        paths.push({ path: key, label: key, hint: `From "${node.data.label}"` })
      }
    }

    paths.push({
      path: `steps.${node.id}`,
      label: `steps.${node.id}`,
      hint: `Raw output of "${node.data.label}"`,
    })
  }

  return paths
}

/**
 * Text input that understands `{{ }}` references.
 *
 * Typing `{{` opens a filtered list of available values; picking one inserts
 * the reference at the cursor. Previously these were plain inputs, so the only
 * way to know what could be referenced was to guess.
 */
export function ExpressionInput({
  id,
  value,
  placeholder,
  multiline,
  dataPaths,
  onChange,
}: {
  id: string
  value: string
  placeholder?: string
  multiline?: boolean
  dataPaths: DataPath[]
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null)

  const matches = useMemo(() => {
    const term = query.trim().toLowerCase()
    const list = term
      ? dataPaths.filter((p) => p.label.toLowerCase().includes(term))
      : dataPaths
    return list.slice(0, 8)
  }, [dataPaths, query])

  const handleChange = (next: string) => {
    onChange(next)

    // Open the picker while the caret sits in an unterminated `{{`.
    const caret = ref.current?.selectionStart ?? next.length
    const before = next.slice(0, caret)
    const opened = before.lastIndexOf('{{')
    const closed = before.lastIndexOf('}}')

    if (opened > closed) {
      setQuery(before.slice(opened + 2).trim())
      setOpen(true)
    } else {
      setOpen(false)
    }
  }

  const insert = (path: string) => {
    const el = ref.current
    const caret = el?.selectionStart ?? value.length
    const before = value.slice(0, caret)
    const opened = before.lastIndexOf('{{')

    // Replace the partially typed reference rather than appending to it.
    const head = opened >= 0 ? value.slice(0, opened) : before
    const tail = value.slice(caret)
    const next = `${head}{{${path}}}${tail}`

    onChange(next)
    setOpen(false)

    // Restore focus with the caret after the inserted reference.
    window.requestAnimationFrame(() => {
      el?.focus()
      const position = head.length + path.length + 4
      el?.setSelectionRange(position, position)
    })
  }

  const shared = {
    id,
    ref,
    value: value ?? '',
    placeholder,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      handleChange(e.target.value),
    onBlur: () => window.setTimeout(() => setOpen(false), 150),
    className: cn(
      'w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30',
      multiline ? 'min-h-[76px] py-2' : 'h-10'
    ),
  }

  return (
    <div className="relative">
      {multiline ? (
        <textarea {...(shared as any)} rows={3} />
      ) : (
        <input {...(shared as any)} />
      )}

      {open && matches.length > 0 && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-md border bg-popover shadow-lg">
          <p className="border-b px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Insert value
          </p>
          {matches.map((match) => (
            <button
              key={match.path}
              type="button"
              // onMouseDown fires before the input's blur, so the click lands.
              onMouseDown={(e) => {
                e.preventDefault()
                insert(match.path)
              }}
              className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-accent"
            >
              <Braces className="h-3 w-3 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-xs">
                  {match.label}
                </span>
                {match.hint && (
                  <span className="block truncate text-[10px] text-muted-foreground">
                    {match.hint}
                  </span>
                )}
              </span>
              <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Browsable tree of every referenceable value.
 *
 * Complements the inline autocomplete for users who would rather look at what
 * is available than remember it.
 */
export function DataPicker({
  dataPaths,
  onPick,
}: {
  dataPaths: DataPath[]
  onPick: (path: string) => void
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-md border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-2.5 py-2 text-left text-xs font-medium hover:bg-accent"
      >
        <ChevronRight
          className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-90')}
        />
        Available data ({dataPaths.length})
      </button>

      {open && (
        <div className="max-h-44 overflow-y-auto border-t p-1">
          {dataPaths.map((path) => (
            <button
              key={path.path}
              type="button"
              onClick={() => onPick(path.path)}
              className="flex w-full flex-col rounded px-2 py-1 text-left hover:bg-accent"
            >
              <span className="truncate font-mono text-[11px]">{path.label}</span>
              {path.hint && (
                <span className="truncate text-[10px] text-muted-foreground">
                  {path.hint}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
