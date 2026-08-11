/**
 * Unit tests for the agent flow-builder validation.
 *
 * Distinct from `lib/workflow/graph.ts`, which validates the newer *workflow*
 * graph — this one covers the agent conversation flow. The distinction that
 * matters is error vs warning: an error blocks saving, a warning does not, so
 * classifying a missing End node as an error would make legitimate flows
 * unsaveable.
 */
import type { Edge, Node } from 'reactflow'
import { describe, expect, it } from 'vitest'

import { validateFlow, validateNodeData } from './flowValidation'

function node(id: string, type: string, data: Record<string, unknown> = {}): Node {
  return { id, type, position: { x: 0, y: 0 }, data }
}

function edge(source: string, target: string): Edge {
  return { id: `${source}-${target}`, source, target }
}

describe('validateFlow', () => {
  it('accepts a minimal connected flow', () => {
    const nodes = [node('s', 'start'), node('e', 'end')]

    const result = validateFlow(nodes, [edge('s', 'e')])

    expect(result.valid).toBe(true)
    expect(result.errors).toEqual([])
  })

  it('requires a start node', () => {
    // Without one there is nowhere for a call to begin, so this blocks saving.
    const result = validateFlow([node('e', 'end')], [])

    expect(result.valid).toBe(false)
    expect(result.errors[0].message).toMatch(/must have a Start node/i)
  })

  it('rejects a second start node', () => {
    // Two entry points make the starting state ambiguous.
    const result = validateFlow([node('s1', 'start'), node('s2', 'start')], [])

    expect(result.valid).toBe(false)
    expect(result.errors.some((e) => /only have one Start/i.test(e.message))).toBe(true)
  })

  it('only warns about a missing end node', () => {
    // A flow can legitimately be built end-first; this must not block saving.
    const result = validateFlow([node('s', 'start')], [])

    expect(result.valid).toBe(true)
    expect(result.warnings.some((w) => /no End node/i.test(w.message))).toBe(true)
  })

  it('warns about a disconnected node, naming it', () => {
    const nodes = [
      node('s', 'start'),
      node('e', 'end'),
      node('m', 'message', { label: 'Greeting' }),
    ]

    const result = validateFlow(nodes, [edge('s', 'e')])

    const warning = result.warnings.find((w) => w.nodeId === 'm')
    expect(warning).toBeDefined()
    expect(warning!.message).toContain('Greeting')
  })

  it('falls back to the node id when it has no label', () => {
    // "Node "undefined" is not connected" would be useless to act on.
    const nodes = [node('s', 'start'), node('m', 'message')]

    const result = validateFlow(nodes, [])

    expect(result.warnings.find((w) => w.nodeId === 'm')!.message).toContain('m')
  })

  it('does not call the start node disconnected', () => {
    // The start node has no incoming edge by definition.
    const result = validateFlow([node('s', 'start')], [])

    expect(result.warnings.some((w) => w.nodeId === 's')).toBe(false)
  })

  it('counts a node as connected when it is only a target', () => {
    const nodes = [node('s', 'start'), node('e', 'end')]

    const result = validateFlow(nodes, [edge('s', 'e')])

    expect(result.warnings.some((w) => w.nodeId === 'e')).toBe(false)
  })

  it('stays invalid while any error is present, regardless of warnings', () => {
    const result = validateFlow([node('m', 'message')], [])

    expect(result.valid).toBe(false)
    expect(result.warnings.length).toBeGreaterThan(0)
  })

  it('treats an empty flow as missing its start node', () => {
    const result = validateFlow([], [])

    expect(result.valid).toBe(false)
  })
})

describe('validateNodeData', () => {
  it('accepts a message node with text', () => {
    expect(validateNodeData(node('m', 'message', { message: 'Hello' }))).toEqual([])
  })

  it('requires message text', () => {
    const errors = validateNodeData(node('m', 'message'))

    expect(errors).toHaveLength(1)
    expect(errors[0]).toMatchObject({ nodeId: 'm', severity: 'error' })
  })

  it('requires question text', () => {
    expect(validateNodeData(node('q', 'question'))).toHaveLength(1)
  })

  it('requires a function name', () => {
    expect(validateNodeData(node('f', 'function'))).toHaveLength(1)
  })

  it('has no requirements for structural nodes', () => {
    expect(validateNodeData(node('s', 'start'))).toEqual([])
    expect(validateNodeData(node('e', 'end'))).toEqual([])
  })

  it('tolerates a node with no data object at all', () => {
    // Nodes dropped from the palette arrive before their config is filled in.
    const bare = { id: 'm', type: 'message', position: { x: 0, y: 0 } } as Node

    expect(() => validateNodeData(bare)).not.toThrow()
  })
})
