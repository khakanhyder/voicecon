'use client'

import { useMemo, useState } from 'react'
import {
  Clock,
  Braces,
  Filter as FilterIcon,
  GitBranch,
  GitMerge,
  Globe,
  MessageCircleQuestion,
  PhoneForwarded,
  PhoneOff,
  Plug,
  Play,
  Search,
  Repeat,
  Sparkles,
  Split,
  Volume2,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import {
  NODE_TYPES,
  PALETTE_CATEGORIES,
  type NodeDescriptor,
} from '@/lib/workflow/nodeTypes'
import { cn } from '@/lib/utils'

const ICONS: Record<string, LucideIcon> = {
  Play,
  Volume2,
  MessageCircleQuestion,
  GitBranch,
  PhoneForwarded,
  Wrench,
  Plug,
  Braces,
  Split,
  FilterIcon,
  GitMerge,
  Repeat,
  Globe,
  Sparkles,
  Clock,
  PhoneOff,
}

interface NodePaletteProps {
  /** Click-to-add, used when a drop target is implied (e.g. end of flow). */
  onAdd: (type: string) => void
}

/**
 * Searchable node palette.
 *
 * Nodes can be dragged onto the canvas or clicked to append. The drag payload
 * is the node type, read by the canvas's onDrop handler.
 */
export function NodePalette({ onAdd }: NodePaletteProps) {
  const [query, setQuery] = useState('')

  const grouped = useMemo(() => {
    const term = query.trim().toLowerCase()
    const result: { category: string; items: NodeDescriptor[] }[] = []

    for (const category of PALETTE_CATEGORIES) {
      const items = Object.values(NODE_TYPES).filter(
        (d) =>
          d.category === category &&
          d.type !== 'trigger' &&
          (!term ||
            d.label.toLowerCase().includes(term) ||
            d.description.toLowerCase().includes(term))
      )
      if (items.length) result.push({ category, items })
    }

    return result
  }, [query])

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r bg-card">
      <div className="border-b p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search steps…"
            className="h-9 w-full rounded-md border bg-background pl-8 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {grouped.length === 0 && (
          <p className="px-1 py-6 text-center text-sm text-muted-foreground">
            No steps match “{query}”
          </p>
        )}

        {grouped.map(({ category, items }) => (
          <div key={category} className="mb-4">
            <p className="mb-1.5 px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {category}
            </p>
            <div className="space-y-1">
              {items.map((descriptor) => {
                const Icon = ICONS[descriptor.icon] ?? Volume2
                return (
                  <button
                    key={descriptor.type}
                    type="button"
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('application/workflow-node', descriptor.type)
                      e.dataTransfer.effectAllowed = 'move'
                    }}
                    onClick={() => onAdd(descriptor.type)}
                    title={descriptor.description}
                    className={cn(
                      'flex w-full cursor-grab items-center gap-2.5 rounded-lg border border-transparent px-2 py-2 text-left transition-colors',
                      'hover:border-border hover:bg-accent active:cursor-grabbing'
                    )}
                  >
                    <span
                      className={cn(
                        'flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-white',
                        descriptor.accent
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {descriptor.label}
                      </span>
                      <span className="block truncate text-[11px] text-muted-foreground">
                        {descriptor.description}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t p-3">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Drag a step onto the canvas, or drag from a node&apos;s bottom dot to
          connect it.
        </p>
      </div>
    </aside>
  )
}
