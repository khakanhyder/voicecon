import { describe, expect, it } from 'vitest'
import {
  EXPORT_FORMAT,
  WorkflowImportError,
  buildExport,
  createPayload,
  exportFileName,
  parseImportFile,
  planImport,
  type ConnectionRef,
  type ExportableWorkflow,
} from './transfer'

const graph = {
  schema_version: 2,
  nodes: [
    { id: 'trigger', type: 'trigger', name: 'Start', position: { x: 0, y: 0 }, config: { inputs: [] } },
    {
      id: 'book',
      type: 'action',
      name: 'Book the slot',
      position: { x: 0, y: 100 },
      config: { connection_id: 'cal-A', action: 'create_event', parameters: { title: '{{trigger.name}}' } },
    },
    {
      id: 'log',
      type: 'action',
      name: 'Log it',
      position: { x: 0, y: 200 },
      config: { connection_id: 'sheets-A', action: 'append_row', parameters: {} },
    },
    { id: 'run', type: 'tool', name: 'Run a tool', position: { x: 0, y: 300 }, config: { tool_id: 'tool-A' } },
  ],
  edges: [
    { id: 'e1', source: 'trigger', sourceHandle: 'out', target: 'book', targetHandle: 'in' },
    { id: 'e2', source: 'book', sourceHandle: 'out', target: 'log', targetHandle: 'in' },
    { id: 'e3', source: 'log', sourceHandle: 'out', target: 'run', targetHandle: 'in' },
  ],
} as any

const workflow: ExportableWorkflow = {
  name: 'Pearl Dental — Book Appointment',
  description: 'Books and logs',
  trigger_type: 'manual',
  trigger_config: {},
  execution_mode: 'sync',
  error_handling: 'stop',
  graph,
}

const sourceConnections: ConnectionRef[] = [
  { id: 'cal-A', status: 'active', connector: { slug: 'google-calendar', name: 'Google Calendar' } },
  { id: 'sheets-A', status: 'active', connector: { slug: 'google-sheets', name: 'Google Sheets' } },
]

function roundTrip(targetConnections: ConnectionRef[], targetTools = [{ id: 'tool-B', name: 'Estimate' }]) {
  const file = buildExport(workflow, sourceConnections, [{ id: 'tool-A', name: 'Estimate' }])
  const parsed = parseImportFile(JSON.stringify(file))
  return planImport(parsed, targetConnections, targetTools)
}

const nodeConfig = (plan: ReturnType<typeof planImport>, id: string) =>
  plan.workflow.graph.nodes.find((n: any) => n.id === id)!.config as Record<string, any>

describe('workflow export', () => {
  it('records which app each connection is for, and each tool by name', () => {
    const file = buildExport(workflow, sourceConnections, [{ id: 'tool-A', name: 'Estimate' }])
    expect(file.format).toBe(EXPORT_FORMAT)
    expect(file.connections['cal-A'].app).toBe('google-calendar')
    expect(file.connections['sheets-A'].app).toBe('google-sheets')
    expect(file.tools['tool-A'].name).toBe('Estimate')
    expect(file.workflow.graph.nodes).toHaveLength(4)
  })

  it('never puts a webhook key in the file', () => {
    const file = buildExport(
      { ...workflow, trigger_type: 'webhook', trigger_config: { webhook_key: 'x'.repeat(32), method: 'POST' } },
      [],
      []
    )
    expect(file.workflow.trigger_config).toEqual({ method: 'POST' })
  })

  it('does not change the workflow it exported', () => {
    buildExport(workflow, sourceConnections, [])
    expect((graph.nodes[1].config as any).connection_id).toBe('cal-A')
  })

  it('makes a safe file name', () => {
    expect(exportFileName('Pearl Dental — Book Appointment')).toBe('pearl-dental-book-appointment.workflow.json')
  })
})

describe('workflow import', () => {
  it("re-points every connection at this workspace's own connection for the same app", () => {
    const plan = roundTrip([
      { id: 'cal-B', status: 'active', connector: { slug: 'google-calendar', name: 'Google Calendar' } },
      { id: 'sheets-B', status: 'active', connector: { slug: 'google-sheets', name: 'Google Sheets' } },
    ])
    expect(nodeConfig(plan, 'book').connection_id).toBe('cal-B')
    expect(nodeConfig(plan, 'log').connection_id).toBe('sheets-B')
    expect(nodeConfig(plan, 'run').tool_id).toBe('tool-B')
    expect(plan.unresolvedNodes).toEqual([])
  })

  it('keeps everything else about each step exactly as exported', () => {
    const plan = roundTrip([
      { id: 'cal-B', status: 'active', connector: { slug: 'google-calendar' } },
      { id: 'sheets-B', status: 'active', connector: { slug: 'google-sheets' } },
    ])
    expect(nodeConfig(plan, 'book').parameters).toEqual({ title: '{{trigger.name}}' })
    expect(plan.workflow.graph.edges).toEqual(graph.edges)
  })

  it('prefers an active connection over a disconnected one', () => {
    const plan = roundTrip([
      { id: 'old', status: 'disconnected', connector: { slug: 'google-calendar' } },
      { id: 'live', status: 'active', connector: { slug: 'google-calendar' } },
      { id: 'sheets-B', status: 'active', connector: { slug: 'google-sheets' } },
    ])
    expect(nodeConfig(plan, 'book').connection_id).toBe('live')
  })

  it('clears and reports a step whose app is not connected here', () => {
    const plan = roundTrip([{ id: 'cal-B', status: 'active', connector: { slug: 'google-calendar' } }])
    expect(nodeConfig(plan, 'log').connection_id).toBe('')
    expect(plan.unresolvedNodes).toContain('Log it')
    expect(plan.missingApps).toEqual(['Google Sheets'])
  })

  it('leaves ids alone when importing back into the same workspace', () => {
    const file = buildExport(workflow, sourceConnections, [{ id: 'tool-A', name: 'Estimate' }])
    const plan = planImport(parseImportFile(JSON.stringify(file)), sourceConnections, [{ id: 'tool-A', name: 'Estimate' }])
    expect(nodeConfig(plan, 'book').connection_id).toBe('cal-A')
    expect(plan.notes).toEqual([])
  })

  it('accepts a bare {name, graph} file like the ones in docs/demo-agent', () => {
    const parsed = parseImportFile(JSON.stringify({ name: 'Bare', description: null, graph }))
    expect(parsed.workflow.name).toBe('Bare')
    expect(parsed.workflow.trigger_type).toBe('manual')
  })

  it.each([
    ['not json', 'not valid JSON'],
    [JSON.stringify({ name: 'x' }), 'no workflow graph'],
    [JSON.stringify({ graph: { nodes: [{ id: 'a', type: 'speak' }], edges: [] } }), 'no trigger'],
    [JSON.stringify({ format: EXPORT_FORMAT, version: 99, workflow: { graph } }), 'newer version'],
  ])('rejects a bad file with a clear message (%#)', (text, message) => {
    expect(() => parseImportFile(text)).toThrow(WorkflowImportError)
    expect(() => parseImportFile(text)).toThrow(message)
  })
})

describe('create payload', () => {
  it('renames on a clash instead of creating two identical names', () => {
    expect(createPayload(workflow, ['pearl dental — book appointment']).name).toBe(
      'Pearl Dental — Book Appointment (imported)'
    )
    expect(
      createPayload(workflow, ['Pearl Dental — Book Appointment', 'Pearl Dental — Book Appointment (imported)']).name
    ).toBe('Pearl Dental — Book Appointment (imported) 2')
  })

  it('switches on only manual workflows', () => {
    expect(createPayload(workflow, []).is_active).toBe(true)
    expect(createPayload({ ...workflow, trigger_type: 'schedule' }, []).is_active).toBe(false)
  })
})
