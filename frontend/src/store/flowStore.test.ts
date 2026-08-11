/**
 * Unit tests for the in-memory flow cache.
 *
 * Keeps the working copy of each flow while the builder is open, so switching
 * between flows does not lose unsaved edits.
 */
import { beforeEach, describe, expect, it } from 'vitest'

import { useFlowStore } from './flowStore'

const nodes = [{ id: 'n1', position: { x: 0, y: 0 }, data: {} }] as never
const edges = [{ id: 'e1', source: 'n1', target: 'n2' }] as never

const store = () => useFlowStore.getState()

beforeEach(() => {
  useFlowStore.setState({ flows: {}, currentFlowId: null })
})

describe('saving and loading', () => {
  it('round-trips a flow by id', () => {
    store().saveFlow('f1', nodes, edges)

    expect(store().loadFlow('f1')).toEqual({ nodes, edges })
  })

  it('returns null for an unknown flow', () => {
    // Must be null, not undefined — the builder branches on it to decide
    // whether to fetch from the server.
    expect(store().loadFlow('missing')).toBeNull()
  })

  it('keeps flows separate', () => {
    store().saveFlow('f1', nodes, [] as never)
    store().saveFlow('f2', [] as never, edges)

    expect(store().loadFlow('f1')?.edges).toEqual([])
    expect(store().loadFlow('f2')?.nodes).toEqual([])
  })

  it('overwrites on re-save', () => {
    store().saveFlow('f1', nodes, edges)
    store().saveFlow('f1', [] as never, [] as never)

    expect(store().loadFlow('f1')).toEqual({ nodes: [], edges: [] })
  })
})

describe('deleting', () => {
  it('removes the flow', () => {
    store().saveFlow('f1', nodes, edges)

    store().deleteFlow('f1')

    expect(store().loadFlow('f1')).toBeNull()
  })

  it('leaves other flows alone', () => {
    store().saveFlow('f1', nodes, edges)
    store().saveFlow('f2', nodes, edges)

    store().deleteFlow('f1')

    expect(store().loadFlow('f2')).not.toBeNull()
  })

  it('clears the selection when the open flow is deleted', () => {
    // Otherwise the builder keeps pointing at a flow that no longer exists.
    store().saveFlow('f1', nodes, edges)
    store().setCurrentFlow('f1')

    store().deleteFlow('f1')

    expect(store().currentFlowId).toBeNull()
  })

  it('keeps the selection when a different flow is deleted', () => {
    store().saveFlow('f1', nodes, edges)
    store().saveFlow('f2', nodes, edges)
    store().setCurrentFlow('f2')

    store().deleteFlow('f1')

    expect(store().currentFlowId).toBe('f2')
  })
})

describe('selection', () => {
  it('tracks the open flow', () => {
    store().setCurrentFlow('f1')

    expect(store().currentFlowId).toBe('f1')
  })

  it('can be cleared', () => {
    store().setCurrentFlow('f1')

    store().setCurrentFlow(null)

    expect(store().currentFlowId).toBeNull()
  })
})
