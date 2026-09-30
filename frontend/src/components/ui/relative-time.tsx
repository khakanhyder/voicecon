'use client'

import { formatDateTime, parseApiDate, timeAgo, useNow, type DateInput } from '@/lib/datetime'

/**
 * "4m ago" that keeps itself current, with the exact local time on hover.
 * Use this rather than computing a relative string once at render.
 */
export function RelativeTime({
  value,
  empty = '—',
  className,
}: {
  value: DateInput
  empty?: string
  className?: string
}) {
  const now = useNow()
  const d = parseApiDate(value)
  if (!d) return <span className={className}>{empty}</span>
  return (
    <time dateTime={d.toISOString()} title={formatDateTime(d)} className={className} suppressHydrationWarning>
      {timeAgo(d, now)}
    </time>
  )
}
