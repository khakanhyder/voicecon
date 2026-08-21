'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import type { Edge } from '@xyflow/react'
import { ArrowLeft, Loader2, Play, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { WorkflowCanvas } from '@/components/workflow/WorkflowCanvas'
import {
  ExecutionPanel,
  type ExecutionResult,
} from '@/components/workflow/ExecutionPanel'
import { useWorkflowRun } from '@/hooks/useWorkflowRun'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { apiToFlow, flowToApi, type ApiGraph, type FlowNode } from '@/lib/workflow/graph'
import { validateTrigger } from '@/lib/workflow/triggerTypes'
import type { TriggerState } from '@/components/workflow/TriggerConfig'
import { toast } from 'sonner'

interface Workflow {
  id: string
  name: string
  description: string | null
  graph: ApiGraph
  is_active: boolean
  trigger_type: string
  trigger_config: Record<string, any>
}

const AUTOSAVE_DELAY_MS = 2000

export default function WorkflowBuilderPage() {
  const router = useRouter()
  const params = useParams()
  const workflowId = params.id as string
  const liveRun = useWorkflowRun(workflowId)

  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [initial, setInitial] = useState<{ nodes: FlowNode[]; edges: Edge[] } | null>(
    null
  )
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  const [execution, setExecution] = useState<ExecutionResult | null>(null)
  const [trigger, setTrigger] = useState<TriggerState | null>(null)
  // What the server currently holds. Diverges from `trigger` only while an
  // edit is incomplete, which is exactly when the panel needs to say which of
  // the two is actually running.
  const [savedTrigger, setSavedTrigger] = useState<TriggerState | null>(null)

  // `save` reads the trigger, and is itself a dependency of the autosave
  // effect. Reading it through a ref keeps every trigger keystroke from
  // rebuilding the callback and restarting the autosave timer.
  const triggerRef = useRef<TriggerState | null>(null)
  triggerRef.current = trigger

  // The canvas owns graph state; it hands back a getter so saving does not
  // require mirroring every change up into this component.
  const getSnapshot = useRef<(() => { nodes: FlowNode[]; edges: Edge[] }) | null>(null)
  const selectNode = useRef<((nodeId: string) => void) | null>(null)
  const autosaveTimer = useRef<number | null>(null)

  useEffect(() => {
    if (!workflowId) return

    let cancelled = false

    apiClient
      .get<Workflow>(API_ENDPOINTS.WORKFLOW(workflowId))
      .then((res) => {
        if (cancelled) return
        setWorkflow(res.data)
        setInitial(apiToFlow(res.data.graph))
        const loaded = {
          type: res.data.trigger_type,
          config: res.data.trigger_config || {},
        }
        setTrigger(loaded)
        setSavedTrigger(loaded)
      })
      .catch((err) => {
        if (cancelled) return
        toast.error(getErrorMessage(err))
        router.push('/dashboard/workflows')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [workflowId, router])

  const save = useCallback(
    async (options: { silent?: boolean } = {}) => {
      const snapshot = getSnapshot.current?.()
      if (!snapshot) return

      const current = triggerRef.current
      // A half-typed cron expression must not block saving the graph. The
      // trigger is held back until it validates, and the panel says so; the
      // API rejects an invalid config outright, so sending it would lose the
      // user's canvas work to an unrelated error.
      const triggerError = current
        ? validateTrigger(current.type, current.config)
        : 'no trigger'

      setIsSaving(true)
      try {
        const res = await apiClient.patch<{
          trigger_type: string
          trigger_config: Record<string, any>
        }>(API_ENDPOINTS.WORKFLOW(workflowId), {
          graph: flowToApi(snapshot.nodes, snapshot.edges),
          ...(current && !triggerError
            ? { trigger_type: current.type, trigger_config: current.config }
            : {}),
        })

        // The server fills in what it owns — a webhook key, for instance — so
        // adopt its version rather than leaving the panel showing a config
        // that is missing the generated fields.
        if (current && !triggerError && res.data?.trigger_type) {
          const persisted = {
            type: res.data.trigger_type,
            config: res.data.trigger_config || {},
          }
          setTrigger(persisted)
          setSavedTrigger(persisted)
        }

        setIsDirty(false)
        setLastSavedAt(new Date())
        if (!options.silent) {
          if (triggerError && current) {
            toast.warning(`Steps saved. Trigger not saved: ${triggerError}`)
          } else {
            toast.success('Workflow saved')
          }
        }
      } catch (err) {
        toast.error(getErrorMessage(err))
      } finally {
        setIsSaving(false)
      }
    },
    [workflowId]
  )

  // Autosave. Manual save still exists, but losing work to a stray
  // back-navigation was the single most common way to lose edits before.
  useEffect(() => {
    if (!isDirty) return

    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current)
    autosaveTimer.current = window.setTimeout(() => {
      void save({ silent: true })
    }, AUTOSAVE_DELAY_MS)

    return () => {
      if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current)
    }
  }, [isDirty, save])

  // Guard against closing the tab mid-edit.
  useEffect(() => {
    if (!isDirty) return

    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }

    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  const runTest = useCallback(async () => {
    // Save first so the run uses the current graph, then stream node-by-node.
    await save({ silent: true })
    setExecution(null)
    liveRun.run({})
  }, [save])

  // A completed streamed run becomes the execution shown in the results panel.
  useEffect(() => {
    if (liveRun.execution) setExecution(liveRun.execution)
  }, [liveRun.execution])

  // While running, node status comes live from the socket. Once done, fall back
  // to the final per-step results (which also cover a page that reconnected).
  const runStatus = useMemo(() => {
    if (liveRun.running || Object.keys(liveRun.status).length > 0) {
      return liveRun.status
    }
    if (!execution?.result_data?.steps) return undefined
    const map: Record<
      string,
      { status: 'success' | 'failed'; error?: string | null }
    > = {}
    for (const step of execution.result_data.steps) {
      map[step.step_id] = {
        status: step.status === 'failed' ? 'failed' : 'success',
        error: step.error ?? null,
      }
    }
    return map
  }, [liveRun.running, liveRun.status, execution])

  if (isLoading || !initial) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
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
            <h1 className="truncate text-sm font-semibold">{workflow?.name}</h1>
            <p className="text-xs text-muted-foreground">
              {isSaving
                ? 'Saving…'
                : isDirty
                  ? 'Unsaved changes'
                  : lastSavedAt
                    ? `Saved ${lastSavedAt.toLocaleTimeString()}`
                    : 'All changes saved'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={runTest} disabled={liveRun.running}>
            {liveRun.running ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-1.5 h-4 w-4" />
            )}
            Test run
          </Button>
          <Button size="sm" onClick={() => save()} disabled={isSaving}>
            <Save className="mr-1.5 h-4 w-4" />
            Save
          </Button>
        </div>
      </header>

      <div className="min-h-0 flex-1">
        <WorkflowCanvas
          initialNodes={initial.nodes}
          initialEdges={initial.edges}
          onDirtyChange={setIsDirty}
          trigger={trigger ?? undefined}
          savedTrigger={savedTrigger}
          workflowIsActive={workflow?.is_active ?? true}
          onTriggerChange={(next) => {
            setTrigger(next)
            setIsDirty(true)
          }}
          runStatus={runStatus}
          registerSave={(fn) => {
            getSnapshot.current = fn
          }}
          registerSelect={(fn) => {
            selectNode.current = fn
          }}
        />
      </div>

      {execution && (
        <ExecutionPanel
          execution={execution}
          onClose={() => setExecution(null)}
          onSelectNode={(nodeId) => selectNode.current?.(nodeId)}
        />
      )}
    </div>
  )
}
