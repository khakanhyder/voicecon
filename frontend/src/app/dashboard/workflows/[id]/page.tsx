'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

interface Workflow {
  id: string
  name: string
  description: string
  trigger_type: string
  trigger_config: any
  workflow_steps: any[]
  is_active: boolean
  execution_mode: string
  error_handling: string
  max_retries: number
  retry_delay: number
  total_executions: number
  successful_executions: number
  failed_executions: number
  created_at: string
  updated_at: string
}

interface WorkflowExecution {
  id: string
  status: string
  started_at: string
  duration_ms: number | null
  steps_executed: number
  steps_successful: number
  steps_failed: number
  error_message: string | null
  result_data: {
    steps?: Array<{
      step_id: string
      step_name: string
      status: string
      duration_ms: number
      result: any
      error: string | null
    }>
    transcript?: Array<{ role: string; type: string; text?: string }>
    simulated?: boolean
  } | null
}

export default function WorkflowDetailPage() {
  const router = useRouter()
  const params = useParams()
  const workflowId = params.id as string

  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isToggling, setIsToggling] = useState(false)

  // Test-run state
  const [isRunning, setIsRunning] = useState(false)
  const [testAnswers, setTestAnswers] = useState('')
  const [executions, setExecutions] = useState<WorkflowExecution[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    if (workflowId) {
      fetchWorkflow()
      fetchExecutions()
    }
  }, [workflowId])

  const fetchExecutions = async () => {
    try {
      const res = await apiClient.get<{ executions: WorkflowExecution[] }>(
        API_ENDPOINTS.WORKFLOW_EXECUTIONS(workflowId)
      )
      setExecutions(res.data.executions || [])
    } catch (error) {
      // A missing execution history shouldn't break the page.
      console.error('Failed to fetch executions:', error)
    }
  }

  const handleTestRun = async () => {
    if (!workflow) return

    // The Ask steps' answers are scripted here so branches can be exercised.
    let answers: Record<string, string> = {}
    if (testAnswers.trim()) {
      try {
        answers = JSON.parse(testAnswers)
      } catch {
        toast.error('Test answers must be valid JSON, e.g. {"intent": "schedule"}')
        return
      }
    }

    setIsRunning(true)
    try {
      const res = await apiClient.post<WorkflowExecution>(
        API_ENDPOINTS.WORKFLOW_EXECUTE(workflowId),
        { trigger_data: { answers }, wait_for_completion: true }
      )
      const ex = res.data
      if (ex.status === 'completed') {
        toast.success(`Run completed — ${ex.steps_successful}/${ex.steps_executed} steps succeeded`)
      } else {
        toast.error(`Run ${ex.status} — ${ex.steps_failed} step(s) failed`)
      }
      setExpandedId(ex.id)
      await Promise.all([fetchWorkflow(), fetchExecutions()])
    } catch (error) {
      console.error('Test run failed:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsRunning(false)
    }
  }

  const fetchWorkflow = async () => {
    try {
      const response = await apiClient.get<Workflow>(API_ENDPOINTS.WORKFLOW(workflowId))
      setWorkflow(response.data)
    } catch (error) {
      console.error('Failed to fetch workflow:', error)
      toast.error(getErrorMessage(error))
      router.push('/dashboard/workflows')
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggleActive = async () => {
    if (!workflow) return

    setIsToggling(true)
    try {
      const response = await apiClient.patch<Workflow>(
        API_ENDPOINTS.WORKFLOW(workflowId),
        { is_active: !workflow.is_active }
      )
      setWorkflow(response.data)
      toast.success(`Workflow ${response.data.is_active ? 'activated' : 'deactivated'} successfully`)
    } catch (error) {
      console.error('Failed to toggle workflow status:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsToggling(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this workflow? This action cannot be undone.')) {
      return
    }

    setIsDeleting(true)
    try {
      await apiClient.delete(API_ENDPOINTS.WORKFLOW(workflowId))
      toast.success('Workflow deleted successfully')
      router.push('/dashboard/workflows')
    } catch (error) {
      console.error('Failed to delete workflow:', error)
      toast.error(getErrorMessage(error))
      setIsDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="text-lg text-muted-foreground">Loading workflow...</div>
      </div>
    )
  }

  if (!workflow) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="text-lg text-muted-foreground">Workflow not found</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{workflow.name}</h1>
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${
              workflow.is_active
                ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
            }`}>
              {workflow.is_active ? 'Active' : 'Inactive'}
            </div>
          </div>
          <p className="text-muted-foreground">
            {workflow.description || 'No description provided'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleToggleActive}
            disabled={isToggling}
          >
            {isToggling ? 'Updating...' : workflow.is_active ? 'Deactivate' : 'Activate'}
          </Button>
          <Link href={`/dashboard/workflows/${workflowId}/edit`}>
            <Button variant="outline">Edit</Button>
          </Link>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-card p-6">
          <div className="text-sm text-muted-foreground mb-1">Total Executions</div>
          <div className="text-3xl font-bold">{workflow.total_executions}</div>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <div className="text-sm text-muted-foreground mb-1">Successful</div>
          <div className="text-3xl font-bold text-green-600">{workflow.successful_executions}</div>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <div className="text-sm text-muted-foreground mb-1">Failed</div>
          <div className="text-3xl font-bold text-red-600">{workflow.failed_executions}</div>
        </div>
      </div>

      {/* Test run */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-xl font-semibold">Test this workflow</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Runs the flow without a real phone call. Nothing is dialled — you get a
              transcript of what the agent would say.
            </p>
          </div>
          <Button onClick={handleTestRun} disabled={isRunning}>
            {isRunning ? 'Running...' : 'Run test'}
          </Button>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">
            Caller answers <span className="text-muted-foreground font-normal">(optional JSON)</span>
          </label>
          <textarea
            className="w-full rounded-md border bg-background p-3 font-mono text-sm"
            rows={3}
            value={testAnswers}
            onChange={(e) => setTestAnswers(e.target.value)}
            placeholder='{"intent": "schedule", "customer_name": "Sajid"}'
          />
          <p className="text-xs text-muted-foreground">
            Scripts what the caller says. Each key is an Ask step&apos;s variable name — change
            these to drive different branches.
          </p>
        </div>
      </div>

      {/* Execution history */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Execution history</h2>
          <Button variant="outline" size="sm" onClick={fetchExecutions}>Refresh</Button>
        </div>

        {executions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No runs yet. Hit &quot;Run test&quot; above to execute this workflow.
          </p>
        ) : (
          <div className="space-y-2">
            {executions.slice(0, 10).map((ex) => (
              <div key={ex.id} className="rounded-md border">
                <button
                  className="w-full flex items-center justify-between p-3 text-left hover:bg-muted/50"
                  onClick={() => setExpandedId(expandedId === ex.id ? null : ex.id)}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        ex.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : ex.status === 'running'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {ex.status}
                    </span>
                    <span className="text-sm">
                      {ex.steps_successful}/{ex.steps_executed} steps
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(ex.started_at).toLocaleString()}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {ex.duration_ms != null ? `${ex.duration_ms}ms` : ''}
                  </span>
                </button>

                {expandedId === ex.id && (
                  <div className="border-t p-3 space-y-4 text-sm">
                    {ex.error_message && (
                      <p className="text-red-600">{ex.error_message}</p>
                    )}

                    {/* Path taken — proves which branch ran */}
                    {ex.result_data?.steps && ex.result_data.steps.length > 0 && (
                      <div className="space-y-1">
                        <p className="font-medium">Steps executed</p>
                        {ex.result_data.steps.map((s, i) => (
                          <div key={i} className="flex items-start gap-2">
                            <span className={s.status === 'success' ? 'text-green-600' : 'text-red-600'}>
                              {s.status === 'success' ? '✓' : '✗'}
                            </span>
                            <div className="min-w-0">
                              <span className="font-medium">{s.step_name || s.step_id}</span>
                              <span className="text-muted-foreground"> ({s.duration_ms}ms)</span>
                              {s.error && <p className="text-red-600 break-words">{s.error}</p>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Transcript — what the agent would have said */}
                    {ex.result_data?.transcript && ex.result_data.transcript.length > 0 && (
                      <div className="space-y-1">
                        <p className="font-medium">
                          Transcript{' '}
                          {ex.result_data.simulated && (
                            <span className="text-xs font-normal text-muted-foreground">(simulated)</span>
                          )}
                        </p>
                        <div className="rounded-md bg-muted/50 p-3 space-y-1">
                          {ex.result_data.transcript.map((t, i) => (
                            <div key={i} className="flex gap-2">
                              <span className="text-xs font-medium w-14 shrink-0 text-muted-foreground">
                                {t.role}
                              </span>
                              <span className="break-words">{t.text || `— ${t.type} —`}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Configuration */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Trigger Configuration */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Trigger Configuration</h2>

          <div className="space-y-3">
            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">Type</span>
              <span className="font-medium capitalize">{workflow.trigger_type.replace('_', ' ')}</span>
            </div>

            {Object.keys(workflow.trigger_config || {}).length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium">Configuration:</div>
                <pre className="text-xs bg-muted p-3 rounded overflow-auto">
                  {JSON.stringify(workflow.trigger_config, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Execution Settings */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Execution Settings</h2>

          <div className="space-y-3">
            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">Mode</span>
              <span className="font-medium capitalize">{workflow.execution_mode}</span>
            </div>

            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">Error Handling</span>
              <span className="font-medium capitalize">{workflow.error_handling}</span>
            </div>

            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">Max Retries</span>
              <span className="font-medium">{workflow.max_retries}</span>
            </div>

            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">Retry Delay</span>
              <span className="font-medium">{workflow.retry_delay}s</span>
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Steps */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Workflow Steps</h2>
          <Link href={`/dashboard/workflows/${workflowId}/builder`}>
            <Button variant="outline" size="sm">
              {workflow.workflow_steps.length === 0 ? 'Add Steps' : 'Edit Steps'}
            </Button>
          </Link>
        </div>

        {workflow.workflow_steps.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <div className="text-4xl mb-2">🎙️</div>
            <p>No steps configured yet</p>
            <p className="text-sm">Open the builder to add voice call steps</p>
          </div>
        ) : (
          <div className="relative space-y-0">
            {workflow.workflow_steps.map((step: any, index: number) => {
              const typeColors: Record<string, string> = {
                speak: 'bg-blue-500', ask: 'bg-purple-500', condition: 'bg-yellow-500',
                transfer: 'bg-green-500', tool: 'bg-orange-500', webhook: 'bg-cyan-500',
                ai: 'bg-indigo-500', end: 'bg-red-500',
              }
              const typeLabels: Record<string, string> = {
                speak: 'Speak', ask: 'Ask Question', condition: 'Branch', transfer: 'Transfer',
                tool: 'Run Tool', webhook: 'Webhook', ai: 'AI Response', end: 'End Call',
              }
              const color = typeColors[step.type] || 'bg-gray-500'
              const label = typeLabels[step.type] || step.type
              return (
                <div key={index} className="flex items-stretch gap-4">
                  <div className="flex flex-col items-center">
                    <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center text-white text-xs font-bold flex-shrink-0`}>
                      {index + 1}
                    </div>
                    {index < workflow.workflow_steps.length - 1 && (
                      <div className="w-px flex-1 bg-border my-1" />
                    )}
                  </div>
                  <div className="flex-1 pb-3">
                    <div className="p-3 border rounded-lg bg-muted/20">
                      <div className="font-medium text-sm">{step.name || `Step ${index + 1}`}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Quick Actions</h2>

        <div className="flex gap-2">
          <Link href={`/dashboard/workflows/${workflowId}/history`}>
            <Button variant="outline">View Execution History</Button>
          </Link>
          <Button variant="outline" disabled>
            Test Workflow
          </Button>
        </div>
      </div>

      {/* Metadata */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Information</h2>

        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <p className="text-sm text-muted-foreground">Workflow ID</p>
            <p className="font-mono text-sm mt-1">{workflow.id}</p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground">Created</p>
            <p className="text-sm mt-1">{new Date(workflow.created_at).toLocaleString()}</p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground">Last Updated</p>
            <p className="text-sm mt-1">{new Date(workflow.updated_at).toLocaleString()}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
