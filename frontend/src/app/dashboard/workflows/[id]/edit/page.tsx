'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { useAgentOptions } from '@/hooks/useAgentOptions'
import { toast } from 'sonner'

interface Workflow {
  id: string
  name: string
  description: string
  trigger_type: string
  trigger_config: any
  is_active: boolean
  execution_mode: string
  error_handling: string
  max_retries: number
  retry_delay: number
}

export default function EditWorkflowPage() {
  const router = useRouter()
  const params = useParams()
  const workflowId = params.id as string

  const [isLoading, setIsLoading] = useState(false)
  const [isFetching, setIsFetching] = useState(true)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    triggerType: 'webhook',
    agentId: '',
    executionMode: 'sequential',
    errorHandling: 'stop',
    maxRetries: 3,
    retryDelay: 60,
  })
  const { agents, isLoading: agentsLoading } = useAgentOptions(
    formData.triggerType === 'call_completed'
  )

  useEffect(() => {
    if (workflowId) {
      fetchWorkflow()
    }
  }, [workflowId])

  const fetchWorkflow = async () => {
    try {
      const response = await apiClient.get<Workflow>(API_ENDPOINTS.WORKFLOW(workflowId))
      const workflow = response.data

      setFormData({
        name: workflow.name,
        description: workflow.description || '',
        triggerType: workflow.trigger_type,
        agentId: workflow.trigger_config?.agent_id || '',
        executionMode: workflow.execution_mode,
        errorHandling: workflow.error_handling,
        maxRetries: workflow.max_retries,
        retryDelay: workflow.retry_delay,
      })
    } catch (error) {
      console.error('Failed to fetch workflow:', error)
      toast.error(getErrorMessage(error))
      router.push('/dashboard/workflows')
    } finally {
      setIsFetching(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await apiClient.patch(API_ENDPOINTS.WORKFLOW(workflowId), {
        name: formData.name,
        description: formData.description,
        trigger_config: formData.agentId ? { agent_id: formData.agentId } : {},
        error_handling: formData.errorHandling,
        max_retries: formData.maxRetries,
        retry_delay: formData.retryDelay,
      })

      toast.success('Workflow updated successfully!')
      router.push(`/dashboard/workflows/${workflowId}`)
    } catch (error) {
      console.error('Failed to update workflow:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  if (isFetching) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="text-lg text-muted-foreground">Loading workflow...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Edit Workflow</h1>
        <p className="text-muted-foreground">
          Update your automation workflow configuration
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Information */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Basic Information</h2>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Workflow Name</Label>
              <Input
                id="name"
                placeholder="Lead Qualification Workflow"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Describe what this workflow does..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
              />
            </div>
          </div>
        </div>

        {/* Trigger Configuration */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Trigger Configuration</h2>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="triggerType">Trigger Type</Label>
              <Select
                value={formData.triggerType}
                onValueChange={(value) => setFormData({ ...formData, triggerType: value })}
                disabled
              >
                <SelectTrigger id="triggerType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="webhook">Webhook</SelectItem>
                  <SelectItem value="schedule">Schedule</SelectItem>
                  <SelectItem value="call_completed">Call Completed</SelectItem>
                  <SelectItem value="integration_event">Integration Event</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Trigger type cannot be changed after creation
              </p>
            </div>

            {formData.triggerType === 'call_completed' && (
              <div className="space-y-2">
                <Label htmlFor="agentId">Agent</Label>
                <Select
                  value={formData.agentId}
                  onValueChange={(value) => setFormData({ ...formData, agentId: value })}
                >
                  <SelectTrigger id="agentId">
                    <SelectValue
                      placeholder={
                        agentsLoading ? 'Loading agents…' : 'Select an agent'
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {agents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!agentsLoading && agents.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No agents yet — create one first to trigger on its calls.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Execution Settings */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Execution Settings</h2>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="executionMode">Execution Mode</Label>
              <Select
                value={formData.executionMode}
                onValueChange={(value) => setFormData({ ...formData, executionMode: value })}
                disabled
              >
                <SelectTrigger id="executionMode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sequential">Sequential</SelectItem>
                  <SelectItem value="parallel">Parallel</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Cannot be changed after creation
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="errorHandling">Error Handling</Label>
              <Select
                value={formData.errorHandling}
                onValueChange={(value) => setFormData({ ...formData, errorHandling: value })}
              >
                <SelectTrigger id="errorHandling">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="stop">Stop on Error</SelectItem>
                  <SelectItem value="continue">Continue on Error</SelectItem>
                  <SelectItem value="retry">Retry on Error</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxRetries">Max Retries</Label>
              <Input
                id="maxRetries"
                type="number"
                min="0"
                max="10"
                value={formData.maxRetries}
                onChange={(e) => setFormData({ ...formData, maxRetries: parseInt(e.target.value) })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="retryDelay">Retry Delay (seconds)</Label>
              <Input
                id="retryDelay"
                type="number"
                min="0"
                value={formData.retryDelay}
                onChange={(e) => setFormData({ ...formData, retryDelay: parseInt(e.target.value) })}
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-4">
          <Button type="submit" size="lg" disabled={isLoading}>
            {isLoading ? 'Updating...' : 'Update Workflow'}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => router.push(`/dashboard/workflows/${workflowId}`)}
            disabled={isLoading}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  )
}
