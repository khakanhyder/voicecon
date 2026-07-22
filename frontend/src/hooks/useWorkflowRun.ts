import { useCallback, useRef, useState } from 'react'
import { API_BASE } from '@/lib/constants'
import type { ExecutionResult } from '@/components/workflow/ExecutionPanel'

export type NodeRunStatus = 'running' | 'success' | 'failed' | 'skipped'

export interface RunState {
  /** Per-node status, updated live as the run progresses. */
  status: Record<string, { status: NodeRunStatus; error?: string | null }>
  /** True while a run is in flight. */
  running: boolean
  /** The completed execution, once it finishes. */
  execution: ExecutionResult | null
}

const EMPTY: RunState = { status: {}, running: false, execution: null }

/**
 * Run a workflow over a WebSocket, receiving live node-by-node status.
 *
 * Falls back cleanly: if the socket errors, the run is marked finished so the
 * UI never gets stuck in a spinning state.
 */
export function useWorkflowRun(workflowId: string) {
  const [state, setState] = useState<RunState>(EMPTY)
  const wsRef = useRef<WebSocket | null>(null)

  const reset = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
    setState(EMPTY)
  }, [])

  const run = useCallback(
    (triggerData: Record<string, unknown> = {}) => {
      // Close any prior run before starting a new one.
      wsRef.current?.close()

      const token = localStorage.getItem('access_token') || ''
      const wsBase = API_BASE.replace(/^http(s?)/, (_, s) => `ws${s}`)
      const url = `${wsBase}/api/v1/workflows/${workflowId}/executions/stream?token=${encodeURIComponent(token)}`

      setState({ status: {}, running: true, execution: null })

      let ws: WebSocket
      try {
        ws = new WebSocket(url)
      } catch {
        setState((s) => ({ ...s, running: false }))
        return
      }
      wsRef.current = ws

      ws.onmessage = (event) => {
        let msg: any
        try {
          msg = JSON.parse(event.data)
        } catch {
          return
        }

        if (msg.event === 'ready') {
          ws.send(JSON.stringify({ trigger_data: triggerData }))
          return
        }

        if (msg.event === 'node_started') {
          setState((s) => ({
            ...s,
            status: { ...s.status, [msg.node_id]: { status: 'running' } },
          }))
          return
        }

        if (msg.event === 'node_finished') {
          setState((s) => ({
            ...s,
            status: {
              ...s.status,
              [msg.node_id]: { status: msg.status, error: msg.error },
            },
          }))
          return
        }

        if (msg.event === 'node_skipped') {
          setState((s) => ({
            ...s,
            status: { ...s.status, [msg.node_id]: { status: 'skipped' } },
          }))
          return
        }

        if (msg.event === 'execution_complete') {
          setState((s) => ({ ...s, running: false, execution: msg.execution }))
          ws.close()
          return
        }

        if (msg.event === 'error') {
          setState((s) => ({ ...s, running: false }))
          ws.close()
        }
      }

      ws.onerror = () => setState((s) => ({ ...s, running: false }))
      ws.onclose = () => setState((s) => ({ ...s, running: false }))
    },
    [workflowId]
  )

  return { ...state, run, reset }
}
