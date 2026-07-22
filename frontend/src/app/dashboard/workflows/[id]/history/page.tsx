'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import type { Edge } from '@xyflow/react'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Loader2,
  RotateCcw,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { WorkflowCanvas } from '@/components/workflow/WorkflowCanvas'
import {
  ExecutionPanel,
  type ExecutionResult,
} from '@/components/workflow/ExecutionPanel'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { apiToFlow, type ApiGraph, type FlowNode } from '@/lib/workflow/graph'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface ExecutionRow {
  id: string
  status: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  steps_executed: number
  steps_successful: number
  steps_failed: number
  error_message: string | null
  result_data: ExecutionResult['result_data']
}

export default function WorkflowHistoryPage() {
  const router = useRouter()
  const params = useParams()
  const workflowId = params.id as string

  const [graph, setGraph] = useState<{ nodes: FlowNode[]; edges: Edge[] } | null>(
    null
  )
  const [workflowName, setWorkflowName] = useState('')
  const [executions, setExecutions] = useState<ExecutionRow[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isReplaying, setIsReplaying] = useState(false)

  const load = useCallback(async () => {
    try {
      const [wf, list] = await Promise.all([
        apiClient.get<{ name: string; graph: ApiGraph }>(
          API_ENDPOINTS.WORKFLOW(workflowId)
        ),
        apiClient.get<{ executions: ExecutionRow[] }>(
          API_ENDPOINTS.WORKFLOW_EXECUTIONS(workflowId)
        ),
      ])
      setWorkflowName(wf.data.name)
      setGraph(apiToFlow(wf.data.graph))
      setExecutions(list.data.executions ?? [])
      setSelectedId((list.data.executions ?? [])[0]?.id ?? null)
    } catch (err) {
      toast.error(getErrorMessage(err))
      router.push(`/dashboard/workflows/${workflowId}`)
    } finally {
      setIsLoading(false)
    }
  }, [workflowId, router])

  useEffect(() => {
    load()
  }, [load])

  const selected = executions.find((e) => e.id === selectedId) ?? null

  // Overlay the selected run's outcomes onto the canvas — the replay.
  const runStatus = useMemo(() => {
    const steps = selected?.result_data?.steps
    if (!steps) return undefined
    const map: Record<
      string,
      { status: 'success' | 'failed'; error?: string | null }
    > = {}
    for (const step of steps) {
      map[step.step_id] = {
        status: step.status === 'failed' ? 'failed' : 'success',
        error: step.error ?? null,
      }
    }
    return map
  }, [selected])

  const replay = useCallback(async () => {
    setIsReplaying(true)
    try {
      await apiClient.post(API_ENDPOINTS.WORKFLOW_EXECUTE(workflowId), {
        trigger_data: selected?.result_data ? {} : {},
        wait_for_completion: true,
      })
      toast.success('Re-ran the workflow')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setIsReplaying(false)
    }
  }, [workflowId, selected, load])

  if (isLoading || !graph) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b bg-card px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/dashboard/workflows/${workflowId}`)}
          >
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            Back
          </Button>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold">{workflowName}</h1>
            <p className="text-xs text-muted-foreground">Execution history</p>
          </div>
        </div>

        {selected && (
          <Button variant="outline" size="sm" onClick={replay} disabled={isReplaying}>
            {isReplaying ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="mr-1.5 h-4 w-4" />
            )}
            Run again
          </Button>
        )}
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Run list */}
        <aside className="flex w-72 shrink-0 flex-col border-r bg-card">
          <div className="border-b px-3 py-2 text-xs font-medium text-muted-foreground">
            {executions.length} run{executions.length === 1 ? '' : 's'}
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {executions.length === 0 && (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">
                No runs yet. Use “Test run” in the builder.
              </p>
            )}
            {executions.map((exec) => (
              <button
                key={exec.id}
                type="button"
                onClick={() => setSelectedId(exec.id)}
                className={cn(
                  'mb-1 flex w-full items-start gap-2.5 rounded-lg border px-2.5 py-2 text-left transition-colors',
                  exec.id === selectedId
                    ? 'border-primary bg-accent'
                    : 'border-transparent hover:bg-accent/60'
                )}
              >
                <StatusIcon status={exec.status} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium capitalize">
                      {exec.status}
                    </span>
                    {exec.duration_ms != null && (
                      <span className="flex shrink-0 items-center gap-0.5 text-[11px] text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {exec.duration_ms}ms
                      </span>
                    )}
                  </div>
                  <p className="truncate text-[11px] text-muted-foreground">
                    {new Date(exec.started_at).toLocaleString()}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {exec.steps_successful}/{exec.steps_executed} steps
                  </p>
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Read-only canvas replay + results */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <WorkflowCanvas
              key={selectedId ?? 'none'}
              initialNodes={graph.nodes}
              initialEdges={graph.edges}
              runStatus={runStatus}
              readOnly
            />
          </div>

          {selected && (
            <ExecutionPanel
              execution={selected}
              onClose={() => setSelectedId(null)}
              onSelectNode={() => {}}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') {
    return <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
  }
  if (status === 'failed') {
    return <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" />
  }
  if (status === 'running') {
    return <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-blue-500" />
  }
  return <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
}
