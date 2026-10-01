/**
 * How long a call (or anything else measured in seconds) lasted, for display.
 *
 * One formatter for every screen. Each page used to carry its own copy, and
 * they all assumed a whole number: an *average* is a fraction, so the Analytics
 * card rendered "2m 21.176470588235304s". The copies also disagreed on padding
 * and on what an empty value looks like.
 *
 *   45        → "45s"
 *   141.18    → "2m 21s"      rounded to the nearest second
 *   2400      → "40m"         no trailing "0s"
 *   3900      → "1h 5m"       seconds are noise at this scale
 *   0.4       → "<1s"         a real but tiny duration is not "0s"
 *   null      → "—"           or whatever `empty` says
 */
export function formatDuration(
  seconds: number | null | undefined,
  {
    empty = '—',
    zeroIsEmpty = true,
  }: {
    /** Shown when there is no duration at all. */
    empty?: string
    /** Treat 0 like "no duration" (a call that never connected). Pass false
     *  where 0 is a real measurement, such as a total. */
    zeroIsEmpty?: boolean
  } = {},
): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return empty
  if (seconds === 0) return zeroIsEmpty ? empty : '0s'
  if (seconds < 0.5) return '<1s'

  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60

  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`
  if (m > 0) return s > 0 ? `${m}m ${s}s` : `${m}m`
  return `${s}s`
}
