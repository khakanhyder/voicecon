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
import {
  Plus, Trash2, Save, ArrowLeft, Volume2, MessageSquare, GitBranch,
  PhoneForwarded, Wrench, Globe, PhoneOff, Bot, ChevronDown, ChevronUp,
  Play, Zap,
} from 'lucide-react'
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
  {
    value: 'speak',
    label: 'Speak',
    icon: Volume2,
    color: 'bg-blue-500',
    lightColor: 'bg-blue-50 border-blue-200 text-blue-700',
    description: 'Agent speaks a message to the caller',
  },
  {
    value: 'ask',
    label: 'Ask Question',
    icon: MessageSquare,
    color: 'bg-purple-500',
    lightColor: 'bg-purple-50 border-purple-200 text-purple-700',
    description: 'Ask and capture caller response in a variable',
  },
  {
    value: 'condition',
    label: 'Branch / Condition',
    icon: GitBranch,
    color: 'bg-yellow-500',
    lightColor: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    description: 'Branch call flow based on a variable or condition',
  },
  {
    value: 'transfer',
    label: 'Transfer Call',
    icon: PhoneForwarded,
    color: 'bg-green-500',
    lightColor: 'bg-green-50 border-green-200 text-green-700',
    description: 'Transfer the call to another number or agent',
  },
  {
    value: 'tool',
    label: 'Run Tool',
    icon: Wrench,
    color: 'bg-orange-500',
    lightColor: 'bg-orange-50 border-orange-200 text-orange-700',
    description: 'Execute a configured tool or function',
  },
  {
    value: 'webhook',
    label: 'Webhook',
    icon: Globe,
    color: 'bg-cyan-500',
    lightColor: 'bg-cyan-50 border-cyan-200 text-cyan-700',
    description: 'Call an external API endpoint',
  },
  {
    value: 'ai',
    label: 'AI Response',
    icon: Bot,
    color: 'bg-indigo-500',
    lightColor: 'bg-indigo-50 border-indigo-200 text-indigo-700',
    description: 'Let AI generate a contextual response',
  },
  {
    value: 'end',
    label: 'End Call',
    icon: PhoneOff,
    color: 'bg-red-500',
    lightColor: 'bg-red-50 border-red-200 text-red-700',
    description: 'End the conversation and hang up',
  },
]

function getStepMeta(type: string) {
  return STEP_TYPES.find((s) => s.value === type) ?? STEP_TYPES[0]
}

function getDefaultConfig(type: string): Record<string, any> {
  switch (type) {
    case 'speak':
      return { message: '', voice: 'default' }
    case 'ask':
      return { question: '', variable: '', input_type: 'speech', timeout: 10 }
    case 'condition':
      return { variable: '', operator: 'equals', value: '', on_true: '', on_false: '' }
    case 'transfer':
      return { destination: '', transfer_type: 'blind', message: '' }
    case 'tool':
      return { tool_id: '', parameters: '{}' }
    case 'webhook':
      return { url: '', method: 'POST', headers: '{}', body: '{}' }
    case 'ai':
      return { context: '', constraints: '', max_turns: 3 }
    case 'end':
      return { farewell: 'Thank you for calling. Goodbye!' }
    default:
      return {}
  }
}

// ── Step config panels ────────────────────────────────────────────────────────

function SpeakConfig({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Message</Label>
        <Textarea
          value={config.message || ''}
          onChange={(e) => onChange({ ...config, message: e.target.value })}
          placeholder="What should the agent say? Use {{variable}} to insert captured values."
          rows={4}
        />
        <p className="text-xs text-muted-foreground">Use {'{{variable_name}}'} to insert dynamic values</p>
      </div>
      <div className="space-y-1.5">
        <Label>Voice</Label>
        <Select value={config.voice || 'default'} onValueChange={(v) => onChange({ ...config, voice: v })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="default">Default</SelectItem>
            <SelectItem value="alloy">Alloy (OpenAI)</SelectItem>
            <SelectItem value="echo">Echo (OpenAI)</SelectItem>
            <SelectItem value="nova">Nova (OpenAI)</SelectItem>
            <SelectItem value="shimmer">Shimmer (OpenAI)</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

function AskConfig({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Question</Label>
        <Textarea
          value={config.question || ''}
          onChange={(e) => onChange({ ...config, question: e.target.value })}
          placeholder="What would you like to ask the caller?"
          rows={3}
        />
      </div>
      <div className="space-y-1.5">
        <Label>Save answer to variable</Label>
        <Input
          value={config.variable || ''}
          onChange={(e) => onChange({ ...config, variable: e.target.value })}
          placeholder="e.g. customer_name"
        />
        <p className="text-xs text-muted-foreground">Reference later as {'{{customer_name}}'}</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label>Input type</Label>
          <Select value={config.input_type || 'speech'} onValueChange={(v) => onChange({ ...config, input_type: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="speech">Speech (voice)</SelectItem>
              <SelectItem value="dtmf">DTMF (keypad)</SelectItem>
              <SelectItem value="both">Both</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Timeout (seconds)</Label>
          <Input
            type="number"
            min={3}
            max={60}
            value={config.timeout || 10}
            onChange={(e) => onChange({ ...config, timeout: parseInt(e.target.value) || 10 })}
          />
        </div>
      </div>
    </div>
  )
}

function ConditionConfig({
  config,
  onChange,
  steps = [],
  currentId,
}: {
  config: any
  onChange: (c: any) => void
  steps?: WorkflowStep[]
  currentId?: string
}) {
  // Any step other than this one is a valid jump target.
  const targets = steps.filter((s) => s.id !== currentId)

  return (
    <div className="space-y-4">
      <div className="bg-muted/50 rounded-lg p-4 space-y-3">
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Condition</p>
        <div className="grid grid-cols-3 gap-2">
          <div className="space-y-1.5">
            <Label>Variable</Label>
            <Input
              value={config.variable || ''}
              onChange={(e) => onChange({ ...config, variable: e.target.value })}
              placeholder="e.g. intent"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Operator</Label>
            <Select value={config.operator || 'equals'} onValueChange={(v) => onChange({ ...config, operator: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="equals">equals</SelectItem>
                <SelectItem value="not_equals">not equals</SelectItem>
                <SelectItem value="contains">contains</SelectItem>
                <SelectItem value="starts_with">starts with</SelectItem>
                <SelectItem value="is_empty">is empty</SelectItem>
                <SelectItem value="is_not_empty">is not empty</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Value</Label>
            <Input
              value={config.value || ''}
              onChange={(e) => onChange({ ...config, value: e.target.value })}
              placeholder="e.g. schedule"
            />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label className="text-green-700">If true, go to</Label>
          <Select
            value={config.on_true || '__next__'}
            onValueChange={(v) => onChange({ ...config, on_true: v === '__next__' ? '' : v })}
          >
            <SelectTrigger><SelectValue placeholder="Next step" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__next__">Continue to next step</SelectItem>
              {targets.map((s) => (
                <SelectItem key={s.id} value={s.id}>{s.name || s.id}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-red-700">If false, go to</Label>
          <Select
            value={config.on_false || '__next__'}
            onValueChange={(v) => onChange({ ...config, on_false: v === '__next__' ? '' : v })}
          >
            <SelectTrigger><SelectValue placeholder="Next step" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__next__">Continue to next step</SelectItem>
              {targets.map((s) => (
                <SelectItem key={s.id} value={s.id}>{s.name || s.id}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Pick where each outcome jumps to. Leave as &quot;next step&quot; for a straight-through flow.
      </p>
    </div>
  )
}

function TransferConfig({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Destination number</Label>
        <Input
          value={config.destination || ''}
          onChange={(e) => onChange({ ...config, destination: e.target.value })}
          placeholder="+15551234567"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Transfer type</Label>
        <Select value={config.transfer_type || 'blind'} onValueChange={(v) => onChange({ ...config, transfer_type: v })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="blind">Blind (immediate)</SelectItem>
            <SelectItem value="warm">Warm (announce first)</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Transfer message (optional)</Label>
        <Input
          value={config.message || ''}
          onChange={(e) => onChange({ ...config, message: e.target.value })}
          placeholder="Please hold while I connect you..."
        />
      </div>
    </div>
  )
}

function ToolConfig({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Tool ID</Label>
        <Input
          value={config.tool_id || ''}
          onChange={(e) => onChange({ ...config, tool_id: e.target.value })}
          placeholder="tool_xxxxxxxx"
        />
        <p className="text-xs text-muted-foreground">Find tool IDs in the Tools section</p>
      </div>
      <div className="space-y-1.5">
        <Label>Parameters (JSON)</Label>
        <Textarea
          value={config.parameters || '{}'}
          onChange={(e) => onChange({ ...config, parameters: e.target.value })}
          placeholder={'{\n  "param": "{{variable}}"\n}'}
          rows={4}
          className="font-mono text-sm"
        />
      </div>
    </div>
  )
}

function WebhookConfig({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        <div className="col-span-2 space-y-1.5">
          <Label>URL</Label>
          <Input
            value={config.url || ''}
            onChange={(e) => onChange({ ...config, url: e.target.value })}
            placeholder="https://api.example.com/endpoint"
          />
        </div>
        <div className="space-y-1.5">
          <Label>Method</Label>
          <Select value={config.method || 'POST'} onValueChange={(v) => onChange({ ...config, method: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="GET">GET</SelectItem>
              <SelectItem value="POST">POST</SelectItem>
              <SelectItem value="PUT">PUT</SelectItem>
              <SelectItem value="PATCH">PATCH</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Headers (JSON)</Label>
        <Textarea
          value={config.headers || '{}'}
          onChange={(e) => onChange({ ...config, headers: e.target.value })}
          placeholder={'{"Authorization": "Bearer {{token}}"}'}
          rows={3}
          className="font-mono text-sm"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Body (JSON)</Label>
        <Textarea
          value={config.body || '{}'}
          onChange={(e) => onChange({ ...config, body: e.target.value })}
          placeholder={'{\n  "caller": "{{caller_number}}",\n  "data": "{{answer}}"\n}'}
          rows={4}
          className="font-mono text-sm"
        />
      </div>
    </div>
  )
}

function AiConfig({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Context / instructions</Label>
        <Textarea
          value={config.context || ''}
          onChange={(e) => onChange({ ...config, context: e.target.value })}
          placeholder="Provide context for the AI response. E.g. 'Answer questions about our pricing. Be concise.'"
          rows={4}
        />
      </div>
      <div className="space-y-1.5">
        <Label>Constraints (optional)</Label>
        <Textarea
          value={config.constraints || ''}
          onChange={(e) => onChange({ ...config, constraints: e.target.value })}
          placeholder="Do not discuss competitors. Keep responses under 50 words."
          rows={2}
        />
      </div>
      <div className="space-y-1.5">
        <Label>Max turns</Label>
        <Input
          type="number"
          min={1}
          max={20}
          value={config.max_turns || 3}
          onChange={(e) => onChange({ ...config, max_turns: parseInt(e.target.value) || 3 })}
        />
        <p className="text-xs text-muted-foreground">Maximum back-and-forth exchanges before moving to the next step</p>
      </div>
    </div>
  )
}

function EndConfig({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Farewell message</Label>
        <Textarea
          value={config.farewell || ''}
          onChange={(e) => onChange({ ...config, farewell: e.target.value })}
          placeholder="Thank you for calling. Have a great day!"
          rows={3}
        />
      </div>
    </div>
  )
}

function StepConfigPanel({
  step,
  onUpdateConfig,
  allSteps = [],
}: {
  step: WorkflowStep
  onUpdateConfig: (config: any) => void
  allSteps?: WorkflowStep[]
}) {
  switch (step.type) {
    case 'speak':     return <SpeakConfig config={step.config} onChange={onUpdateConfig} />
    case 'ask':       return <AskConfig config={step.config} onChange={onUpdateConfig} />
    case 'condition': return <ConditionConfig config={step.config} onChange={onUpdateConfig} steps={allSteps} currentId={step.id} />
    case 'transfer':  return <TransferConfig config={step.config} onChange={onUpdateConfig} />
    case 'tool':      return <ToolConfig config={step.config} onChange={onUpdateConfig} />
    case 'webhook':   return <WebhookConfig config={step.config} onChange={onUpdateConfig} />
    case 'ai':        return <AiConfig config={step.config} onChange={onUpdateConfig} />
    case 'end':       return <EndConfig config={step.config} onChange={onUpdateConfig} />
    default:          return <p className="text-muted-foreground text-sm">No configuration for this step type.</p>
  }
}

// ── Step node card in the flow ────────────────────────────────────────────────

function FlowStepCard({
  step,
  index,
  total,
  selected,
  onClick,
  onDelete,
  onMove,
}: {
  step: WorkflowStep
  index: number
  total: number
  selected: boolean
  onClick: () => void
  onDelete: () => void
  onMove: (dir: 'up' | 'down') => void
}) {
  const meta = getStepMeta(step.type)
  const Icon = meta.icon

  return (
    <div className="flex flex-col items-center">
      {/* connector line from above */}
      {index > 0 && (
        <div className="w-px h-6 bg-border" />
      )}

      <div
        onClick={onClick}
        className={`w-full max-w-sm rounded-xl border-2 transition-all cursor-pointer shadow-sm hover:shadow-md ${
          selected
            ? 'border-primary shadow-primary/10 shadow-lg'
            : 'border-border hover:border-primary/40'
        } bg-card`}
      >
        <div className="p-4">
          <div className="flex items-center gap-3">
            {/* step number + icon */}
            <div className={`w-10 h-10 rounded-lg ${meta.color} flex items-center justify-center flex-shrink-0`}>
              <Icon className="w-5 h-5 text-white" />
            </div>

            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-foreground truncate">{step.name}</div>
              <div className={`text-xs px-2 py-0.5 rounded-full border inline-block mt-0.5 ${meta.lightColor}`}>
                {meta.label}
              </div>
            </div>

            {/* move + delete */}
            <div className="flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
              <button
                disabled={index === 0}
                onClick={() => onMove('up')}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronUp className="w-3.5 h-3.5" />
              </button>
              <button
                disabled={index === total - 1}
                onClick={() => onMove('down')}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>

            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="p-1.5 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>

          {/* preview of key config */}
          {step.type === 'speak' && step.config.message && (
            <p className="mt-2 text-xs text-muted-foreground italic line-clamp-2 pl-13">
              "{step.config.message}"
            </p>
          )}
          {step.type === 'ask' && step.config.question && (
            <p className="mt-2 text-xs text-muted-foreground italic line-clamp-1 pl-13">
              "{step.config.question}"
            </p>
          )}
          {step.type === 'condition' && step.config.variable && (
            <p className="mt-2 text-xs text-muted-foreground pl-13">
              if {'{{' + step.config.variable + '}}'} {step.config.operator} "{step.config.value}"
            </p>
          )}
          {step.type === 'transfer' && step.config.destination && (
            <p className="mt-2 text-xs text-muted-foreground pl-13">
              → {step.config.destination}
            </p>
          )}
          {step.type === 'webhook' && step.config.url && (
            <p className="mt-2 text-xs text-muted-foreground truncate pl-13">
              {step.config.method} {step.config.url}
            </p>
          )}
        </div>
      </div>

      {/* connector line to below */}
      {index < total - 1 && (
        <div className="w-px h-6 bg-border" />
      )}
    </div>
  )
}

// ── Add step picker ───────────────────────────────────────────────────────────

function AddStepPicker({ onAdd }: { onAdd: (type: string) => void }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex flex-col items-center">
      <div className="w-px h-4 bg-border" />
      <div className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border-2 border-dashed border-primary/40 text-primary hover:border-primary hover:bg-primary/5 transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          Add step
        </button>

        {open && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
            <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 z-20 bg-card border rounded-xl shadow-xl p-2 w-64">
              {STEP_TYPES.map((t) => {
                const Icon = t.icon
                return (
                  <button
                    key={t.value}
                    onClick={() => { onAdd(t.value); setOpen(false) }}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-muted transition-colors text-left"
                  >
                    <div className={`w-8 h-8 rounded-lg ${t.color} flex items-center justify-center flex-shrink-0`}>
                      <Icon className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <div className="text-sm font-medium">{t.label}</div>
                      <div className="text-xs text-muted-foreground">{t.description}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

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
    if (workflowId) fetchWorkflow()
  }, [workflowId])

  const fetchWorkflow = async () => {
    try {
      const res = await apiClient.get<Workflow>(API_ENDPOINTS.WORKFLOW(workflowId))
      setWorkflow(res.data)
      setSteps(res.data.workflow_steps || [])
    } catch (err) {
      toast.error(getErrorMessage(err))
      router.push('/dashboard/workflows')
    } finally {
      setIsLoading(false)
    }
  }

  const addStep = (type: string) => {
    const meta = getStepMeta(type)
    const newStep: WorkflowStep = {
      id: `step_${Date.now()}`,
      name: meta.label,
      type,
      config: getDefaultConfig(type),
      order: steps.length,
    }
    const updated = [...steps, newStep]
    setSteps(updated)
    setSelectedStepIndex(updated.length - 1)
  }

  const updateStep = (index: number, updates: Partial<WorkflowStep>) => {
    const updated = [...steps]
    updated[index] = { ...updated[index], ...updates }
    setSteps(updated)
  }

  const deleteStep = (index: number) => {
    const updated = steps.filter((_, i) => i !== index).map((s, i) => ({ ...s, order: i }))
    setSteps(updated)
    setSelectedStepIndex(
      selectedStepIndex === index
        ? null
        : selectedStepIndex !== null && selectedStepIndex > index
        ? selectedStepIndex - 1
        : selectedStepIndex
    )
  }

  const moveStep = (index: number, dir: 'up' | 'down') => {
    if ((dir === 'up' && index === 0) || (dir === 'down' && index === steps.length - 1)) return
    const newIndex = dir === 'up' ? index - 1 : index + 1
    const updated = [...steps]
    const [moved] = updated.splice(index, 1)
    updated.splice(newIndex, 0, moved)
    updated.forEach((s, i) => { s.order = i })
    setSteps(updated)
    setSelectedStepIndex(newIndex)
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await apiClient.patch(API_ENDPOINTS.WORKFLOW(workflowId), { workflow_steps: steps })
      toast.success('Workflow saved!')
    } catch (err) {
      toast.error(getErrorMessage(err))
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
    <div className="h-screen flex flex-col bg-background">
      {/* ── Header ── */}
      <div className="bg-card border-b px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-4">
          <Link href={`/dashboard/workflows/${workflowId}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-lg font-bold leading-tight">{workflow.name}</h1>
            <p className="text-xs text-muted-foreground">Voice Call Workflow</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted px-2 py-1 rounded-md">
            <Zap className="w-3.5 h-3.5" />
            {steps.length} step{steps.length !== 1 ? 's' : ''}
          </div>
          <Button onClick={handleSave} disabled={isSaving} size="sm">
            <Save className="w-4 h-4 mr-2" />
            {isSaving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>

      {/* ── Main layout ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── Flow canvas (left) ── */}
        <div className="flex-1 overflow-y-auto bg-muted/20 p-8">
          <div className="flex flex-col items-center min-h-full">
            {/* Start node */}
            <div className="flex flex-col items-center">
              <div className="flex items-center gap-2 px-4 py-2 bg-card border-2 border-green-400 rounded-full shadow-sm">
                <Play className="w-4 h-4 text-green-600 fill-green-600" />
                <span className="text-sm font-semibold text-green-700">Call starts</span>
              </div>
            </div>

            {/* Steps */}
            {steps.length === 0 ? (
              <div className="flex flex-col items-center mt-4">
                <div className="w-px h-8 bg-border" />
                <AddStepPicker onAdd={addStep} />
                <div className="mt-8 text-center text-muted-foreground">
                  <div className="text-4xl mb-3">🎙️</div>
                  <p className="font-medium">Build your voice call flow</p>
                  <p className="text-sm mt-1">Add steps to define what the agent says and does</p>
                </div>
              </div>
            ) : (
              <div className="w-full max-w-sm mt-0">
                {steps.map((step, index) => (
                  <div key={step.id} className="group">
                    <FlowStepCard
                      step={step}
                      index={index}
                      total={steps.length}
                      selected={selectedStepIndex === index}
                      onClick={() => setSelectedStepIndex(index === selectedStepIndex ? null : index)}
                      onDelete={() => deleteStep(index)}
                      onMove={(dir) => moveStep(index, dir)}
                    />
                    {/* add step button between nodes */}
                    <AddStepPicker onAdd={addStep} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Config panel (right) ── */}
        <div className="w-96 border-l bg-card overflow-y-auto flex-shrink-0">
          {selectedStep ? (
            <div className="p-6 space-y-6">
              {/* panel header */}
              <div className="flex items-center gap-3">
                {(() => {
                  const meta = getStepMeta(selectedStep.type)
                  const Icon = meta.icon
                  return (
                    <>
                      <div className={`w-10 h-10 rounded-lg ${meta.color} flex items-center justify-center`}>
                        <Icon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h2 className="font-bold text-base">{meta.label}</h2>
                        <p className="text-xs text-muted-foreground">{meta.description}</p>
                      </div>
                    </>
                  )
                })()}
              </div>

              {/* step name */}
              <div className="space-y-1.5">
                <Label>Step name</Label>
                <Input
                  value={selectedStep.name}
                  onChange={(e) => updateStep(selectedStepIndex!, { name: e.target.value })}
                  placeholder="e.g. Greet caller"
                />
              </div>

              <div className="border-t" />

              {/* type-specific config */}
              <StepConfigPanel
                step={selectedStep}
                onUpdateConfig={(config) => updateStep(selectedStepIndex!, { config })}
                allSteps={steps}
              />

              {/* change type */}
              <div className="border-t pt-4">
                <Label className="text-xs text-muted-foreground uppercase tracking-wide">Change step type</Label>
                <div className="mt-2 grid grid-cols-2 gap-1.5">
                  {STEP_TYPES.map((t) => {
                    const Icon = t.icon
                    return (
                      <button
                        key={t.value}
                        onClick={() =>
                          updateStep(selectedStepIndex!, {
                            type: t.value,
                            config: getDefaultConfig(t.value),
                          })
                        }
                        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg border text-xs transition-colors ${
                          selectedStep.type === t.value
                            ? 'border-primary bg-primary/5 text-primary font-medium'
                            : 'border-border hover:border-primary/40 hover:bg-muted/50'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded ${t.color} flex items-center justify-center flex-shrink-0`}>
                          <Icon className="w-3 h-3 text-white" />
                        </div>
                        {t.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* delete */}
              <Button
                variant="destructive"
                size="sm"
                className="w-full"
                onClick={() => deleteStep(selectedStepIndex!)}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Remove this step
              </Button>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-8">
              <div className="text-center text-muted-foreground">
                <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <MessageSquare className="w-8 h-8" />
                </div>
                <p className="font-medium">Select a step</p>
                <p className="text-sm mt-1">Click any step in the flow to configure it</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
