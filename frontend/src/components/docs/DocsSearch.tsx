'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { CornerDownLeft, FileText, Hash, Search, X } from 'lucide-react'
import { searchDocs, type SearchEntry } from '@/lib/docs/navigation'
import { cn } from '@/lib/utils'

/**
 * Command-palette search over the docs index.
 *
 * The index is static and small (a few hundred entries), so search runs
 * synchronously on every keystroke with no debounce — debouncing here would
 * only add perceived lag to an operation that costs well under a millisecond.
 */
export function DocsSearch({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const [query, setQuery] = useState('')
  const [highlighted, setHighlighted] = useState(0)

  const results = useMemo(() => searchDocs(query, 10), [query])

  // Reset between openings so the palette never reopens onto a stale query.
  useEffect(() => {
    if (open) {
      setQuery('')
      setHighlighted(0)
      // Focus after paint; focusing during the same tick loses to the
      // browser's own focus restoration when the dialog mounts.
      const raf = requestAnimationFrame(() => inputRef.current?.focus())
      return () => cancelAnimationFrame(raf)
    }
  }, [open])

  // A new query invalidates the previous highlight position.
  useEffect(() => {
    setHighlighted(0)
  }, [query])

  const go = useCallback(
    (entry: SearchEntry) => {
      onOpenChange(false)
      router.push(entry.href)
    },
    [onOpenChange, router]
  )

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      onOpenChange(false)
      return
    }
    if (results.length === 0) return

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlighted((current) => (current + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlighted((current) => (current - 1 + results.length) % results.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      go(results[highlighted])
    }
  }

  // Keep the highlighted row in view during keyboard navigation.
  useEffect(() => {
    const active = listRef.current?.children[highlighted] as HTMLElement | undefined
    active?.scrollIntoView({ block: 'nearest' })
  }, [highlighted])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-slate-900/40 px-4 pt-[12vh] backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="Search documentation"
      onMouseDown={(event) => {
        // Only a click on the backdrop itself dismisses — mousedown inside the
        // panel that drifts onto the backdrop should not close the palette.
        if (event.target === event.currentTarget) onOpenChange(false)
      }}
    >
      <div className="w-full max-w-[600px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center gap-3 border-b border-slate-200 px-4">
          <Search className="h-[18px] w-[18px] flex-shrink-0 text-slate-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search the documentation…"
            className="h-14 w-full border-0 bg-transparent p-0 text-[15px] text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:ring-0"
          />
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Close search"
            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[52vh] overflow-y-auto">
          {query.trim() === '' ? (
            <p className="px-4 py-8 text-center text-[14px] text-slate-400">
              Start typing to search across every page.
            </p>
          ) : results.length === 0 ? (
            <p className="px-4 py-8 text-center text-[14px] text-slate-400">
              No results for “{query}”.
            </p>
          ) : (
            <ul ref={listRef} className="p-2">
              {results.map((entry, index) => {
                const active = index === highlighted
                const Icon = entry.section ? Hash : FileText
                return (
                  <li key={`${entry.href}-${entry.title}`}>
                    <button
                      type="button"
                      onMouseEnter={() => setHighlighted(index)}
                      onClick={() => go(entry)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors',
                        active ? 'bg-brand-50' : 'hover:bg-slate-50'
                      )}
                    >
                      <Icon
                        className={cn(
                          'h-4 w-4 flex-shrink-0',
                          active ? 'text-brand-600' : 'text-slate-400'
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-poppins text-[14px] font-semibold text-slate-900">
                          {entry.title}
                        </span>
                        <span className="block truncate text-[12.5px] text-slate-500">
                          {entry.section ? `${entry.group} · ${entry.section}` : entry.description}
                        </span>
                      </span>
                      {active && (
                        <CornerDownLeft className="h-3.5 w-3.5 flex-shrink-0 text-brand-500" />
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <div className="flex items-center gap-4 border-t border-slate-200 bg-slate-50 px-4 py-2 text-[11.5px] text-slate-500">
          <span className="flex items-center gap-1">
            <Kbd>↑</Kbd>
            <Kbd>↓</Kbd> to navigate
          </span>
          <span className="flex items-center gap-1">
            <Kbd>↵</Kbd> to open
          </span>
          <span className="flex items-center gap-1">
            <Kbd>esc</Kbd> to close
          </span>
        </div>
      </div>
    </div>
  )
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-slate-300 bg-white px-1.5 py-0.5 font-sans text-[11px] text-slate-600">
      {children}
    </kbd>
  )
}
