'use client'

import { useMemo, useState } from 'react'
import { AlertTriangle, Check, Copy } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { API_ENDPOINTS } from '@/lib/constants'
import { useAgentOptions } from '@/hooks/useAgentOptions'
import { useEntitlementStore } from '@/store/entitlementStore'
import { FEATURES } from '@/lib/entitlements'
import {
  INTEGRATION_TYPES,
  TRIGGER_ORDER,
  WEEKDAYS,
  describeTrigger,
  getTriggerDescriptor,
  isKnownTriggerType,
  scheduleConfigFromForm,
  scheduleFormFromConfig,
  validateTrigger,
  type ScheduleForm,
  type SchedulePreset,
} from '@/lib/workflow/triggerTypes'

const SELECT_CLASS =
  'h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30'

export interface TriggerState {
  type: string
  config: Record<string, any>
}

interface TriggerConfigProps {
  trigger: TriggerState
  /**
   * The trigger as last persisted, used to say what is actually running while
   * an edit is still incomplete.
   */
  savedTrigger?: TriggerState | null
  /** Whether the workflow is active. An inactive workflow ignores its trigger. */
  isActive?: boolean
  onChange: (trigger: TriggerState) => void
}

/**
 * How the workflow starts.
 *
 * This lives in the builder's trigger node rather than on a separate settings
 * form: the trigger is the first thing in the flow, and splitting it across
 * two screens meant the canvas could never show what actually started the
 * workflow.
 *
 * The workflow row remains the single source of truth — the trigger is *not*
 * mirrored into the graph — so this component edits page state that is saved
 * alongside the graph.
 */
export function TriggerConfig({
  trigger,
  savedTrigger,
  isActive = true,
  onChange,
}: TriggerConfigProps) {
  const descriptor = getTriggerDescriptor(trigger.type)
  const error = validateTrigger(trigger.type, trigger.config)
  const known = isKnownTriggerType(trigger.type)

  // While the edit is incomplete the workflow keeps running whatever was last
  // saved. Saying so matters most when the *type* has changed: the panel would
  // otherwise read "Integration event" for a workflow still firing on its old
  // schedule, which is the opposite of what the builder is for.
  const liveTrigger =
    error && savedTrigger && savedTrigger.type !== trigger.type
      ? describeTrigger(savedTrigger.type, savedTrigger.config)
      : null

  // Automatic triggers fire from background loops and unauthenticated
  // endpoints, so the plan check happens there rather than on a request the
  // user can see fail. Without this the workflow saves cleanly, looks correct,
  // and simply never runs — the only trace is a line in the server log.
  // Selectors, not the whole store: this panel re-renders on every keystroke
  // and only needs two booleans out of it.
  const scheduledAllowed = useEntitlementStore((s) =>
    s.has(FEATURES.WORKFLOW_SCHEDULING)
  )
  const plansLoading = useEntitlementStore((s) => s.isLoading)
  const planBlocked =
    trigger.type !== 'manual' && !plansLoading && !scheduledAllowed

  const setType = (type: string) => {
    // Seed a valid default rather than carrying the previous type's keys
    // across: a schedule config left on a webhook trigger is meaningless, and
    // the backend validates whatever it is handed.
    onChange({ type, config: getTriggerDescriptor(type).defaultConfig() })
  }

  const setConfig = (config: Record<string, any>) =>
    onChange({ type: trigger.type, config })

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="trigger-type">Start this workflow</Label>
        <select
          id="trigger-type"
          value={trigger.type}
          onChange={(e) => setType(e.target.value)}
          className={SELECT_CLASS}
        >
          {!known && (
            <option value={trigger.type}>{trigger.type} (unsupported)</option>
          )}
          {TRIGGER_ORDER.map((type) => (
            <option key={type} value={type}>
              {getTriggerDescriptor(type).label}
            </option>
          ))}
        </select>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {descriptor.description}
        </p>
      </div>

      {/*
        * Every automatic trigger is gated on the workflow being active: the
        * scheduler only queries active rows, and the webhook endpoint answers
        * 404 for an inactive one. Saying so here is the difference between
        * "my webhook is broken" and "switch it on".
        */}
      {planBlocked && (
        <p className="flex items-start gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 p-2.5 text-[11px] leading-relaxed text-amber-700 dark:text-amber-400">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" />
          <span>
            Your plan does not include scheduled and triggered workflows, so
            this trigger will not fire. You can still build the workflow and run
            it manually, or upgrade to have it run on its own.
          </span>
        </p>
      )}

      {!isActive && trigger.type !== 'manual' && (
        <p className="flex items-start gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 p-2.5 text-[11px] leading-relaxed text-amber-700 dark:text-amber-400">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" />
          <span>
            This workflow is inactive, so nothing will start it. Activate it
            from the workflow page once the steps are ready.
          </span>
        </p>
      )}

      {trigger.type === 'schedule' && (
        <ScheduleFields config={trigger.config} onChange={setConfig} />
      )}

      {trigger.type === 'webhook' && <WebhookFields config={trigger.config} />}

      {(trigger.type === 'call_completed' || trigger.type === 'call_started') && (
        <CallFilterFields config={trigger.config} onChange={setConfig} />
      )}

      {trigger.type === 'integration_event' && (
        <IntegrationEventFields config={trigger.config} onChange={setConfig} />
      )}

      {trigger.type === 'manual' && (
        <p className="rounded-md border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
          Run this workflow from its page, or let a voice agent call it as a
          tool. Inputs you declare below become the parameters the agent fills
          in.
        </p>
      )}

      {error && (
        <div className="flex items-start gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 p-2.5 text-[11px] leading-relaxed text-amber-700 dark:text-amber-400">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" />
          <div className="space-y-1">
            <p>
              {error} The trigger is not saved until this is fixed — the rest
              of the workflow still saves.
            </p>
            {liveTrigger && (
              <p className="font-medium">
                Until then this workflow still runs on its saved trigger:{' '}
                {liveTrigger}.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Schedule
// ---------------------------------------------------------------------------

const PRESETS: { value: SchedulePreset; label: string }[] = [
  { value: 'minutes', label: 'Every N minutes' },
  { value: 'hours', label: 'Every N hours' },
  { value: 'daily', label: 'Every day' },
  { value: 'weekly', label: 'Every week' },
  { value: 'monthly', label: 'Every month' },
  { value: 'once', label: 'Once, at a set time' },
  { value: 'cron', label: 'Custom (cron)' },
]

function ScheduleFields({
  config,
  onChange,
}: {
  config: Record<string, any>
  onChange: (config: Record<string, any>) => void
}) {
  // The stored config is lossy (several presets compile to cron), so the form
  // is derived from it once and then held locally. Deriving on every render
  // would snap "every 90 minutes" back to the nearest representable preset
  // mid-edit.
  const [form, setForm] = useState<ScheduleForm>(() =>
    scheduleFormFromConfig(config)
  )

  const update = (patch: Partial<ScheduleForm>) => {
    const next = { ...form, ...patch }
    setForm(next)
    onChange(scheduleConfigFromForm(next))
  }

  const timeFields = (
    <div className="space-y-2">
      <Label htmlFor="schedule-time">At</Label>
      <Input
        id="schedule-time"
        type="time"
        value={`${String(form.hour).padStart(2, '0')}:${String(form.minute).padStart(2, '0')}`}
        onChange={(e) => {
          const [hour, minute] = e.target.value.split(':').map(Number)
          if (Number.isNaN(hour) || Number.isNaN(minute)) return
          update({ hour, minute })
        }}
      />
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="schedule-preset">How often</Label>
        <select
          id="schedule-preset"
          value={form.preset}
          onChange={(e) => update({ preset: e.target.value as SchedulePreset })}
          className={SELECT_CLASS}
        >
          {PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      </div>

      {(form.preset === 'minutes' || form.preset === 'hours') && (
        <div className="space-y-2">
          <Label htmlFor="schedule-every">
            Run every ({form.preset === 'minutes' ? 'minutes' : 'hours'})
          </Label>
          <Input
            id="schedule-every"
            type="number"
            min={1}
            value={form.every}
            onChange={(e) => update({ every: Math.max(1, Number(e.target.value) || 1) })}
          />
          <p className="text-[11px] text-muted-foreground">
            The scheduler checks every 30 seconds, so intervals shorter than
            that run once per check.
          </p>
        </div>
      )}

      {form.preset === 'daily' && timeFields}

      {form.preset === 'weekly' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="schedule-weekday">On</Label>
            <select
              id="schedule-weekday"
              value={form.weekday}
              onChange={(e) => update({ weekday: Number(e.target.value) })}
              className={SELECT_CLASS}
            >
              {WEEKDAYS.map((day) => (
                <option key={day.value} value={day.value}>
                  {day.label}
                </option>
              ))}
            </select>
          </div>
          {timeFields}
        </>
      )}

      {form.preset === 'monthly' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="schedule-day">On day of month</Label>
            <Input
              id="schedule-day"
              type="number"
              min={1}
              max={28}
              value={form.day}
              onChange={(e) =>
                update({ day: Math.min(28, Math.max(1, Number(e.target.value) || 1)) })
              }
            />
            <p className="text-[11px] text-muted-foreground">
              Capped at 28 so the run never skips a short month.
            </p>
          </div>
          {timeFields}
        </>
      )}

      {form.preset === 'once' && (
        <div className="space-y-2">
          <Label htmlFor="schedule-at">Date and time (UTC)</Label>
          <Input
            id="schedule-at"
            type="datetime-local"
            value={form.at}
            onChange={(e) => update({ at: e.target.value })}
          />
          <p className="text-[11px] text-muted-foreground">
            The workflow deactivates itself after this single run.
          </p>
        </div>
      )}

      {form.preset === 'cron' && (
        <div className="space-y-2">
          <Label htmlFor="schedule-cron">Cron expression</Label>
          <Input
            id="schedule-cron"
            value={form.expression}
            placeholder="0 9 * * 1-5"
            className="font-mono text-xs"
            onChange={(e) => update({ expression: e.target.value })}
          />
          <p className="text-[11px] text-muted-foreground">
            Five fields: minute, hour, day of month, month, day of week.
          </p>
        </div>
      )}

      {form.preset !== 'minutes' && form.preset !== 'hours' && form.preset !== 'once' && (
        <div className="space-y-2">
          <Label htmlFor="schedule-timezone">Time zone</Label>
          <Input
            id="schedule-timezone"
            value={form.timezone}
            placeholder="UTC"
            onChange={(e) => update({ timezone: e.target.value })}
          />
          <p className="text-[11px] text-muted-foreground">
            An IANA name such as UTC, Europe/London, or Asia/Karachi.
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Webhook
// ---------------------------------------------------------------------------

function WebhookFields({ config }: { config: Record<string, any> }) {
  const [copied, setCopied] = useState(false)
  const key = config.webhook_key as string | undefined
  const url = key ? API_ENDPOINTS.WORKFLOW_WEBHOOK(key) : null

  const copy = async () => {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can be denied; the URL is selectable either way.
    }
  }

  if (!url) {
    return (
      <p className="rounded-md border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
        Save the workflow to generate its webhook URL.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label htmlFor="webhook-url">Webhook URL</Label>
        <div className="flex gap-1.5">
          <Input
            id="webhook-url"
            readOnly
            value={url}
            onFocus={(e) => e.currentTarget.select()}
            className="font-mono text-[11px]"
          />
          <button
            type="button"
            onClick={copy}
            title="Copy URL"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border text-muted-foreground transition-colors hover:bg-accent"
          >
            {copied ? (
              <Check className="h-4 w-4 text-emerald-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          POST JSON here to run the workflow. The body is available to later
          steps as {'{{trigger.payload}}'}.
        </p>
      </div>

      <details className="rounded-md border bg-muted/40 p-3">
        <summary className="cursor-pointer text-xs font-medium">
          Example request
        </summary>
        <pre className="mt-2 overflow-x-auto whitespace-pre text-[10px] leading-relaxed text-muted-foreground">
{`curl -X POST '${url}' \\
  -H 'Content-Type: application/json' \\
  -d '{"name": "Ada", "email": "ada@example.com"}'`}
        </pre>
      </details>

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        Anyone with this URL can start the workflow. Treat it as a secret.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Call events
// ---------------------------------------------------------------------------

/**
 * Filters for call-event triggers.
 *
 * These are stored under `filters`, which is where `VoiceEventTriggerHandler`
 * reads them. A previous version wrote `agent_id` at the top level, where
 * nothing read it — so the workflow fired for every agent's calls regardless
 * of the one chosen.
 */
function CallFilterFields({
  config,
  onChange,
}: {
  config: Record<string, any>
  onChange: (config: Record<string, any>) => void
}) {
  // Tolerate the legacy top-level shape when reopening an old workflow.
  const filters: Record<string, any> = useMemo(
    () => ({
      ...(config.agent_id ? { agent_id: config.agent_id } : {}),
      ...(config.filters || {}),
    }),
    [config]
  )

  const { agents, isLoading } = useAgentOptions(true)

  const setFilter = (key: string, value: unknown) => {
    const next = { ...filters }
    if (value === '' || value === undefined || value === null) {
      delete next[key]
    } else {
      next[key] = value
    }
    // Written as `filters` only — the legacy top-level key is dropped on the
    // first edit so the two shapes cannot drift apart.
    onChange({ filters: next })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="filter-agent">Only for agent</Label>
        <select
          id="filter-agent"
          value={filters.agent_id ?? ''}
          onChange={(e) => setFilter('agent_id', e.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">Any agent</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        {!isLoading && agents.length === 0 && (
          <p className="text-[11px] text-muted-foreground">
            No agents yet — create one to filter by agent.
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="filter-duration">Only if the call lasted at least</Label>
        <Input
          id="filter-duration"
          type="number"
          min={0}
          placeholder="Any length (seconds)"
          value={filters.duration_min ?? ''}
          onChange={(e) =>
            setFilter(
              'duration_min',
              e.target.value === '' ? '' : Number(e.target.value)
            )
          }
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="filter-keywords">Only if the transcript mentions</Label>
        <Input
          id="filter-keywords"
          placeholder="refund, cancel"
          value={
            Array.isArray(filters.keywords)
              ? filters.keywords.join(', ')
              : (filters.keywords ?? '')
          }
          onChange={(e) => {
            const words = e.target.value
              .split(',')
              .map((w) => w.trim())
              .filter(Boolean)
            setFilter('keywords', words.length ? words : '')
          }}
        />
        <p className="text-[11px] text-muted-foreground">
          Comma-separated. Every word must appear for the workflow to run.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Integration events
// ---------------------------------------------------------------------------

/** Event names commonly posted per app, offered as hints rather than a fixed list. */
const EVENT_SUGGESTIONS: Record<string, string[]> = {
  salesforce: ['lead.created', 'opportunity.updated', 'contact.created'],
  hubspot: ['contact.creation', 'deal.propertyChange', 'company.creation'],
  stripe: ['payment_intent.succeeded', 'invoice.paid', 'customer.subscription.deleted'],
  slack: ['message.channels', 'app_mention', 'reaction_added'],
  sendgrid: ['delivered', 'open', 'bounce'],
  'google-calendar': ['event.created', 'event.updated', 'event.cancelled'],
}

function IntegrationEventFields({
  config,
  onChange,
}: {
  config: Record<string, any>
  onChange: (config: Record<string, any>) => void
}) {
  const integrationType = String(config.integration_type || '')
  const suggestions = EVENT_SUGGESTIONS[integrationType] ?? []

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="integration-type">App</Label>
        <select
          id="integration-type"
          value={integrationType}
          onChange={(e) =>
            // Event names are app-specific, so a changed app invalidates the
            // event rather than silently keeping one that can never match.
            onChange({ integration_type: e.target.value, event_type: '' })
          }
          className={SELECT_CLASS}
        >
          <option value="">Select an app…</option>
          {INTEGRATION_TYPES.map((integration) => (
            <option key={integration.value} value={integration.value}>
              {integration.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="integration-event">Event</Label>
        <Input
          id="integration-event"
          list="integration-event-suggestions"
          placeholder={suggestions[0] ?? 'contact.created'}
          value={config.event_type ?? ''}
          onChange={(e) =>
            onChange({ ...config, event_type: e.target.value })
          }
        />
        <datalist id="integration-event-suggestions">
          {suggestions.map((event) => (
            <option key={event} value={event} />
          ))}
        </datalist>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Must match the event name posted to the integration-event endpoint
          exactly. The event body is available as {'{{trigger.payload}}'}.
        </p>
      </div>
    </div>
  )
}
