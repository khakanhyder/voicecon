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

export default function WorkflowDetailPage() {
  const router = useRouter()
  const params = useParams()
  const workflowId = params.id as string

  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isToggling, setIsToggling] = useState(false)

  useEffect(() => {
    if (workflowId) {
      fetchWorkflow()
    }
  }, [workflowId])

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
