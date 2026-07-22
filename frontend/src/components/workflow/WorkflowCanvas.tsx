'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type OnSelectionChangeParams,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  AlertTriangle,
  CheckCircle2,
  LayoutGrid,
  Maximize2,
  Redo2,
  Undo2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { TriggerNode, WorkflowNode } from './WorkflowNode'
import { WorkflowEdge } from './WorkflowEdge'
import { NodePalette } from './NodePalette'
import { NodeInspector } from './NodeInspector'
import {
  autoLayout,
  validateFlow,
  type FlowNode,
  type Issue,
  NODE_HEIGHT,
  NODE_WIDTH,
} from '@/lib/workflow/graph'
import { defaultConfig, getDescriptor, newNodeId } from '@/lib/workflow/nodeTypes'
import { buildDataPaths } from './fields/ExpressionInput'
import { cn } from '@/lib/utils'

const nodeTypes = { stepNode: WorkflowNode, triggerNode: TriggerNode }
const edgeTypes = { workflowEdge: WorkflowEdge }

interface Snapshot {
  nodes: FlowNode[]
  edges: Edge[]
}

interface WorkflowCanvasProps {
  initialNodes: FlowNode[]
  initialEdges: Edge[]
  onDirtyChange?: (dirty: boolean) => void
  onGraphChange?: (nodes: FlowNode[], edges: Edge[]) => void
  registerSave?: (fn: () => Snapshot) => void
  /** Per-node outcome from the last run, keyed by node id. */
  runStatus?: Record<string, { status: FlowNode['data']['status']; error?: string | null }>
  /** Lets the page focus a node from the execution results panel. */
  registerSelect?: (fn: (nodeId: string) => void) => void
  /** View-only: no palette, no editing, no inspector. Used by history replay. */
  readOnly?: boolean
}

export function WorkflowCanvas(props: WorkflowCanvasProps) {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  )
}

function CanvasInner({
  initialNodes,
  initialEdges,
  onDirtyChange,
  onGraphChange,
  registerSave,
  runStatus,
  registerSelect,
  readOnly = false,
}: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showIssues, setShowIssues] = useState(false)

  const wrapperRef = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition, fitView } = useReactFlow()

  // ---- history ----------------------------------------------------------
  // Snapshots are pushed on committed edits, not on every drag frame.
  const past = useRef<Snapshot[]>([])
  const future = useRef<Snapshot[]>([])
  const [, forceRender] = useState(0)
  const skipHistory = useRef(false)

  const pushHistory = useCallback(() => {
    past.current.push({ nodes: structuredClone(nodes), edges: structuredClone(edges) })
    if (past.current.length > 100) past.current.shift()
    future.current = []
    forceRender((n) => n + 1)
  }, [nodes, edges])

  const undo = useCallback(() => {
    const previous = past.current.pop()
    if (!previous) return
    future.current.push({ nodes: structuredClone(nodes), edges: structuredClone(edges) })
    skipHistory.current = true
    setNodes(previous.nodes)
    setEdges(previous.edges)
    forceRender((n) => n + 1)
  }, [nodes, edges, setNodes, setEdges])

  const redo = useCallback(() => {
    const next = future.current.pop()
    if (!next) return
    past.current.push({ nodes: structuredClone(nodes), edges: structuredClone(edges) })
    skipHistory.current = true
    setNodes(next.nodes)
    setEdges(next.edges)
    forceRender((n) => n + 1)
  }, [nodes, edges, setNodes, setEdges])

  // ---- dirty tracking ---------------------------------------------------
  const firstRender = useRef(true)
  // Set when nodes change for a reason that is not a user edit (currently the
  // run-status overlay), so a test run does not trigger an autosave.
  const suppressDirty = useRef(false)

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    if (suppressDirty.current) {
      suppressDirty.current = false
      return
    }
    onDirtyChange?.(true)
    onGraphChange?.(nodes, edges)
  }, [nodes, edges, onDirtyChange, onGraphChange])

  useEffect(() => {
    registerSave?.(() => ({ nodes, edges }))
  }, [nodes, edges, registerSave])

  useEffect(() => {
    registerSelect?.((nodeId: string) => setSelectedId(nodeId))
  }, [registerSelect])

  // Overlay run outcomes onto the nodes. Kept out of the history stack: a test
  // run is not an edit, and undoing it should not be possible.
  useEffect(() => {
    suppressDirty.current = true
    setNodes((current) =>
      current.map((n) => {
        const outcome = runStatus?.[n.id]
        if (!outcome && !n.data.status) return n
        return {
          ...n,
          data: { ...n.data, status: outcome?.status, error: outcome?.error ?? null },
        }
      })
    )
    // Only react to a new run, not to every node edit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runStatus])

  // ---- validation -------------------------------------------------------
  const issues: Issue[] = useMemo(() => validateFlow(nodes, edges), [nodes, edges])
  const errorCount = issues.filter((i) => i.severity === 'error').length
  const warningCount = issues.length - errorCount

  // ---- node operations --------------------------------------------------
  const addNode = useCallback(
    (type: string, position?: { x: number; y: number }) => {
      pushHistory()
      const descriptor = getDescriptor(type)
      const id = newNodeId()

      setNodes((current) => {
        // Default placement: below the lowest node, so click-to-add lands
        // somewhere visible instead of stacking at the origin.
        const fallback = current.reduce(
          (acc, n) => Math.max(acc, n.position.y),
          0
        )
        return [
          ...current,
          {
            id,
            type: 'stepNode',
            position: position ?? { x: 320, y: fallback + 160 },
            data: {
              label: descriptor.label,
              nodeType: type,
              config: defaultConfig(type),
              settings: {},
            },
          } as FlowNode,
        ]
      })

      setSelectedId(id)
      return id
    },
    [pushHistory, setNodes]
  )

  const deleteNode = useCallback(
    (id: string) => {
      const node = nodes.find((n) => n.id === id)
      if (node?.data.nodeType === 'trigger') return

      pushHistory()
      setNodes((current) => current.filter((n) => n.id !== id))
      // Removing the node's edges too is what keeps dangling references
      // impossible by construction.
      setEdges((current) => current.filter((e) => e.source !== id && e.target !== id))
      setSelectedId((current) => (current === id ? null : current))
    },
    [nodes, pushHistory, setNodes, setEdges]
  )

  const duplicateNode = useCallback(
    (id: string) => {
      const node = nodes.find((n) => n.id === id)
      if (!node || node.data.nodeType === 'trigger') return

      pushHistory()
      const copyId = newNodeId()
      setNodes((current) => [
        ...current,
        {
          ...structuredClone(node),
          id: copyId,
          position: { x: node.position.x + 40, y: node.position.y + 60 },
          selected: false,
          data: { ...structuredClone(node.data), label: `${node.data.label} copy` },
        } as FlowNode,
      ])
      setSelectedId(copyId)
    },
    [nodes, pushHistory, setNodes]
  )

  const updateNode = useCallback(
    (id: string, patch: Partial<FlowNode['data']>) => {
      setNodes((current) =>
        current.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, ...patch } } : n
        )
      )
    },
    [setNodes]
  )

  // ---- edge operations --------------------------------------------------
  const onConnect = useCallback(
    (connection: Connection) => {
      pushHistory()
      setEdges((current) => {
        // One edge per source handle keeps execution deterministic: the engine
        // follows a single path out of each output.
        const filtered = current.filter(
          (e) =>
            !(
              e.source === connection.source &&
              (e.sourceHandle ?? 'out') === (connection.sourceHandle ?? 'out')
            )
        )
        return addEdge(
          {
            ...connection,
            type: 'workflowEdge',
            label:
              connection.sourceHandle === 'true'
                ? 'true'
                : connection.sourceHandle === 'false'
                  ? 'false'
                  : undefined,
          },
          filtered
        )
      })
    },
    [pushHistory, setEdges]
  )

  const deleteEdge = useCallback(
    (edgeId: string) => {
      pushHistory()
      setEdges((current) => current.filter((e) => e.id !== edgeId))
    },
    [pushHistory, setEdges]
  )

  /** Splice a new node into an existing connection. */
  const insertOnEdge = useCallback(
    (edgeId: string, type: string = 'speak') => {
      const edge = edges.find((e) => e.id === edgeId)
      if (!edge) return

      const source = nodes.find((n) => n.id === edge.source)
      const target = nodes.find((n) => n.id === edge.target)
      if (!source || !target) return

      pushHistory()
      const descriptor = getDescriptor(type)
      const id = newNodeId()
      const midpoint = {
        x: (source.position.x + target.position.x) / 2,
        y: (source.position.y + target.position.y) / 2,
      }

      setNodes((current) => [
        ...current,
        {
          id,
          type: 'stepNode',
          position: midpoint,
          data: {
            label: descriptor.label,
            nodeType: type,
            config: defaultConfig(type),
            settings: {},
          },
        } as FlowNode,
      ])

      setEdges((current) => [
        ...current.filter((e) => e.id !== edgeId),
        {
          id: `e_${edge.source}_${id}`,
          source: edge.source,
          sourceHandle: edge.sourceHandle,
          target: id,
          targetHandle: 'in',
          type: 'workflowEdge',
          label: edge.label,
        },
        {
          id: `e_${id}_${edge.target}`,
          source: id,
          sourceHandle: 'out',
          target: edge.target,
          targetHandle: 'in',
          type: 'workflowEdge',
        },
      ])

      setSelectedId(id)
    },
    [edges, nodes, pushHistory, setNodes, setEdges]
  )

  // Edge callbacks are injected as data so the edge component stays memoized.
  const edgesWithHandlers = useMemo(
    () =>
      edges.map((e) => ({
        ...e,
        type: 'workflowEdge',
        data: { ...e.data, onInsert: insertOnEdge, onDelete: deleteEdge },
      })),
    [edges, insertOnEdge, deleteEdge]
  )

  // ---- drag and drop ----------------------------------------------------
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const type = event.dataTransfer.getData('application/workflow-node')
      if (!type) return

      // screenToFlowPosition accounts for pan and zoom; using raw client
      // coordinates would drop the node in the wrong place whenever the
      // canvas is panned.
      const position = screenToFlowPosition({
        x: event.clientX - NODE_WIDTH / 2,
        y: event.clientY - NODE_HEIGHT / 2,
      })

      addNode(type, position)
    },
    [addNode, screenToFlowPosition]
  )

  // ---- selection & keyboard --------------------------------------------
  const onSelectionChange = useCallback((params: OnSelectionChangeParams) => {
    setSelectedId(params.nodes.length === 1 ? params.nodes[0].id : null)
  }, [])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      // Never hijack keys while the user is typing in the inspector.
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      ) {
        return
      }

      const meta = event.metaKey || event.ctrlKey

      if (meta && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        event.shiftKey ? redo() : undo()
        return
      }
      if (meta && event.key.toLowerCase() === 'd' && selectedId) {
        event.preventDefault()
        duplicateNode(selectedId)
        return
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectedId) {
        event.preventDefault()
        deleteNode(selectedId)
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, duplicateNode, deleteNode, selectedId])

  // ---- layout -----------------------------------------------------------
  const tidyUp = useCallback(() => {
    pushHistory()
    setNodes((current) => autoLayout(current, edges))
    window.setTimeout(() => fitView({ duration: 300, padding: 0.2 }), 50)
  }, [pushHistory, setNodes, edges, fitView])

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null

  // Values the selected node can reference. A node counts as "inside a loop"
  // when any loop node's `loop` output reaches it.
  const dataPaths = useMemo(() => {
    if (!selectedNode) return []

    const loopBodies = new Set<string>()
    for (const loop of nodes.filter((n) => n.data.nodeType === 'loop')) {
      const stack = edges
        .filter((e) => e.source === loop.id && e.sourceHandle === 'loop')
        .map((e) => e.target)
      while (stack.length) {
        const id = stack.pop()!
        if (loopBodies.has(id)) continue
        loopBodies.add(id)
        edges.filter((e) => e.source === id).forEach((e) => stack.push(e.target))
      }
    }

    return buildDataPaths(nodes, selectedNode.id, loopBodies.has(selectedNode.id))
  }, [nodes, edges, selectedNode])

  return (
    <div className="flex h-full min-h-0 w-full">
      {!readOnly && <NodePalette onAdd={(type) => addNode(type)} />}

      <div ref={wrapperRef} className="relative min-w-0 flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edgesWithHandlers}
          onNodesChange={readOnly ? undefined : onNodesChange}
          onEdgesChange={readOnly ? undefined : onEdgesChange}
          onConnect={readOnly ? undefined : onConnect}
          onDrop={readOnly ? undefined : onDrop}
          onDragOver={readOnly ? undefined : onDragOver}
          onSelectionChange={readOnly ? undefined : onSelectionChange}
          onNodeDragStart={readOnly ? undefined : pushHistory}
          nodesDraggable={!readOnly}
          nodesConnectable={!readOnly}
          elementsSelectable={!readOnly}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultEdgeOptions={{ type: 'workflowEdge' }}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.2}
          maxZoom={2}
          snapToGrid
          snapGrid={[16, 16]}
          proOptions={{ hideAttribution: true }}
          deleteKeyCode={null}
          className="bg-muted/30"
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
          <Controls showInteractive={false} />

          {!readOnly && (
          <Panel position="top-left" className="flex items-center gap-1.5">
            <div className="flex items-center gap-1 rounded-lg border bg-card p-1 shadow-sm">
              <Button
                size="sm"
                variant="ghost"
                onClick={undo}
                disabled={past.current.length === 0}
                title="Undo (Cmd+Z)"
              >
                <Undo2 className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={redo}
                disabled={future.current.length === 0}
                title="Redo (Cmd+Shift+Z)"
              >
                <Redo2 className="h-4 w-4" />
              </Button>
              <div className="mx-0.5 h-5 w-px bg-border" />
              <Button size="sm" variant="ghost" onClick={tidyUp} title="Tidy up layout">
                <LayoutGrid className="mr-1.5 h-4 w-4" />
                Tidy up
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => fitView({ duration: 300, padding: 0.2 })}
                title="Fit to view"
              >
                <Maximize2 className="h-4 w-4" />
              </Button>
            </div>

            <button
              type="button"
              onClick={() => setShowIssues((v) => !v)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1.5 text-xs font-medium shadow-sm transition-colors',
                errorCount > 0
                  ? 'text-destructive hover:bg-destructive/10'
                  : warningCount > 0
                    ? 'text-amber-600 hover:bg-amber-500/10 dark:text-amber-400'
                    : 'text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400'
              )}
            >
              {errorCount > 0 || warningCount > 0 ? (
                <AlertTriangle className="h-3.5 w-3.5" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              {errorCount > 0
                ? `${errorCount} error${errorCount > 1 ? 's' : ''}`
                : warningCount > 0
                  ? `${warningCount} warning${warningCount > 1 ? 's' : ''}`
                  : 'No issues'}
            </button>
          </Panel>
          )}

          {!readOnly && showIssues && issues.length > 0 && (
            <Panel position="bottom-left" className="max-w-md">
              <div className="max-h-56 overflow-y-auto rounded-lg border bg-card p-2 shadow-lg">
                {issues.map((issue, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => issue.nodeId && setSelectedId(issue.nodeId)}
                    className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent"
                  >
                    <AlertTriangle
                      className={cn(
                        'mt-0.5 h-3.5 w-3.5 shrink-0',
                        issue.severity === 'error'
                          ? 'text-destructive'
                          : 'text-amber-500'
                      )}
                    />
                    <span>{issue.message}</span>
                  </button>
                ))}
              </div>
            </Panel>
          )}

          {nodes.filter((n) => n.data.nodeType !== 'trigger').length === 0 && (
            <Panel position="top-center" className="pointer-events-none mt-24">
              <div className="rounded-xl border border-dashed bg-card/80 px-6 py-5 text-center backdrop-blur">
                <p className="text-sm font-medium">Start building your workflow</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Drag a step from the left, or drag down from the trigger&apos;s dot.
                </p>
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {selectedNode && !readOnly && (
        <NodeInspector
          node={selectedNode}
          onChangeName={(label) => updateNode(selectedNode.id, { label })}
          onChangeConfig={(config) => updateNode(selectedNode.id, { config })}
          onChangeSettings={(settings) =>
            updateNode(selectedNode.id, { settings })
          }
          dataPaths={dataPaths}
          onDuplicate={() => duplicateNode(selectedNode.id)}
          onDelete={() => deleteNode(selectedNode.id)}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
