'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, Plug, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

interface WorkflowTemplate {
  slug: string
  name: string
  description: string
  icon: string | null
  tags: string[]
  required_integrations: string[] | null
}

const INPUT_CLASS =
  'w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]'

/**
 * Create a workflow, from a template or from nothing.
 *
 * Templates lead because starting from a working example is the fastest way to
 * learn what the builder can do — a blank canvas teaches nothing about which
 * of seventeen step types to reach for. Both paths land in the builder, where
 * the trigger and steps are configured together.
 */
export default function NewWorkflowPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [installing, setInstalling] = useState<string | null>(null)
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(true)
  const [formData, setFormData] = useState({ name: '', description: '' })

  useEffect(() => {
    let cancelled = false

    apiClient
      .get<WorkflowTemplate[]>(API_ENDPOINTS.WORKFLOW_TEMPLATES, {
        params: { sort_by: 'popular', limit: 12 },
      })
      .then((res) => {
        if (!cancelled) setTemplates(res.data || [])
      })
      .catch(() => {
        // A marketplace that is unreachable must not block creating a workflow
        // by hand, so this degrades to the blank form rather than erroring.
        if (!cancelled) setTemplates([])
      })
      .finally(() => {
        if (!cancelled) setTemplatesLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const installTemplate = async (slug: string) => {
    setInstalling(slug)
    try {
      const res = await apiClient.post<{ created_workflow_id: string }>(
        API_ENDPOINTS.WORKFLOW_TEMPLATE_INSTALL(slug),
        { customizations: {} }
      )
      toast.success('Workflow created from template. Finish setting it up here.')
      router.push(`/dashboard/workflows/${res.data.created_workflow_id}/builder`)
    } catch (error) {
      console.error('Failed to install template:', error)
      toast.error(getErrorMessage(error))
      setInstalling(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const res = await apiClient.post<{ id: string }>(API_ENDPOINTS.WORKFLOWS, {
        name: formData.name,
        description: formData.description,
        // Created as manual, which needs no configuration and so can never be
        // rejected at creation. The trigger is chosen on the trigger node in
        // the builder, where its settings live alongside the rest of the flow.
        trigger_type: 'manual',
        trigger_config: {},
        workflow_steps: [],
        is_active: false,
        execution_mode: 'sequential',
        error_handling: 'stop',
        max_retries: 3,
        retry_delay: 60,
      })
      toast.success('Workflow created! Set its trigger and steps in the builder.')
      router.push(`/dashboard/workflows/${res.data.id}/builder`)
    } catch (error) {
      console.error('Failed to create workflow:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  const busy = isLoading || installing !== null

  return (
    <div className="space-y-8">
      {/* Templates */}
      {(templatesLoading || templates.length > 0) && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <div>
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-[#0F6A59]" />
              Start from a template
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              A working workflow you can open, read, and change. Installed
              inactive, so nothing runs until you switch it on.
            </p>
          </div>

          {templatesLoading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading templates…
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {templates.map((template) => {
                const needs = template.required_integrations ?? []
                const isInstalling = installing === template.slug

                return (
                  <button
                    key={template.slug}
                    type="button"
                    disabled={busy}
                    onClick={() => installTemplate(template.slug)}
                    className={cn(
                      'flex flex-col gap-2 rounded-xl border border-slate-200 p-4 text-left transition-colors',
                      'hover:border-[#0F6A59] hover:bg-[#0F6A59]/[0.03]',
                      'disabled:cursor-not-allowed disabled:opacity-60'
                    )}
                  >
                    <div className="flex items-start gap-2.5">
                      <span className="text-xl leading-none">
                        {template.icon || '⚙️'}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-[#000000]">
                          {template.name}
                        </p>
                        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                          {template.description}
                        </p>
                      </div>
                      {isInstalling && (
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                      )}
                    </div>

                    {/*
                      * Say up front what has to be connected. Finding out only
                      * after installing — from a blank required field on a
                      * step — is the worst moment to learn it.
                      */}
                    <span
                      className={cn(
                        'inline-flex w-fit items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium',
                        needs.length
                          ? 'bg-amber-500/10 text-amber-700'
                          : 'bg-emerald-500/10 text-emerald-700'
                      )}
                    >
                      {needs.length ? (
                        <>
                          <Plug className="h-3 w-3" />
                          Needs {needs.join(', ')}
                        </>
                      ) : (
                        'No setup needed'
                      )}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Blank */}
      <form onSubmit={handleSubmit} className="space-y-8">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-semibold">Or start from scratch</h2>

          <div className="space-y-2">
            <Label
              htmlFor="name"
              className="text-[14px] font-bold text-[#000000] font-poppins block"
            >
              Workflow Name *
            </Label>
            <Input
              id="name"
              placeholder="Lead Qualification Workflow"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              className={INPUT_CLASS}
            />
          </div>

          <div className="space-y-2">
            <Label
              htmlFor="description"
              className="text-[14px] font-bold text-[#000000] font-poppins block"
            >
              Description
            </Label>
            <Textarea
              id="description"
              placeholder="Qualifies inbound leads and routes them to the appropriate team"
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              rows={3}
              className="w-full rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 py-2 text-[14px]"
            />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
          <h3 className="font-semibold mb-2 text-[#000000]">What happens next</h3>
          <p className="text-sm text-muted-foreground mb-4">
            You&apos;ll land in the visual builder. Choose how the workflow
            starts on its trigger step — on a schedule, from a webhook, after a
            call, or manually — then add the steps below it.
          </p>
          <div className="flex flex-wrap gap-2 text-xs">
            {[
              'Speak',
              'Ask Question',
              'Branch',
              'Transfer',
              'Run Tool',
              'Webhook',
              'AI Response',
              'End Call',
            ].map((s) => (
              <span
                key={s}
                className="rounded bg-white px-2 py-1 border border-slate-200 font-medium text-[#000000]"
              >
                {s}
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <Button type="submit" size="lg" disabled={busy}>
            {isLoading ? 'Creating...' : 'Create Workflow'}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => router.push('/dashboard/workflows')}
            disabled={busy}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  )
}
