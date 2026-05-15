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
import { toast } from 'sonner'
import { Plus, Trash2, GripVertical, Save, ArrowLeft } from 'lucide-react'
import Link from 'next/link'

interface WorkflowStep {
  id: string
  name: string
  type: string
  config: Record<string, any>
  order: number
}

interface Workflow {
  id: string
  name: string
  description: string
  trigger_type: string
  workflow_steps: WorkflowStep[]
}

const STEP_TYPES = [
  { value: 'action', label: 'Action', description: 'Perform an action (API call, send email, etc.)' },
  { value: 'condition', label: 'Condition', description: 'Branch based on a condition' },
  { value: 'loop', label: 'Loop', description: 'Repeat steps for a list of items' },
  { value: 'transform', label: 'Transform', description: 'Transform data between steps' },
  { value: 'delay', label: 'Delay', description: 'Wait for a specified duration' },
]

const ACTION_SUBTYPES = [
  { value: 'http_request', label: 'HTTP Request' },
  { value: 'send_email', label: 'Send Email' },
  { value: 'send_sms', label: 'Send SMS' },
  { value: 'update_crm', label: 'Update CRM' },
  { value: 'create_task', label: 'Create Task' },
]

export default function WorkflowBuilderPage() {
  const router = useRouter()
  const params = useParams()
  const workflowId = params.id as string

  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [steps, setSteps] = useState<WorkflowStep[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(null)

  useEffect(() => {
    if (workflowId) {
      fetchWorkflow()
    }
  }, [workflowId])

  const fetchWorkflow = async () => {
    try {
      const response = await apiClient.get<Workflow>(`${API_ENDPOINTS.WORKFLOWS}${workflowId}`)
      setWorkflow(response.data)
      setSteps(response.data.workflow_steps || [])
    } catch (error) {
      console.error('Failed to fetch workflow:', error)
      toast.error(getErrorMessage(error))
      router.push('/dashboard/workflows')
    } finally {
      setIsLoading(false)
    }
  }

  const addStep = () => {
    const newStep: WorkflowStep = {
      id: `step_${Date.now()}`,
      name: `Step ${steps.length + 1}`,
      type: 'action',
      config: {
        action_type: 'http_request',
      },
      order: steps.length,
    }
    setSteps([...steps, newStep])
    setSelectedStepIndex(steps.length)
  }

  const updateStep = (index: number, updates: Partial<WorkflowStep>) => {
    const updatedSteps = [...steps]
    updatedSteps[index] = { ...updatedSteps[index], ...updates }
    setSteps(updatedSteps)
  }

  const deleteStep = (index: number) => {
    const updatedSteps = steps.filter((_, i) => i !== index)
    // Update order for remaining steps
    updatedSteps.forEach((step, i) => {
      step.order = i
    })
    setSteps(updatedSteps)
    if (selectedStepIndex === index) {
      setSelectedStepIndex(null)
    } else if (selectedStepIndex !== null && selectedStepIndex > index) {
      setSelectedStepIndex(selectedStepIndex - 1)
    }
  }

  const moveStep = (index: number, direction: 'up' | 'down') => {
    if (
      (direction === 'up' && index === 0) ||
      (direction === 'down' && index === steps.length - 1)
    ) {
      return
    }

    const newIndex = direction === 'up' ? index - 1 : index + 1
    const updatedSteps = [...steps]
    const [movedStep] = updatedSteps.splice(index, 1)
    updatedSteps.splice(newIndex, 0, movedStep)

    // Update order
    updatedSteps.forEach((step, i) => {
      step.order = i
    })

    setSteps(updatedSteps)
    setSelectedStepIndex(newIndex)
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await apiClient.patch(`${API_ENDPOINTS.WORKFLOWS}${workflowId}`, {
        workflow_steps: steps,
      })
      toast.success('Workflow steps saved successfully!')
    } catch (error) {
      console.error('Failed to save workflow steps:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsSaving(false)
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

  const selectedStep = selectedStepIndex !== null ? steps[selectedStepIndex] : null

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-card border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/dashboard/workflows/${workflowId}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </Link>
            <div>
              <h1 className="text-2xl font-bold">{workflow.name}</h1>
              <p className="text-sm text-muted-foreground">Workflow Builder</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={handleSave} disabled={isSaving}>
              <Save className="w-4 h-4 mr-2" />
              {isSaving ? 'Saving...' : 'Save Workflow'}
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Steps List */}
        <div className="w-96 border-r bg-card overflow-y-auto">
          <div className="p-4 border-b">
            <Button onClick={addStep} className="w-full">
              <Plus className="w-4 h-4 mr-2" />
              Add Step
            </Button>
          </div>

          <div className="p-4 space-y-2">
            {steps.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <div className="text-4xl mb-2">⚡</div>
                <p>No steps yet</p>
                <p className="text-sm">Click "Add Step" to get started</p>
              </div>
            ) : (
              steps.map((step, index) => (
                <div
                  key={step.id}
                  className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                    selectedStepIndex === index
                      ? 'border-primary bg-primary/5'
                      : 'hover:border-primary/50'
                  }`}
                  onClick={() => setSelectedStepIndex(index)}
                >
                  <div className="flex items-start gap-2">
                    <div className="flex flex-col gap-1 mt-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          moveStep(index, 'up')
                        }}
                        disabled={index === 0}
                        className="text-muted-foreground hover:text-foreground disabled:opacity-30"
                      >
                        <GripVertical className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium">
                          {index + 1}
                        </div>
                        <div className="font-medium">{step.name}</div>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1 capitalize">
                        {step.type}
                        {step.config.action_type && ` - ${step.config.action_type.replace('_', ' ')}`}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteStep(index)
                      }}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Step Configuration */}
        <div className="flex-1 overflow-y-auto bg-muted/30">
          {selectedStep ? (
            <div className="p-6 max-w-3xl mx-auto space-y-6">
              <div className="bg-card rounded-lg border p-6 space-y-4">
                <h2 className="text-xl font-semibold">Step Configuration</h2>

                {/* Step Name */}
                <div className="space-y-2">
                  <Label>Step Name</Label>
                  <Input
                    value={selectedStep.name}
                    onChange={(e) =>
                      updateStep(selectedStepIndex!, { name: e.target.value })
                    }
                    placeholder="e.g., Send Welcome Email"
                  />
                </div>

                {/* Step Type */}
                <div className="space-y-2">
                  <Label>Step Type</Label>
                  <Select
                    value={selectedStep.type}
                    onValueChange={(value) =>
                      updateStep(selectedStepIndex!, { type: value, config: {} })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STEP_TYPES.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          <div>
                            <div className="font-medium">{type.label}</div>
                            <div className="text-xs text-muted-foreground">{type.description}</div>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Type-Specific Configuration */}
                {selectedStep.type === 'action' && (
                  <>
                    <div className="space-y-2">
                      <Label>Action Type</Label>
                      <Select
                        value={selectedStep.config.action_type || 'http_request'}
                        onValueChange={(value) =>
                          updateStep(selectedStepIndex!, {
                            config: { ...selectedStep.config, action_type: value },
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ACTION_SUBTYPES.map((subtype) => (
                            <SelectItem key={subtype.value} value={subtype.value}>
                              {subtype.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {selectedStep.config.action_type === 'http_request' && (
                      <>
                        <div className="space-y-2">
                          <Label>URL</Label>
                          <Input
                            value={selectedStep.config.url || ''}
                            onChange={(e) =>
                              updateStep(selectedStepIndex!, {
                                config: { ...selectedStep.config, url: e.target.value },
                              })
                            }
                            placeholder="https://api.example.com/endpoint"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Method</Label>
                          <Select
                            value={selectedStep.config.method || 'GET'}
                            onValueChange={(value) =>
                              updateStep(selectedStepIndex!, {
                                config: { ...selectedStep.config, method: value },
                              })
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="GET">GET</SelectItem>
                              <SelectItem value="POST">POST</SelectItem>
                              <SelectItem value="PUT">PUT</SelectItem>
                              <SelectItem value="PATCH">PATCH</SelectItem>
                              <SelectItem value="DELETE">DELETE</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>Headers (JSON)</Label>
                          <Textarea
                            value={selectedStep.config.headers || '{}'}
                            onChange={(e) =>
                              updateStep(selectedStepIndex!, {
                                config: { ...selectedStep.config, headers: e.target.value },
                              })
                            }
                            placeholder='{"Content-Type": "application/json"}'
                            rows={3}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Body (JSON)</Label>
                          <Textarea
                            value={selectedStep.config.body || '{}'}
                            onChange={(e) =>
                              updateStep(selectedStepIndex!, {
                                config: { ...selectedStep.config, body: e.target.value },
                              })
                            }
                            placeholder='{"key": "value"}'
                            rows={5}
                          />
                        </div>
                      </>
                    )}

                    {selectedStep.config.action_type === 'send_email' && (
                      <>
                        <div className="space-y-2">
                          <Label>To Email</Label>
                          <Input
                            value={selectedStep.config.to_email || ''}
                            onChange={(e) =>
                              updateStep(selectedStepIndex!, {
                                config: { ...selectedStep.config, to_email: e.target.value },
                              })
                            }
                            placeholder="user@example.com"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Subject</Label>
                          <Input
                            value={selectedStep.config.subject || ''}
                            onChange={(e) =>
                              updateStep(selectedStepIndex!, {
                                config: { ...selectedStep.config, subject: e.target.value },
                              })
                            }
                            placeholder="Email subject"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Body</Label>
                          <Textarea
                            value={selectedStep.config.email_body || ''}
                            onChange={(e) =>
                              updateStep(selectedStepIndex!, {
                                config: { ...selectedStep.config, email_body: e.target.value },
                              })
                            }
                            placeholder="Email content..."
                            rows={5}
                          />
                        </div>
                      </>
                    )}
                  </>
                )}

                {selectedStep.type === 'condition' && (
                  <>
                    <div className="space-y-2">
                      <Label>Condition Expression</Label>
                      <Input
                        value={selectedStep.config.expression || ''}
                        onChange={(e) =>
                          updateStep(selectedStepIndex!, {
                            config: { ...selectedStep.config, expression: e.target.value },
                          })
                        }
                        placeholder="e.g., data.status == 'active'"
                      />
                      <p className="text-xs text-muted-foreground">
                        Use JavaScript-like expressions to evaluate conditions
                      </p>
                    </div>
                  </>
                )}

                {selectedStep.type === 'delay' && (
                  <>
                    <div className="space-y-2">
                      <Label>Delay Duration (seconds)</Label>
                      <Input
                        type="number"
                        value={selectedStep.config.duration || 0}
                        onChange={(e) =>
                          updateStep(selectedStepIndex!, {
                            config: { ...selectedStep.config, duration: parseInt(e.target.value) },
                          })
                        }
                        placeholder="60"
                      />
                    </div>
                  </>
                )}

                {selectedStep.type === 'transform' && (
                  <>
                    <div className="space-y-2">
                      <Label>Transform Script</Label>
                      <Textarea
                        value={selectedStep.config.script || ''}
                        onChange={(e) =>
                          updateStep(selectedStepIndex!, {
                            config: { ...selectedStep.config, script: e.target.value },
                          })
                        }
                        placeholder="// Transform data here&#10;return { transformedData: data }"
                        rows={8}
                      />
                      <p className="text-xs text-muted-foreground">
                        JavaScript code to transform data between steps
                      </p>
                    </div>
                  </>
                )}

                {selectedStep.type === 'loop' && (
                  <>
                    <div className="space-y-2">
                      <Label>Items Path</Label>
                      <Input
                        value={selectedStep.config.items_path || ''}
                        onChange={(e) =>
                          updateStep(selectedStepIndex!, {
                            config: { ...selectedStep.config, items_path: e.target.value },
                          })
                        }
                        placeholder="e.g., data.items"
                      />
                      <p className="text-xs text-muted-foreground">
                        Path to the array to loop over
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <div className="text-center">
                <div className="text-4xl mb-2">👈</div>
                <p>Select a step to configure it</p>
                <p className="text-sm">or add a new step to get started</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
