/**
 * Every timestamp the dashboard shows goes through here.
 *
 * The API stores UTC. It now sends an explicit offset ("…+00:00"), but older
 * responses — and anything cached or proxied from before that — carried naive
 * strings like "2026-09-30T10:00:00". `new Date()` reads a naive string as the
 * browser's *local* time, which put every relative time off by the viewer's UTC
 * offset: at UTC+5 a call made two minutes ago read "5h ago". So parsing is
 * never done with a bare `new Date(value)` on API data; use `parseApiDate`.
 *
 * Display is always in the viewer's own timezone (the browser's), via
 * `toLocale*String` with no hardcoded zone or offset.
 */
import { useSyncExternalStore } from 'react'

const HAS_ZONE = /(?:[zZ]|[+-]\d{2}:?\d{2})$/
const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/

export type DateInput = string | number | Date | null | undefined

/**
 * A `Date` for an API value, or `null` if there isn't a usable one.
 *
 * - ISO datetime without a zone → treated as UTC (that is how it was stored).
 * - ISO datetime with a zone → taken as-is.
 * - Date only ("2026-09-30", a daily bucket or billing day) → that calendar day
 *   in local time. Read as UTC midnight it would show as the previous day
 *   anywhere west of Greenwich.
 * - Numbers are epoch milliseconds.
 */
export function parseApiDate(value: DateInput): Date | null {
  if (value == null || value === '') return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (typeof value === 'number') {
    const d = new Date(value)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const s = value.trim()
  const day = DATE_ONLY.exec(s)
  if (day) return new Date(Number(day[1]), Number(day[2]) - 1, Number(day[3]))
  const d = new Date(HAS_ZONE.test(s) || !s.includes('T') ? s : `${s}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Milliseconds since the epoch, or 0 — for sorting API rows by time. */
export function apiTime(value: DateInput): number {
  return parseApiDate(value)?.getTime() ?? 0
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/**
 * "Just now", "4m ago", "3h ago", "2d ago" — then the date itself once it is a
 * week old, because "23d ago" makes the reader do arithmetic. Future values
 * read "in 4m". Pass `now` from `useNow()` so the label keeps moving.
 */
export function timeAgo(value: DateInput, now: number = Date.now(), empty = '—'): string {
  const d = parseApiDate(value)
  if (!d) return empty
  const diff = now - d.getTime()
  const future = diff < 0
  const abs = Math.abs(diff)
  // A few seconds of clock skew between server and browser is not "the future".
  if (abs < MINUTE) return 'Just now'
  let label: string
  if (abs < HOUR) label = `${Math.floor(abs / MINUTE)}m`
  else if (abs < DAY) label = `${Math.floor(abs / HOUR)}h`
  else if (abs < 7 * DAY) label = `${Math.floor(abs / DAY)}d`
  else return formatDate(d, { withYear: d.getFullYear() !== new Date(now).getFullYear() })
  return future ? `in ${label}` : `${label} ago`
}

/** "Sep 30, 2026" (or "Sep 30" with `withYear: false`) in the viewer's timezone. */
export function formatDate(
  value: DateInput,
  { withYear = true, month = 'short', empty = '—' }: { withYear?: boolean; month?: 'short' | 'long'; empty?: string } = {},
): string {
  const d = parseApiDate(value)
  if (!d) return empty
  return d.toLocaleDateString(undefined, { month, day: 'numeric', ...(withYear ? { year: 'numeric' } : {}) })
}

/** "Sep 30, 2026, 3:04 PM" in the viewer's timezone. */
export function formatDateTime(value: DateInput, empty = '—'): string {
  const d = parseApiDate(value)
  if (!d) return empty
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

/** "3:04 PM" in the viewer's timezone. */
export function formatTime(value: DateInput, { seconds = false, empty = '—' } = {}): string {
  const d = parseApiDate(value)
  if (!d) return empty
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}) })
}

// ---------------------------------------------------------------------------
// A shared clock, so relative labels move on their own.
//
// One interval for the whole page, however many timestamps are on screen; it
// only runs while something is subscribed.
// ---------------------------------------------------------------------------

const TICK_MS = 30_000
let clockNow = Date.now()
let timer: ReturnType<typeof setInterval> | null = null
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  if (!timer) {
    clockNow = Date.now()
    timer = setInterval(() => {
      clockNow = Date.now()
      listeners.forEach((l) => l())
    }, TICK_MS)
  }
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0 && timer) {
      clearInterval(timer)
      timer = null
    }
  }
}

/** The current time, re-rendering the caller every 30 seconds. */
export function useNow(): number {
  return useSyncExternalStore(subscribe, () => clockNow, () => clockNow)
}
