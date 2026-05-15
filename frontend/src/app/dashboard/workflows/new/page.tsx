'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

export default function NewWorkflowPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    triggerType: 'webhook',
    agentId: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await apiClient.post(API_ENDPOINTS.WORKFLOWS, {
        name: formData.name,
        description: formData.description,
        trigger_type: formData.triggerType,
        trigger_config: formData.agentId ? { agent_id: formData.agentId } : {},
        workflow_steps: [],
        is_active: false,
        execution_mode: 'sequential',
        error_handling: 'stop',
        max_retries: 3,
        retry_delay: 60,
      })

      toast.success('Workflow created successfully!')
      router.push('/dashboard/workflows')
    } catch (error) {
      console.error('Failed to create workflow:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Create New Workflow</h1>
        <p className="text-muted-foreground">
          Build an automation workflow
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Basic Information */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Basic Information</h2>

          <div className="space-y-2">
            <Label htmlFor="name">Workflow Name *</Label>
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
              placeholder="Qualifies inbound leads and routes them to the appropriate team"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
            />
          </div>
        </div>

        {/* Trigger Configuration */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Trigger</h2>

          <div className="space-y-2">
            <Label htmlFor="triggerType">Trigger Type *</Label>
            <Select
              value={formData.triggerType}
              onValueChange={(value) => setFormData({ ...formData, triggerType: value })}
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
              What should trigger this workflow?
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
                  <SelectValue placeholder="Select an agent" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="agent1">Customer Support Agent</SelectItem>
                  <SelectItem value="agent2">Sales Agent</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {/* Visual Builder Notice */}
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-6">
          <h3 className="font-semibold mb-2">Visual Workflow Builder</h3>
          <p className="text-sm text-muted-foreground mb-4">
            After creating the workflow, you'll be able to add actions, conditions, and integrations using our visual builder.
          </p>
          <div className="flex gap-2 text-sm">
            <span className="rounded bg-background px-2 py-1 font-mono">Triggers</span>
            <span className="text-muted-foreground">→</span>
            <span className="rounded bg-background px-2 py-1 font-mono">Conditions</span>
            <span className="text-muted-foreground">→</span>
            <span className="rounded bg-background px-2 py-1 font-mono">Actions</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-4">
          <Button type="submit" size="lg" disabled={isLoading}>
            {isLoading ? 'Creating...' : 'Create Workflow'}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => router.push('/dashboard/workflows')}
            disabled={isLoading}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  )
}
