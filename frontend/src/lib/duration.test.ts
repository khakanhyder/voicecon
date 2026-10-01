import { describe, expect, it } from 'vitest'
import { formatDuration } from './duration'

describe('formatDuration', () => {
  it('rounds a fractional average instead of printing the fraction', () => {
    expect(formatDuration(141.176470588235304)).toBe('2m 21s')
    expect(formatDuration(45.5)).toBe('46s')
    expect(formatDuration(59.6)).toBe('1m') // rounds up across the minute, not "60s"
    expect(formatDuration(3599.7)).toBe('1h')
  })

  it('formats whole seconds, minutes and hours', () => {
    expect(formatDuration(45)).toBe('45s')
    expect(formatDuration(125)).toBe('2m 5s')
    expect(formatDuration(2400)).toBe('40m')
    expect(formatDuration(3900)).toBe('1h 5m')
    expect(formatDuration(7200)).toBe('2h')
  })

  it('shows a tiny duration as under a second, not zero', () => {
    expect(formatDuration(0.2)).toBe('<1s')
  })

  it('treats missing values as empty', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(undefined)).toBe('—')
    expect(formatDuration(Number.NaN)).toBe('—')
    expect(formatDuration(-5)).toBe('—')
    expect(formatDuration(null, { empty: '0s' })).toBe('0s')
  })

  it('lets the caller decide what zero means', () => {
    expect(formatDuration(0)).toBe('—')
    expect(formatDuration(0, { zeroIsEmpty: false })).toBe('0s')
  })
})
