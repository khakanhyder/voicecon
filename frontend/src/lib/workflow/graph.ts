/**
 * Conversion between the backend's v2 graph and React Flow's node/edge model,
 * plus layout and client-side validation.
 */
import type { Edge, Node } from '@xyflow/react'
import dagre from '@dagrejs/dagre'
import { getDescriptor, outputsFor } from './nodeTypes'

export interface NodeSettings {
  on_error?: 'stop' | 'continue'
  timeout_seconds?: number
  retry?: {
    enabled?: boolean
    max_tries?: number
    delay_seconds?: number
    backoff?: 'fixed' | 'exponential'
  }
}

export interface ApiNode {
  id: string
  type: string
  name: string
  description?: string | null
  position: { x: number; y: number }
  config: Record<string, any>
  settings?: NodeSettings
}

export interface ApiEdge {
  id: string
  source: string
  sourceHandle?: string
  target: string
  targetHandle?: string
}

export interface ApiGraph {
  schema_version: number
  nodes: ApiNode[]
  edges: ApiEdge[]
  viewport?: { x: number; y: number; zoom: number }
}

export interface FlowNodeData extends Record<string, unknown> {
  label: string
  nodeType: string
  config: Record<string, any>
  settings: NodeSettings
  /** Execution status overlaid after a test run. */
  status?: 'running' | 'success' | 'failed' | 'skipped'
  error?: string | null
}

export type FlowNode = Node<FlowNodeData>

export const NODE_WIDTH = 280
export const NODE_HEIGHT = 92

// ---------------------------------------------------------------------------
// Conversion
// ---------------------------------------------------------------------------

export function apiToFlow(graph: ApiGraph): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes: FlowNode[] = (graph.nodes || []).map((n) => ({
    id: n.id,
    // Every node renders through one component; the descriptor drives its look.
    type: n.type === 'trigger' ? 'triggerNode' : 'stepNode',
    position: { x: n.position?.x ?? 0, y: n.position?.y ?? 0 },
    data: {
      label: n.name,
      nodeType: n.type,
      config: n.config || {},
      settings: n.settings || {},
    },
  }))

  const edges: Edge[] = (graph.edges || []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? 'out',
    targetHandle: e.targetHandle ?? 'in',
    type: 'workflowEdge',
    label: branchLabel(e.sourceHandle),
  }))

  return { nodes, edges }
}

export function flowToApi(nodes: FlowNode[], edges: Edge[]): ApiGraph {
  return {
    schema_version: 2,
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.data.nodeType,
      name: n.data.label,
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
      config: n.data.config || {},
      settings: n.data.settings || {},
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle ?? 'out',
      target: e.target,
      targetHandle: e.targetHandle ?? 'in',
    })),
  }
}

function branchLabel(handle?: string | null): string | undefined {
  if (handle === 'true') return 'true'
  if (handle === 'false') return 'false'
  return undefined
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

/**
 * Lay the graph out top-to-bottom with dagre.
 *
 * Migrated workflows arrive as a naive vertical stack, and hand-built graphs
 * drift; "Tidy up" reflows them.
 */
export function autoLayout(nodes: FlowNode[], edges: Edge[]): FlowNode[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80 })

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }))
  edges.forEach((e) => {
    // dagre throws on edges whose endpoints it does not know about.
    if (g.hasNode(e.source) && g.hasNode(e.target)) g.setEdge(e.source, e.target)
  })

  dagre.layout(g)

  return nodes.map((n) => {
    const pos = g.node(n.id)
    if (!pos) return n
    return {
      ...n,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    }
  })
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

export interface Issue {
  nodeId: string | null
  message: string
  severity: 'error' | 'warning'
}

/**
 * Validate the graph in the browser so problems surface as you edit.
 *
 * Mirrors the server's checks in `app/services/workflows/graph.py`; the server
 * remains authoritative on save.
 */
export function validateFlow(nodes: FlowNode[], edges: Edge[]): Issue[] {
  const issues: Issue[] = []

  if (nodes.filter((n) => n.data.nodeType !== 'trigger').length === 0) {
    issues.push({
      nodeId: null,
      message: 'Workflow has no steps yet',
      severity: 'warning',
    })
    return issues
  }

  // Required fields
  for (const node of nodes) {
    const descriptor = getDescriptor(node.data.nodeType)
    for (const field of descriptor.fields) {
      if (!field.required) continue
      const value = node.data.config?.[field.name]
      if (value === undefined || value === null || String(value).trim() === '') {
        issues.push({
          nodeId: node.id,
          message: `${node.data.label}: "${field.label}" is required`,
          severity: 'error',
        })
      }
    }

    // JSON fields must parse
    for (const field of descriptor.fields) {
      if (field.type !== 'json') continue
      const raw = node.data.config?.[field.name]
      if (!raw) continue
      try {
        JSON.parse(raw)
      } catch {
        issues.push({
          nodeId: node.id,
          message: `${node.data.label}: "${field.label}" is not valid JSON`,
          severity: 'error',
        })
      }
    }
  }

  // Reachability from the trigger
  const trigger = nodes.find((n) => n.data.nodeType === 'trigger')
  const start = trigger
    ? edges.filter((e) => e.source === trigger.id).map((e) => e.target)
    : []
  const reachable = new Set<string>()
  const stack = [...start]
  while (stack.length) {
    const id = stack.pop()!
    if (reachable.has(id)) continue
    reachable.add(id)
    edges.filter((e) => e.source === id).forEach((e) => stack.push(e.target))
  }

  for (const node of nodes) {
    if (node.data.nodeType === 'trigger') continue
    if (!reachable.has(node.id)) {
      issues.push({
        nodeId: node.id,
        message: `"${node.data.label}" is not connected to the flow`,
        severity: 'warning',
      })
    }
  }

  // Branch nodes with an unconnected output
  for (const node of nodes) {
    const outputs = outputsFor(node.data.nodeType, node.data.config || {})
    if (outputs.length < 2) continue
    for (const output of outputs) {
      const connected = edges.some(
        (e) => e.source === node.id && (e.sourceHandle ?? 'out') === output.id
      )
      if (!connected) {
        issues.push({
          nodeId: node.id,
          message: `"${node.data.label}" has no "${output.label ?? output.id}" output connected`,
          severity: 'warning',
        })
      }
    }
  }

  if (hasCycle(nodes, edges)) {
    issues.push({
      nodeId: null,
      message: 'Workflow contains a loop; remove the cycle',
      severity: 'error',
    })
  }

  return issues
}

function hasCycle(nodes: FlowNode[], edges: Edge[]): boolean {
  const adjacency = new Map<string, string[]>()
  nodes.forEach((n) => adjacency.set(n.id, []))
  edges.forEach((e) => adjacency.get(e.source)?.push(e.target))

  const WHITE = 0
  const GREY = 1
  const BLACK = 2
  const colour = new Map<string, number>(nodes.map((n) => [n.id, WHITE]))

  const visit = (id: string): boolean => {
    colour.set(id, GREY)
    for (const next of adjacency.get(id) ?? []) {
      const c = colour.get(next)
      if (c === GREY) return true
      if (c === WHITE && visit(next)) return true
    }
    colour.set(id, BLACK)
    return false
  }

  for (const node of nodes) {
    if (colour.get(node.id) === WHITE && visit(node.id)) return true
  }
  return false
}
