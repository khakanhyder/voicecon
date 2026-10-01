'use client'

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, Search } from 'lucide-react'
import {
  findPhoneCountry,
  flagUrl,
  phoneCountries,
  sanitizePhoneInput,
  type PhoneValue,
} from '@/lib/phone'
import { errorInputClass } from '@/components/ui/field-error'

function Flag({ iso, className = 'h-3.5 w-5' }: { iso: string; className?: string }) {
  const [broken, setBroken] = useState(false)
  if (broken) {
    return (
      <span className="w-5 text-center text-[10px] font-semibold text-slate-500">{iso}</span>
    )
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={flagUrl(iso)}
      alt=""
      loading="lazy"
      onError={() => setBroken(true)}
      className={`${className} shrink-0 rounded-[2px] object-cover shadow-[0_0_0_1px_rgba(15,23,42,0.08)]`}
    />
  )
}

interface PhoneInputProps {
  id: string
  value: PhoneValue
  onChange: (value: PhoneValue) => void
  disabled?: boolean
  /** Styles the country button and the number box, so each form keeps its own look. */
  inputClassName: string
  error?: string
  placeholder?: string
}

/**
 * A phone field: a searchable country picker (flag, name, calling code) beside
 * a number box that only accepts what a phone number can contain.
 *
 * It holds no state of its own beyond the open list and the search text — the
 * form owns the value and validates it with `phoneError` / `phoneToE164`.
 */
export function PhoneInput({
  id,
  value,
  onChange,
  disabled,
  inputClassName,
  error,
  placeholder = '(301) 798 1897',
}: PhoneInputProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listId = useId()

  const selected = findPhoneCountry(value.country)

  const results = useMemo(() => {
    const q = query.trim().toLowerCase().replace(/^\+/, '')
    const all = phoneCountries()
    if (!q) return all
    return all.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.iso.toLowerCase() === q ||
        c.dial.slice(1).startsWith(q),
    )
  }, [query])

  // Close on an outside press. pointerdown (not click) so it also closes before
  // a tap lands on whatever sits underneath on a touch screen.
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [open])

  useEffect(() => {
    if (!open) return
    searchRef.current?.focus()
    const i = phoneCountries().findIndex((c) => c.iso === value.country)
    setActive(Math.max(0, i))
    // Only on open: re-running on every value change would fight the search box.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  const close = () => {
    setOpen(false)
    setQuery('')
  }

  const pick = (iso: PhoneValue['country']) => {
    onChange({ ...value, country: iso })
    close()
    document.getElementById(id)?.focus()
  }

  const onSearchKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (results[active]) pick(results[active].iso)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      close()
    }
  }

  return (
    <div ref={rootRef} className="relative flex gap-2">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        aria-label={`Country code, ${selected?.name ?? ''} ${selected?.dial ?? ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        className={`${inputClassName} flex w-auto shrink-0 items-center gap-1.5 whitespace-nowrap`}
      >
        <Flag iso={value.country} />
        <span>{selected?.dial}</span>
        <ChevronDown className="h-4 w-4 text-slate-400" aria-hidden="true" />
      </button>

      <input
        id={id}
        type="tel"
        inputMode="tel"
        autoComplete="tel-national"
        maxLength={20}
        placeholder={placeholder}
        value={value.national}
        disabled={disabled}
        onChange={(e) => onChange({ ...value, national: sanitizePhoneInput(e.target.value) })}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`${inputClassName} min-w-0 flex-1 ${error ? errorInputClass : ''}`}
      />

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-[min(21rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl shadow-slate-900/10">
          <div className="relative border-b border-slate-100 p-2">
            <Search
              className="pointer-events-none absolute left-5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              ref={searchRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setActive(0)
              }}
              onKeyDown={onSearchKey}
              placeholder="Search country or code"
              aria-label="Search countries"
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-activedescendant={results[active] ? `${listId}-${results[active].iso}` : undefined}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-500/20"
            />
          </div>
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-label="Countries"
            className="max-h-64 overflow-y-auto overscroll-contain py-1"
          >
            {results.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-slate-500">No country found</li>
            )}
            {results.map((c, i) => (
              <li
                key={c.iso}
                id={`${listId}-${c.iso}`}
                role="option"
                data-index={i}
                aria-selected={c.iso === value.country}
                onPointerDown={(e) => e.preventDefault()}
                onClick={() => pick(c.iso)}
                onMouseMove={() => setActive(i)}
                className={`flex cursor-pointer items-center gap-3 px-3 py-2 text-sm ${
                  i === active ? 'bg-brand-50' : ''
                }`}
              >
                <Flag iso={c.iso} />
                <span className="min-w-0 flex-1 truncate text-slate-800">{c.name}</span>
                <span className="shrink-0 text-slate-500">{c.dial}</span>
                {c.iso === value.country && (
                  <Check className="h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
