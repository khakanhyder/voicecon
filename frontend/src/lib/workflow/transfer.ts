/**
 * Workflow import and export as a portable JSON file.
 *
 * A workflow refers to things that belong to one workspace: integration
 * connections (every Integration node stores a connection id) and tools (Run
 * Tool nodes store a tool id). Those ids mean nothing in another workspace, so
 * the export records *what* each one is — the app a connection is for, the
 * name of a tool — and the import re-points each reference at the importing
 * workspace's own connection or tool of the same kind. Anything it cannot
 * match is cleared and reported, so the builder shows an empty picker to fill
 * in rather than a step that fails at run time with someone else's id.
 */
import type { ApiGraph, ApiNode } from './graph'

export const EXPORT_FORMAT = 'voicecon.workflow'
export const EXPORT_VERSION = 1

export interface ExportableWorkflow {
  name: string
  description?: string | null
  trigger_type: string
  trigger_config?: Record<string, any> | null
  execution_mode?: string
  error_handling?: string
  max_retries?: number
  retry_delay?: number
  graph: ApiGraph
}

export interface ConnectionRef {
  id: string
  name?: string | null
  status?: string | null
  connector?: { slug?: string | null; name?: string | null } | null
}

export interface ToolRef {
  id: string
  name: string
}

export interface WorkflowExportFile {
  format: typeof EXPORT_FORMAT
  version: number
  exported_at: string
  workflow: ExportableWorkflow
  /** Connection id → the app it is for, so an import can find its own. */
  connections: Record<string, { app: string | null; name: string | null }>
  /** Tool id → tool name, for the same reason. */
  tools: Record<string, { name: string }>
}

export interface ImportPlan {
  workflow: ExportableWorkflow
  /** Human-readable notes about what was re-pointed or needs attention. */
  notes: string[]
  /** Apps with no connection in this workspace; connect them, then pick them in the builder. */
  missingApps: string[]
  /** Nodes left without a connection or tool, by node name. */
  unresolvedNodes: string[]
}

export class WorkflowImportError extends Error {}

/** Trigger config keys that act as credentials and must not travel in a file. */
const SECRET_TRIGGER_KEYS = ['webhook_key', 'secret', 'signing_secret']

function nodesOf(graph: ApiGraph | undefined | null): ApiNode[] {
  return Array.isArray(graph?.nodes) ? (graph!.nodes as ApiNode[]) : []
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

/** Build the file contents for one workflow. */
export function buildExport(
  workflow: ExportableWorkflow,
  connections: ConnectionRef[],
  tools: ToolRef[],
  now: Date = new Date()
): WorkflowExportFile {
  const graph = clone(workflow.graph)
  const connectionIds = new Set<string>()
  const toolIds = new Set<string>()
  for (const node of nodesOf(graph)) {
    const cfg = (node.config || {}) as Record<string, any>
    if (node.type === 'action' && cfg.connection_id) connectionIds.add(String(cfg.connection_id))
    if (node.type === 'tool' && cfg.tool_id) toolIds.add(String(cfg.tool_id))
  }

  const connectionMap: WorkflowExportFile['connections'] = {}
  for (const id of connectionIds) {
    const found = connections.find((c) => c.id === id)
    connectionMap[id] = {
      app: found?.connector?.slug ?? null,
      name: found?.connector?.name ?? found?.name ?? null,
    }
  }

  const toolMap: WorkflowExportFile['tools'] = {}
  for (const id of toolIds) {
    const found = tools.find((t) => t.id === id)
    if (found) toolMap[id] = { name: found.name }
  }

  const triggerConfig = { ...(workflow.trigger_config || {}) }
  for (const key of SECRET_TRIGGER_KEYS) delete triggerConfig[key]

  return {
    format: EXPORT_FORMAT,
    version: EXPORT_VERSION,
    exported_at: now.toISOString(),
    workflow: {
      name: workflow.name,
      description: workflow.description ?? null,
      trigger_type: workflow.trigger_type || 'manual',
      trigger_config: triggerConfig,
      execution_mode: workflow.execution_mode,
      error_handling: workflow.error_handling,
      max_retries: workflow.max_retries,
      retry_delay: workflow.retry_delay,
      graph,
    },
    connections: connectionMap,
    tools: toolMap,
  }
}

/** A safe file name for a workflow export. */
export function exportFileName(name: string): string {
  const slug = (name || 'workflow')
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/[\s_]+/g, '-')
    .toLowerCase()
    .slice(0, 60)
  return `${slug || 'workflow'}.workflow.json`
}

/**
 * Read an uploaded file. Accepts this module's export format, and also a bare
 * `{name, description, graph}` object such as the reference files kept in
 * docs/demo-agent.
 */
export function parseImportFile(text: string): {
  workflow: ExportableWorkflow
  connections: WorkflowExportFile['connections']
  tools: WorkflowExportFile['tools']
} {
  let data: any
  try {
    data = JSON.parse(text)
  } catch {
    throw new WorkflowImportError('That file is not valid JSON.')
  }
  if (!data || typeof data !== 'object') {
    throw new WorkflowImportError('That file does not contain a workflow.')
  }

  const isExport = data.format === EXPORT_FORMAT
  if (isExport && Number(data.version) > EXPORT_VERSION) {
    throw new WorkflowImportError(
      'This file was exported by a newer version of Voicecon and cannot be imported here.'
    )
  }
  const raw = isExport ? data.workflow : data
  const graph = raw?.graph

  if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) {
    throw new WorkflowImportError(
      'That file has no workflow graph. Export a workflow from Voicecon and import that file.'
    )
  }
  if (!graph.nodes.some((n: any) => n?.type === 'trigger')) {
    throw new WorkflowImportError('The workflow in that file has no trigger node.')
  }

  return {
    workflow: {
      name: String(raw.name || 'Imported workflow').slice(0, 255),
      description: raw.description ?? null,
      trigger_type: raw.trigger_type || 'manual',
      trigger_config: raw.trigger_config || {},
      execution_mode: raw.execution_mode,
      error_handling: raw.error_handling,
      max_retries: raw.max_retries,
      retry_delay: raw.retry_delay,
      graph: clone(graph),
    },
    connections: (isExport && data.connections) || {},
    tools: (isExport && data.tools) || {},
  }
}

function pickConnection(app: string, connections: ConnectionRef[]): ConnectionRef | undefined {
  const sameApp = connections.filter((c) => c.connector?.slug === app)
  return (
    sameApp.find((c) => (c.status || 'active') === 'active') ??
    sameApp.find((c) => c.status !== 'disconnected')
  )
}

/** Re-point every connection and tool reference at this workspace's own. */
export function planImport(
  parsed: ReturnType<typeof parseImportFile>,
  myConnections: ConnectionRef[],
  myTools: ToolRef[]
): ImportPlan {
  const workflow = clone(parsed.workflow)
  const notes: string[] = []
  const missingApps = new Set<string>()
  const unresolvedNodes: string[] = []
  const myConnectionIds = new Set(myConnections.map((c) => c.id))
  const myToolIds = new Set(myTools.map((t) => t.id))

  for (const node of nodesOf(workflow.graph)) {
    const cfg = (node.config || (node.config = {})) as Record<string, any>
    const label = node.name || node.id

    if (node.type === 'action') {
      const id = cfg.connection_id ? String(cfg.connection_id) : ''
      if (id && myConnectionIds.has(id)) continue

      const app = (id && parsed.connections[id]?.app) || null
      const match = app ? pickConnection(app, myConnections) : undefined
      if (match) {
        cfg.connection_id = match.id
        notes.push(`"${label}" now uses your ${match.connector?.name || app} connection.`)
      } else {
        cfg.connection_id = ''
        unresolvedNodes.push(label)
        if (app) missingApps.add(parsed.connections[id]?.name || app)
      }
    }

    if (node.type === 'tool') {
      const id = cfg.tool_id ? String(cfg.tool_id) : ''
      if (id && myToolIds.has(id)) continue

      const wanted = (id && parsed.tools[id]?.name) || null
      const match = wanted ? myTools.find((t) => t.name === wanted) : undefined
      if (match) {
        cfg.tool_id = match.id
        notes.push(`"${label}" now runs your tool "${match.name}".`)
      } else {
        cfg.tool_id = ''
        unresolvedNodes.push(label)
      }
    }
  }

  return { workflow, notes, missingApps: [...missingApps], unresolvedNodes }
}

/**
 * The body to create the imported workflow with.
 *
 * Only manual workflows arrive switched on. A scheduled, webhook or call
 * triggered workflow would start firing the moment it landed, possibly before
 * its connections are picked, so those are created off for the user to review
 * and activate.
 */
export function createPayload(workflow: ExportableWorkflow, existingNames: string[]) {
  const taken = new Set(existingNames.map((n) => n.trim().toLowerCase()))
  let name = workflow.name
  if (taken.has(name.trim().toLowerCase())) {
    const base = `${workflow.name} (imported)`
    name = base
    for (let i = 2; taken.has(name.toLowerCase()); i++) name = `${base} ${i}`
  }

  const body: Record<string, any> = {
    name,
    description: workflow.description ?? null,
    trigger_type: workflow.trigger_type || 'manual',
    trigger_config: workflow.trigger_config || {},
    graph: workflow.graph,
    is_active: (workflow.trigger_type || 'manual') === 'manual',
  }
  for (const key of ['execution_mode', 'error_handling', 'max_retries', 'retry_delay'] as const) {
    if (workflow[key] !== undefined && workflow[key] !== null) body[key] = workflow[key]
  }
  return body
}

/** Hand the browser a JSON file to save. */
export function downloadJson(fileName: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
