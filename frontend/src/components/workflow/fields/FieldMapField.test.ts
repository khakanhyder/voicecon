import { describe, expect, it } from 'vitest'

import { chainOf, fromChain } from './FieldMapField'

describe('reading a field spec', () => {
  it('treats a bare string as a source with no transform', () => {
    expect(chainOf({ source: '{{trigger.total}}' })).toEqual([])
  })

  it('reads the single-transform shape written before chains existed', () => {
    expect(chainOf({ source: 'orders', transform: 'sum', args: 'amount' })).toEqual([
      { name: 'sum', args: 'amount' },
    ])
  })

  it('reads a stored chain in order', () => {
    expect(
      chainOf({
        source: 'when',
        transform: [
          { name: 'add_hours', args: '2' },
          { name: 'format_date', args: '%H:%M' },
        ],
      })
    ).toEqual([
      { name: 'add_hours', args: '2' },
      { name: 'format_date', args: '%H:%M' },
    ])
  })

  it('ignores an empty slot left behind in a chain', () => {
    expect(
      chainOf({ transform: [{ name: 'add_hours', args: '2' }, { name: '' }] })
    ).toEqual([{ name: 'add_hours', args: '2' }])
  })
})

describe('writing a field spec', () => {
  it('stores one transform in the shape it has always had', () => {
    // A workflow that predates chains must not be rewritten just by opening it.
    expect(fromChain([{ name: 'sum', args: 'amount' }])).toEqual({
      transform: 'sum',
      args: 'amount',
    })
  })

  it('omits an argument the transform does not take', () => {
    expect(fromChain([{ name: 'count' }])).toEqual({ transform: 'count' })
  })

  it('widens to a list only once there is a second transform', () => {
    expect(
      fromChain([
        { name: 'add_hours', args: '2' },
        { name: 'format_date', args: '%H:%M' },
      ])
    ).toEqual({
      transform: [
        { name: 'add_hours', args: '2' },
        { name: 'format_date', args: '%H:%M' },
      ],
    })
  })

  it('clears the transform entirely when nothing is chosen', () => {
    expect(fromChain([])).toEqual({})
    expect(fromChain([{ name: '' }])).toEqual({})
  })

  it('round-trips a chain', () => {
    const chain = [
      { name: 'add_days', args: '7' },
      { name: 'format_date', args: '%d %b %Y' },
    ]
    expect(chainOf(fromChain(chain) as any)).toEqual(chain)
  })
})
