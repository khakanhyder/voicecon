/**
 * Unit tests for the workflow graph: conversion between the backend's v2 graph
 * and React Flow's model, auto-layout, and client-side validation.
 *
 * The conversion is the important half. Every save round-trips the whole graph
 * through `flowToApi`, so a field dropped here is a setting silently lost on
 * the user's next save — which no error surfaces. The tests therefore assert
 * the round trip preserves config and settings, not merely that it runs.
 */
import type { Edge } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import {
  apiToFlow,
  autoLayout,
  flowNodeComponent,
  flowToApi,
  validateFlow,
  type ApiGraph,
  type FlowNode,
} from './graph'
import {
  NODE_TYPES,
  PALETTE_CATEGORIES,
  getDescriptor,
  isKnownNodeType,
  paletteVisibility,
} from './nodeTypes'

function apiNode(overrides: Partial<ApiGraph['nodes'][number]> = {}) {
  return {
    id: 'n1',
    type: 'speak',
    name: 'Say hello',
    position: { x: 10, y: 20 },
    config: { message: 'Hello' },
    ...overrides,
  }
}

function flowNode(
  id: string,
  nodeType: string,
  config: Record<string, unknown> = {},
  label = id
): FlowNode {
  return {
    id,
    type: nodeType === 'trigger' ? 'triggerNode' : 'stepNode',
    position: { x: 0, y: 0 },
    data: { label, nodeType, config, settings: {} },
  }
}

function edge(source: string, target: string, sourceHandle?: string): Edge {
  return {
    id: `${source}->${target}${sourceHandle ? `:${sourceHandle}` : ''}`,
    source,
    target,
    sourceHandle: sourceHandle ?? 'out',
    targetHandle: 'in',
  }
}

describe('apiToFlow', () => {
  it('maps a trigger to the trigger component and steps to the step component', () => {
    const { nodes } = apiToFlow({
      schema_version: 2,
      nodes: [
        apiNode({ id: 't', type: 'trigger' }),
        apiNode({ id: 's', type: 'speak' }),
      ],
      edges: [],
    })

    expect(nodes.find((n) => n.id === 't')?.type).toBe('triggerNode')
    expect(nodes.find((n) => n.id === 's')?.type).toBe('stepNode')
  })

  it('keeps the backend type on the node data', () => {
    // `type` drives rendering; `data.nodeType` is the real type and is what
    // gets written back on save.
    const { nodes } = apiToFlow({
      schema_version: 2,
      nodes: [apiNode({ type: 'condition' })],
      edges: [],
    })

    expect(nodes[0].data.nodeType).toBe('condition')
  })

  it('defaults a missing position to the origin instead of NaN', () => {
    const { nodes } = apiToFlow({
      schema_version: 2,
      nodes: [{ ...apiNode(), position: undefined as never }],
      edges: [],
    })

    expect(nodes[0].position).toEqual({ x: 0, y: 0 })
  })

  it('defaults missing edge handles', () => {
    // React Flow will not draw an edge whose handle is undefined.
    const { edges } = apiToFlow({
      schema_version: 2,
      nodes: [],
      edges: [{ id: 'e1', source: 'a', target: 'b' }],
    })

    expect(edges[0].sourceHandle).toBe('out')
    expect(edges[0].targetHandle).toBe('in')
  })

  it('labels branch edges so the canvas shows which way is which', () => {
    const { edges } = apiToFlow({
      schema_version: 2,
      nodes: [],
      edges: [
        { id: 'e1', source: 'a', sourceHandle: 'true', target: 'b' },
        { id: 'e2', source: 'a', sourceHandle: 'false', target: 'c' },
        { id: 'e3', source: 'c', sourceHandle: 'out', target: 'd' },
      ],
    })

    expect(edges[0].label).toBe('true')
    expect(edges[1].label).toBe('false')
    // A plain sequential edge needs no label; one would be visual noise.
    expect(edges[2].label).toBeUndefined()
  })

  it('survives a graph with no nodes or edges arrays', () => {
    // A brand new workflow comes back with an essentially empty graph.
    const { nodes, edges } = apiToFlow({ schema_version: 2 } as ApiGraph)

    expect(nodes).toEqual([])
    expect(edges).toEqual([])
  })
})

describe('flowToApi', () => {
  it('writes the v2 schema version', () => {
    expect(flowToApi([], []).schema_version).toBe(2)
  })

  it('rounds positions to whole pixels', () => {
    // Dragging produces sub-pixel floats; storing them makes every save a diff.
    const node = flowNode('n1', 'speak')
    node.position = { x: 10.4, y: 20.6 }

    expect(flowToApi([node], []).nodes[0].position).toEqual({ x: 10, y: 21 })
  })

  it('writes the node type back, not the React Flow component name', () => {
    const api = flowToApi([flowNode('n1', 'condition')], [])

    expect(api.nodes[0].type).toBe('condition')
  })
})

describe('round trip', () => {
  it('preserves config and settings through flow and back', () => {
    // The property that matters: every save goes through this path, so a
    // dropped field is a setting silently lost with no error to notice.
    const original: ApiGraph = {
      schema_version: 2,
      nodes: [
        {
          id: 'n1',
          type: 'http',
          name: 'Call the CRM',
          position: { x: 100, y: 200 },
          config: { url: 'https://api.test/x', method: 'POST', body: '{"a":1}' },
          settings: {
            on_error: 'continue',
            timeout_seconds: 30,
            retry: { enabled: true, max_tries: 3, backoff: 'exponential' },
          },
        },
      ],
      edges: [{ id: 'e1', source: 'n1', sourceHandle: 'out', target: 'n2', targetHandle: 'in' }],
    }

    const { nodes, edges } = apiToFlow(original)
    const restored = flowToApi(nodes, edges)

    expect(restored.nodes[0]).toMatchObject({
      id: 'n1',
      type: 'http',
      name: 'Call the CRM',
      position: { x: 100, y: 200 },
      config: original.nodes[0].config,
      settings: original.nodes[0].settings,
    })
    expect(restored.edges[0]).toMatchObject(original.edges[0])
  })

  it('does not invent config for a node that has none', () => {
    const { nodes, edges } = apiToFlow({
      schema_version: 2,
      nodes: [{ id: 'n1', type: 'speak', name: 'x', position: { x: 0, y: 0 }, config: {} }],
      edges: [],
    })

    expect(flowToApi(nodes, edges).nodes[0].config).toEqual({})
  })
})

describe('autoLayout', () => {
  it('gives connected nodes distinct positions', () => {
    // Migrated workflows arrive stacked at the same spot; "Tidy up" spreads them.
    const nodes = [
      flowNode('t', 'trigger'),
      flowNode('a', 'speak'),
      flowNode('b', 'speak'),
    ]
    const laid = autoLayout(nodes, [edge('t', 'a'), edge('a', 'b')])

    const ys = laid.map((n) => n.position.y)
    expect(new Set(ys).size).toBe(3)
  })

  it('lays the graph out top to bottom, following the edges', () => {
    const nodes = [flowNode('t', 'trigger'), flowNode('a', 'speak')]
    const laid = autoLayout(nodes, [edge('t', 'a')])

    const trigger = laid.find((n) => n.id === 't')!
    const step = laid.find((n) => n.id === 'a')!
    expect(step.position.y).toBeGreaterThan(trigger.position.y)
  })

  it('ignores edges pointing at nodes that are not on the canvas', () => {
    // dagre throws on an edge whose endpoint it does not know about, which
    // would take the whole builder down.
    const nodes = [flowNode('a', 'speak')]

    expect(() => autoLayout(nodes, [edge('a', 'ghost')])).not.toThrow()
  })

  it('handles an empty graph', () => {
    expect(autoLayout([], [])).toEqual([])
  })

  it('returns a node per input node', () => {
    const nodes = [flowNode('a', 'speak'), flowNode('b', 'speak')]

    expect(autoLayout(nodes, []).map((n) => n.id)).toEqual(['a', 'b'])
  })
})

describe('validateFlow', () => {
  const trigger = () => flowNode('t', 'trigger')

  it('warns that a workflow with only a trigger has no steps', () => {
    const issues = validateFlow([trigger()], [])

    expect(issues).toHaveLength(1)
    expect(issues[0].severity).toBe('warning')
    expect(issues[0].message).toMatch(/no steps/i)
  })

  it('accepts a complete linear workflow', () => {
    const nodes = [trigger(), flowNode('a', 'speak', { message: 'hi' })]

    expect(validateFlow(nodes, [edge('t', 'a')])).toEqual([])
  })

  it('reports a required field left empty', () => {
    const nodes = [trigger(), flowNode('a', 'speak', {}, 'Greeting')]
    const issues = validateFlow(nodes, [edge('t', 'a')])

    expect(issues).toContainEqual(
      expect.objectContaining({ nodeId: 'a', severity: 'error' })
    )
    expect(issues[0].message).toContain('Greeting')
  })

  it('treats whitespace as empty for a required field', () => {
    // "   " passes a truthiness check but is not an answer.
    const nodes = [trigger(), flowNode('a', 'speak', { message: '   ' })]

    expect(validateFlow(nodes, [edge('t', 'a')])).toContainEqual(
      expect.objectContaining({ nodeId: 'a', severity: 'error' })
    )
  })

  it('accepts a JSON field that already holds parsed JSON', () => {
    // A workflow created through the API stores the object, not the text for
    // it. Both are valid on the wire, and JSON.parse on an object stringifies
    // it to "[object Object]" first — which reported every such webhook as
    // broken while it ran perfectly well.
    const nodes = [
      trigger(),
      flowNode('a', 'webhook', {
        url: 'https://example.com/hook',
        headers: {},
        body: { city: 'Austin' },
      }),
    ]

    expect(validateFlow(nodes, [edge('t', 'a')])).toEqual([])
  })

  it('still reports a JSON field whose text does not parse', () => {
    const nodes = [
      trigger(),
      flowNode('a', 'webhook', { url: 'https://example.com/hook', headers: '{oops' }),
    ]

    expect(validateFlow(nodes, [edge('t', 'a')])).toContainEqual(
      expect.objectContaining({ nodeId: 'a', severity: 'error' })
    )
  })

  it('reports a node unreachable from the trigger', () => {
    const nodes = [
      trigger(),
      flowNode('a', 'speak', { message: 'hi' }),
      flowNode('orphan', 'speak', { message: 'nobody hears me' }, 'Orphan'),
    ]
    const issues = validateFlow(nodes, [edge('t', 'a')])

    expect(issues).toContainEqual(
      expect.objectContaining({ nodeId: 'orphan', severity: 'warning' })
    )
    expect(issues.find((i) => i.nodeId === 'orphan')!.message).toContain('Orphan')
  })

  it('follows a chain when deciding reachability', () => {
    // Reachability is transitive; only nodes off the graph entirely are flagged.
    const nodes = [
      trigger(),
      flowNode('a', 'speak', { message: '1' }),
      flowNode('b', 'speak', { message: '2' }),
      flowNode('c', 'speak', { message: '3' }),
    ]
    const issues = validateFlow(nodes, [edge('t', 'a'), edge('a', 'b'), edge('b', 'c')])

    expect(issues).toEqual([])
  })

  it('warns about a branch output left unconnected', () => {
    const nodes = [
      trigger(),
      flowNode('c', 'condition', { variable: 'x', operator: 'eq', value: '1' }, 'Check'),
      flowNode('a', 'speak', { message: 'yes' }),
    ]
    const issues = validateFlow(nodes, [edge('t', 'c'), edge('c', 'a', 'true')])

    const branchIssue = issues.find((i) => i.message.includes('false'))
    expect(branchIssue).toBeDefined()
    expect(branchIssue!.severity).toBe('warning')
  })

  it('is satisfied once both branch outputs are connected', () => {
    const nodes = [
      trigger(),
      flowNode('c', 'condition', { variable: 'x', operator: 'eq', value: '1' }),
      flowNode('a', 'speak', { message: 'yes' }),
      flowNode('b', 'speak', { message: 'no' }),
    ]
    const issues = validateFlow(nodes, [
      edge('t', 'c'),
      edge('c', 'a', 'true'),
      edge('c', 'b', 'false'),
    ])

    expect(issues.filter((i) => i.message.includes('output'))).toEqual([])
  })

  it('reports a cycle as an error', () => {
    // The runtime would spin forever, so this is an error rather than a warning.
    const nodes = [
      trigger(),
      flowNode('a', 'speak', { message: '1' }),
      flowNode('b', 'speak', { message: '2' }),
    ]
    const issues = validateFlow(nodes, [
      edge('t', 'a'),
      edge('a', 'b'),
      edge('b', 'a'),
    ])

    expect(issues).toContainEqual(
      expect.objectContaining({ severity: 'error', message: expect.stringMatching(/loop/i) })
    )
  })

  it('reports a self-loop', () => {
    const nodes = [trigger(), flowNode('a', 'speak', { message: '1' })]
    const issues = validateFlow(nodes, [edge('t', 'a'), edge('a', 'a')])

    expect(issues.some((i) => /loop/i.test(i.message))).toBe(true)
  })

  it('does not mistake a diamond for a cycle', () => {
    // Two paths that rejoin are legal; a naive "visited" check calls this a loop.
    const nodes = [
      trigger(),
      flowNode('a', 'speak', { message: '1' }),
      flowNode('b', 'speak', { message: '2' }),
      flowNode('c', 'speak', { message: '3' }),
      flowNode('d', 'speak', { message: '4' }),
    ]
    const issues = validateFlow(nodes, [
      edge('t', 'a'),
      edge('a', 'b'),
      edge('a', 'c'),
      edge('b', 'd'),
      edge('c', 'd'),
    ])

    expect(issues.some((i) => /loop/i.test(i.message))).toBe(false)
  })
})

describe('the Run Tool node', () => {
  it('picks a tool rather than asking for a pasted id', () => {
    // The field was free text whose placeholder read "tool_xxxxxxxx", while
    // the engine parses the value as a UUID and the Tools page prints no id
    // anywhere — so the node could not be configured correctly from the UI.
    const field = getDescriptor('tool').fields.find((f) => f.name === 'tool_id')
    expect(field?.type).toBe('tool')
    expect(field?.required).toBe(true)
    expect(field?.placeholder).toBeUndefined()
  })

  it('reports on the canvas whether a tool is chosen', () => {
    const { summary } = getDescriptor('tool')
    expect(summary({})).toBe('No tool selected')
    // A bare UUID on the canvas node tells the reader nothing.
    expect(summary({ tool_id: '7f4a…' })).not.toContain('7f4a')
  })
})

describe('the node registry', () => {
  it('has no Code node, and has the nodes that replaced it', () => {
    expect(isKnownNodeType('code')).toBe(false)
    expect(isKnownNodeType('transform')).toBe(true)
    expect(isKnownNodeType('calculate')).toBe(true)
  })

  it('gives a retired node type a descriptor with no fields', () => {
    // Falling back to another node's descriptor would read the stored config
    // against the wrong fields and discard it on the next save.
    const retired = getDescriptor('code')
    expect(retired.fields).toEqual([])
    expect(retired.label).toBe('Unsupported step')
  })
})

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

describe('notes are annotations, not steps', () => {
  const note = (): FlowNode => ({
    id: 'note1',
    type: 'noteNode',
    position: { x: 0, y: 0 },
    data: {
      label: 'Note',
      nodeType: 'note',
      config: { text: 'Check with billing before changing this' },
      settings: {},
    },
  })

  const trigger = (): FlowNode => ({
    id: 't1',
    type: 'triggerNode',
    position: { x: 0, y: 0 },
    data: { label: 'Trigger', nodeType: 'trigger', config: {}, settings: {} },
  })

  const speak = (): FlowNode => ({
    id: 's1',
    type: 'stepNode',
    position: { x: 0, y: 0 },
    data: {
      label: 'Say hi',
      nodeType: 'speak',
      config: { message: 'Hello' },
      settings: {},
    },
  })

  it('renders through its own component, which has no handles', () => {
    expect(flowNodeComponent('note')).toBe('noteNode')
    expect(flowNodeComponent('trigger')).toBe('triggerNode')
    expect(flowNodeComponent('speak')).toBe('stepNode')
  })

  it('does not count as a step, so a note-only canvas is still empty', () => {
    const issues = validateFlow([trigger(), note()], [])
    expect(issues.map((i) => i.message)).toContain('Workflow has no steps yet')
  })

  it('is not reported as unconnected — it is unconnected by design', () => {
    const edges: Edge[] = [
      {
        id: 'e1',
        source: 't1',
        target: 's1',
        sourceHandle: 'out',
        targetHandle: 'in',
      },
    ]
    const issues = validateFlow([trigger(), speak(), note()], edges)

    expect(issues.filter((i) => i.nodeId === 'note1')).toHaveLength(0)
    expect(issues).toHaveLength(0)
  })

  it('survives the save round trip with its text intact', () => {
    const api = flowToApi([note()], [])
    expect(api.nodes[0]).toMatchObject({
      id: 'note1',
      type: 'note',
      config: { text: 'Check with billing before changing this' },
    })
    expect(apiToFlow(api).nodes[0].data.config.text).toBe(
      'Check with billing before changing this'
    )
  })
})

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------

describe('palette placement', () => {
  it('retires Filter from the palette without breaking it', () => {
    // Hiding, not deleting: workflows already using Filter must keep running
    // and stay editable. Dropping the descriptor would strand them on
    // UNKNOWN_NODE and force a rebuild.
    expect(paletteVisibility(NODE_TYPES.filter)).toBe('hidden')
    expect(isKnownNodeType('filter')).toBe(true)
    expect(NODE_TYPES.filter.fields.length).toBeGreaterThan(0)
  })

  it('gives Filter the same operators as Branch', () => {
    const operators = (type: string) =>
      NODE_TYPES[type].fields
        .find((f) => f.name === 'operator')!
        .options!.map((o) => o.value)

    expect(operators('filter')).toEqual(operators('condition'))
  })

  it('moves the rarely-needed Logic steps behind Advanced', () => {
    for (const type of ['merge', 'loop', 'calculate']) {
      expect(paletteVisibility(NODE_TYPES[type])).toBe('advanced')
    }
  })

  it('leaves the everyday steps in the default palette', () => {
    for (const type of ['speak', 'ask', 'condition', 'switch', 'transform', 'delay']) {
      expect(paletteVisibility(NODE_TYPES[type])).toBe('default')
    }
  })

  it('describes the three "call something external" steps distinguishably', () => {
    // All three call outside the workflow. Describing each by its mechanism
    // left the reader to work out which one they wanted.
    const descriptions = ['tool', 'webhook', 'action'].map(
      (t) => NODE_TYPES[t].description
    )
    expect(new Set(descriptions).size).toBe(3)
    expect(NODE_TYPES.action.description).toMatch(/connected/i)
    expect(NODE_TYPES.tool.description).toMatch(/Tools section/i)
  })

  it('lists every category a descriptor uses', () => {
    const used = new Set(
      Object.values(NODE_TYPES)
        .filter((d) => d.type !== 'trigger')
        .map((d) => d.category)
    )
    for (const category of used) {
      expect(PALETTE_CATEGORIES).toContain(category)
    }
  })
})
