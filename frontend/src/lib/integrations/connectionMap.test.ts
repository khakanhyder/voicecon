import { describe, expect, it } from 'vitest'

import { buildConnectionMap } from './connectionMap'

const conn = (id: string, slug: string, status: string) => ({
  id,
  slug,
  status,
  connector: { slug },
  created_at: '2026-08-13T15:00:00',
})

describe('deciding what an integration card shows', () => {
  it('lets a working connection win over a stale broken one', () => {
    // The exact shape that made a live Google Calendar read "Error": two rows,
    // and the expired one happened to come last.
    const map = buildConnectionMap([
      conn('live', 'google-calendar', 'active'),
      conn('stale', 'google-calendar', 'expired'),
    ])

    expect(map['google-calendar']).toEqual({ connectionId: 'live', status: 'connected' })
  })

  it('wins regardless of the order they arrive in', () => {
    const map = buildConnectionMap([
      conn('stale', 'google-calendar', 'expired'),
      conn('live', 'google-calendar', 'active'),
    ])

    expect(map['google-calendar'].connectionId).toBe('live')
  })

  it('still reports an error when every connection is broken', () => {
    const map = buildConnectionMap([
      conn('a', 'google-sheets', 'expired'),
      conn('b', 'google-sheets', 'error'),
    ])

    expect(map['google-sheets'].status).toBe('error')
  })

  it('prefers a working connection over one still pending', () => {
    const map = buildConnectionMap([
      conn('p', 'trello', 'pending'),
      conn('a', 'trello', 'active'),
    ])

    expect(map['trello']).toEqual({ connectionId: 'a', status: 'connected' })
  })

  it('ignores disconnected rows entirely', () => {
    const map = buildConnectionMap([conn('gone', 'slack', 'disconnected')])

    expect(map['slack']).toBeUndefined()
  })

  it('keeps apps separate', () => {
    const map = buildConnectionMap([
      conn('cal', 'google-calendar', 'active'),
      conn('sheet', 'google-sheets', 'expired'),
    ])

    expect(map['google-calendar'].status).toBe('connected')
    expect(map['google-sheets'].status).toBe('error')
  })
})
