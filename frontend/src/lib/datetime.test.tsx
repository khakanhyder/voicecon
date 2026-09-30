import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { apiTime, formatDate, parseApiDate, timeAgo } from './datetime'
import { RelativeTime } from '@/components/ui/relative-time'

// Run under several zones (TZ=Asia/Karachi, America/Los_Angeles, UTC): every
// assertion here must hold whatever the browser's offset is.
const NOW = Date.UTC(2026, 8, 30, 10, 0, 0) // 2026-09-30T10:00:00Z

describe('parseApiDate', () => {
  it('reads a naive API timestamp as UTC, not local time', () => {
    // The bug: at UTC+5 this came back five hours early, so "2m ago" read "5h ago".
    expect(parseApiDate('2026-09-30T09:58:00')!.getTime()).toBe(Date.UTC(2026, 8, 30, 9, 58))
    expect(parseApiDate('2026-09-30T09:58:00.123456')!.getTime()).toBe(Date.UTC(2026, 8, 30, 9, 58, 0, 123))
  })

  it('honours an explicit offset', () => {
    expect(parseApiDate('2026-09-30T09:58:00+00:00')!.getTime()).toBe(Date.UTC(2026, 8, 30, 9, 58))
    expect(parseApiDate('2026-09-30T09:58:00Z')!.getTime()).toBe(Date.UTC(2026, 8, 30, 9, 58))
    expect(parseApiDate('2026-09-30T14:58:00+05:00')!.getTime()).toBe(Date.UTC(2026, 8, 30, 9, 58))
  })

  it('keeps a date-only value on its calendar day in any zone', () => {
    const d = parseApiDate('2026-09-30')!
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 8, 30])
  })

  it('returns null for missing or unparseable input', () => {
    expect(parseApiDate(null)).toBeNull()
    expect(parseApiDate('')).toBeNull()
    expect(parseApiDate('not a date')).toBeNull()
    expect(apiTime(undefined)).toBe(0)
  })
})

describe('timeAgo', () => {
  it('measures from the real event time', () => {
    expect(timeAgo('2026-09-30T09:59:40', NOW)).toBe('Just now')
    expect(timeAgo('2026-09-30T09:58:00', NOW)).toBe('2m ago')
    expect(timeAgo('2026-09-30T09:58:00+00:00', NOW)).toBe('2m ago')
    expect(timeAgo('2026-09-30T07:00:00', NOW)).toBe('3h ago')
    expect(timeAgo('2026-09-28T10:00:00', NOW)).toBe('2d ago')
  })

  it('reads future values forward, and tolerates small clock skew', () => {
    expect(timeAgo('2026-09-30T10:05:00', NOW)).toBe('in 5m')
    expect(timeAgo('2026-09-30T10:00:20', NOW)).toBe('Just now')
  })

  it('falls back to the date after a week', () => {
    expect(timeAgo('2026-09-01T10:00:00', NOW)).toBe(formatDate('2026-09-01T10:00:00', { withYear: false }))
    expect(timeAgo('2025-09-01T10:00:00', NOW)).toBe(formatDate('2025-09-01T10:00:00'))
    expect(timeAgo(null, NOW)).toBe('—')
  })
})

describe('<RelativeTime>', () => {
  afterEach(() => vi.useRealTimers())

  it('updates as time passes', () => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    render(<RelativeTime value="2026-09-30T09:58:00" />)
    expect(screen.getByText('2m ago')).toBeTruthy()
    act(() => {
      vi.advanceTimersByTime(3 * 60_000)
    })
    expect(screen.getByText('5m ago')).toBeTruthy()
  })

  it('renders the fallback for no value', () => {
    render(<RelativeTime value={null} empty="Never" />)
    expect(screen.getByText('Never')).toBeTruthy()
  })
})
