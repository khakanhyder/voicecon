/**
 * Workflow trigger registry.
 *
 * A workflow's trigger lives on the workflow row (`trigger_type` /
 * `trigger_config`), not in the graph, so it cannot be described by a node
 * descriptor. This module plays the same role for triggers that
 * `nodeTypes.ts` plays for steps: one descriptor per type drives the trigger
 * panel, the canvas summary, and client-side validation.
 *
 * Config shapes here must match what the backend actually reads:
 *   - `TriggerValidator` in `trigger_handlers.py` (accept/reject)
 *   - `WorkflowScheduler` in `scheduler.py` (schedule execution)
 *   - `VoiceEventTriggerHandler` / `IntegrationEventTriggerHandler` (matching)
 */

export type TriggerTypeId =
  | 'manual'
  | 'webhook'
  | 'schedule'
  | 'call_completed'
  | 'call_started'
  | 'integration_event'

export interface TriggerDescriptor {
  type: TriggerTypeId
  label: string
  /** One line explaining when to pick this trigger. */
  description: string
  /** Lucide icon name, resolved in the icon map. */
  icon: string
  /**
   * Config seeded when the user switches to this type.
   *
   * Every default must already be valid, so switching type can never leave
   * the workflow in a state the API rejects.
   */
  defaultConfig: () => Record<string, any>
  /** Plain-English summary, shown on the canvas node and the panel header. */
  summary: (config: Record<string, any>) => string
  /**
   * Client-side mirror of the backend validator. Returns an error message, or
   * null when the config is acceptable.
   */
  validate: (config: Record<string, any>) => string | null
}

// ---------------------------------------------------------------------------
// Schedules
// ---------------------------------------------------------------------------

/** Integration types the backend's `_validate_integration_event` accepts. */
export const INTEGRATION_TYPES = [
  { value: 'salesforce', label: 'Salesforce' },
  { value: 'hubspot', label: 'HubSpot' },
  { value: 'stripe', label: 'Stripe' },
  { value: 'slack', label: 'Slack' },
  { value: 'sendgrid', label: 'SendGrid' },
  { value: 'google-calendar', label: 'Google Calendar' },
] as const

export const WEEKDAYS = [
  { value: 0, label: 'Sunday' },
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
]

/**
 * How the schedule is presented, which is deliberately not how it is stored.
 *
 * Users think in "every day at 9am"; the scheduler thinks in cron. Presets are
 * the translation layer, so nobody has to write `0 9 * * *` to get a daily run.
 */
export type SchedulePreset =
  | 'minutes'
  | 'hours'
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'once'
  | 'cron'

export interface ScheduleForm {
  preset: SchedulePreset
  /** minutes / hours presets. */
  every: number
  /** daily / weekly / monthly presets, and the display for `once`. */
  hour: number
  minute: number
  weekday: number
  day: number
  /** `once` preset: a `datetime-local` value. */
  at: string
  /** `cron` preset. */
  expression: string
  timezone: string
}

const CRON_FIELD = /^(\*|\d+|\d+-\d+|(\*|\d+)\/\d+|(\d+(,\d+)+))$/

/** Structural cron check. `croniter` on the backend remains authoritative. */
export function isValidCron(expression: string): boolean {
  const fields = expression.trim().split(/\s+/)
  if (fields.length !== 5) return false
  return fields.every((field) => CRON_FIELD.test(field))
}

const pad = (n: number) => String(n).padStart(2, '0')

/** The browser's IANA zone, falling back to UTC where it is unavailable. */
export function localTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

export function defaultScheduleForm(): ScheduleForm {
  return {
    preset: 'daily',
    every: 30,
    hour: 9,
    minute: 0,
    weekday: 1,
    day: 1,
    at: '',
    expression: '0 9 * * *',
    timezone: localTimezone(),
  }
}

/**
 * Recover the editing form from a stored config.
 *
 * Storage is lossy on purpose — several presets compile to cron — so a cron
 * expression that does not match a known preset shape reopens as "Custom",
 * which is accurate rather than a guess.
 */
export function scheduleFormFromConfig(
  config: Record<string, any>
): ScheduleForm {
  const form = defaultScheduleForm()
  form.timezone = config.timezone || form.timezone

  const scheduleType = config.schedule_type

  if (scheduleType === 'interval') {
    const seconds = Number(config.interval_seconds) || 3600
    if (seconds % 3600 === 0) {
      form.preset = 'hours'
      form.every = seconds / 3600
    } else {
      form.preset = 'minutes'
      form.every = Math.max(1, Math.round(seconds / 60))
    }
    return form
  }

  if (scheduleType === 'one_time') {
    form.preset = 'once'
    // `datetime-local` wants `YYYY-MM-DDTHH:MM` with no zone suffix.
    form.at = String(config.scheduled_at || '').slice(0, 16)
    return form
  }

  if (scheduleType === 'cron') {
    const expression = String(config.cron_expression || '').trim()
    form.expression = expression || form.expression

    const [minute, hour, dom, month, dow] = expression.split(/\s+/)
    const numeric = (v: string) => /^\d+$/.test(v)

    if (numeric(minute) && numeric(hour) && month === '*') {
      form.minute = Number(minute)
      form.hour = Number(hour)

      if (dom === '*' && dow === '*') {
        form.preset = 'daily'
        return form
      }
      if (dom === '*' && numeric(dow)) {
        form.preset = 'weekly'
        form.weekday = Number(dow)
        return form
      }
      if (numeric(dom) && dow === '*') {
        form.preset = 'monthly'
        form.day = Number(dom)
        return form
      }
    }

    form.preset = 'cron'
    return form
  }

  return form
}

/** Compile the editing form down to the config the backend stores and runs. */
export function scheduleConfigFromForm(form: ScheduleForm): Record<string, any> {
  switch (form.preset) {
    case 'minutes':
      return {
        schedule_type: 'interval',
        interval_seconds: Math.max(1, Math.round(form.every)) * 60,
      }
    case 'hours':
      return {
        schedule_type: 'interval',
        interval_seconds: Math.max(1, Math.round(form.every)) * 3600,
      }
    case 'daily':
      return {
        schedule_type: 'cron',
        cron_expression: `${form.minute} ${form.hour} * * *`,
        timezone: form.timezone,
      }
    case 'weekly':
      return {
        schedule_type: 'cron',
        cron_expression: `${form.minute} ${form.hour} * * ${form.weekday}`,
        timezone: form.timezone,
      }
    case 'monthly':
      return {
        schedule_type: 'cron',
        cron_expression: `${form.minute} ${form.hour} ${form.day} * *`,
        timezone: form.timezone,
      }
    case 'once':
      return {
        schedule_type: 'one_time',
        // Sent without a zone suffix; the backend reads naive values as UTC.
        scheduled_at: form.at,
      }
    case 'cron':
    default:
      return {
        schedule_type: 'cron',
        cron_expression: form.expression.trim(),
        timezone: form.timezone,
      }
  }
}

function describeSchedule(config: Record<string, any>): string {
  const scheduleType = config.schedule_type

  if (scheduleType === 'interval') {
    const seconds = Number(config.interval_seconds) || 0
    if (!seconds) return 'No interval set'
    if (seconds % 3600 === 0) {
      const hours = seconds / 3600
      return hours === 1 ? 'Every hour' : `Every ${hours} hours`
    }
    const minutes = Math.round(seconds / 60)
    return minutes === 1 ? 'Every minute' : `Every ${minutes} minutes`
  }

  if (scheduleType === 'one_time') {
    if (!config.scheduled_at) return 'No date set'
    return `Once on ${String(config.scheduled_at).replace('T', ' ').slice(0, 16)}`
  }

  if (scheduleType === 'cron') {
    const expression = String(config.cron_expression || '').trim()
    if (!expression) return 'No schedule set'

    const zone = config.timezone && config.timezone !== 'UTC' ? ` ${config.timezone}` : ' UTC'
    const [minute, hour, dom, month, dow] = expression.split(/\s+/)
    const numeric = (v: string) => /^\d+$/.test(v)

    if (numeric(minute) && numeric(hour) && month === '*') {
      const time = `${pad(Number(hour))}:${pad(Number(minute))}`
      if (dom === '*' && dow === '*') return `Every day at ${time}${zone}`
      if (dom === '*' && numeric(dow)) {
        const day = WEEKDAYS.find((d) => d.value === Number(dow))?.label ?? 'day'
        return `Every ${day} at ${time}${zone}`
      }
      if (numeric(dom) && dow === '*') {
        return `Day ${Number(dom)} of each month at ${time}${zone}`
      }
    }

    return `Cron: ${expression}${zone}`
  }

  return 'No schedule set'
}

// ---------------------------------------------------------------------------
// Descriptors
// ---------------------------------------------------------------------------

export const TRIGGER_TYPES: Record<TriggerTypeId, TriggerDescriptor> = {
  manual: {
    type: 'manual',
    label: 'Run manually',
    description: 'Only runs when you start it, or when an agent calls it as a tool',
    icon: 'MousePointerClick',
    defaultConfig: () => ({}),
    summary: () => 'Started manually',
    validate: () => null,
  },

  webhook: {
    type: 'webhook',
    label: 'Webhook',
    description: 'Runs when an external system posts to a URL',
    icon: 'Globe',
    // The key is generated server-side when absent, so an empty config is
    // valid here and comes back filled in.
    defaultConfig: () => ({}),
    summary: (config) =>
      config.webhook_key ? 'When the webhook URL is called' : 'Webhook URL is generated on save',
    validate: (config) => {
      const key = config.webhook_key
      if (key !== undefined && (typeof key !== 'string' || key.length < 16)) {
        return 'Webhook key must be at least 16 characters.'
      }
      return null
    },
  },

  schedule: {
    type: 'schedule',
    label: 'Schedule',
    description: 'Runs on a repeating schedule, or once at a set time',
    icon: 'CalendarClock',
    defaultConfig: () => scheduleConfigFromForm(defaultScheduleForm()),
    summary: describeSchedule,
    validate: (config) => {
      const scheduleType = config.schedule_type
      if (!scheduleType) return 'Pick how often this should run.'

      if (scheduleType === 'cron') {
        const expression = String(config.cron_expression || '').trim()
        if (!expression) return 'Enter a cron expression.'
        if (!isValidCron(expression)) {
          return 'That cron expression is not valid. It needs 5 fields, e.g. 0 9 * * *'
        }
        return null
      }

      if (scheduleType === 'interval') {
        const seconds = config.interval_seconds
        if (!Number.isInteger(seconds) || seconds <= 0) {
          return 'Enter how often this should run.'
        }
        return null
      }

      if (scheduleType === 'one_time') {
        const at = config.scheduled_at
        if (!at) return 'Pick the date and time to run.'
        if (Number.isNaN(Date.parse(String(at)))) return 'That date and time is not valid.'
        return null
      }

      return `Unsupported schedule type: ${scheduleType}`
    },
  },

  call_completed: {
    type: 'call_completed',
    label: 'Call completed',
    description: 'Runs after a call ends',
    icon: 'PhoneOff',
    defaultConfig: () => ({ filters: {} }),
    summary: (config) => {
      const filters = config.filters || {}
      const count = Object.keys(filters).length
      return count ? `After a call ends (${count} filter${count > 1 ? 's' : ''})` : 'After any call ends'
    },
    validate: (config) => {
      if (config.filters && typeof config.filters !== 'object') {
        return 'Filters must be a set of fields.'
      }
      return null
    },
  },

  call_started: {
    type: 'call_started',
    label: 'Call started',
    description: 'Runs as soon as a call begins',
    icon: 'PhoneCall',
    defaultConfig: () => ({ filters: {} }),
    summary: (config) => {
      const filters = config.filters || {}
      const count = Object.keys(filters).length
      return count ? `When a call starts (${count} filter${count > 1 ? 's' : ''})` : 'When any call starts'
    },
    validate: (config) => {
      if (config.filters && typeof config.filters !== 'object') {
        return 'Filters must be a set of fields.'
      }
      return null
    },
  },

  integration_event: {
    type: 'integration_event',
    label: 'Integration event',
    description: 'Runs when a connected app reports an event',
    icon: 'Plug',
    defaultConfig: () => ({ integration_type: 'hubspot', event_type: '' }),
    summary: (config) => {
      const app = INTEGRATION_TYPES.find((i) => i.value === config.integration_type)
      if (!app) return 'No app selected'
      if (!config.event_type) return `${app.label} — no event selected`
      return `${app.label}: ${config.event_type}`
    },
    validate: (config) => {
      const valid = INTEGRATION_TYPES.some((i) => i.value === config.integration_type)
      if (!valid) return 'Pick which app sends the event.'
      if (!String(config.event_type || '').trim()) return 'Enter the event name to listen for.'
      return null
    },
  },
}

/** Types offered in the picker, in the order they are shown. */
export const TRIGGER_ORDER: TriggerTypeId[] = [
  'manual',
  'call_completed',
  'call_started',
  'schedule',
  'webhook',
  'integration_event',
]

/**
 * Descriptor for a trigger type this build does not know.
 *
 * Falling back to another descriptor would let `defaultConfig` overwrite a
 * stored config that the backend still understands.
 */
const UNKNOWN_TRIGGER: TriggerDescriptor = {
  type: 'manual',
  label: 'Unsupported trigger',
  description: 'This trigger type is not available in the builder.',
  icon: 'HelpCircle',
  defaultConfig: () => ({}),
  summary: () => 'Not editable here',
  validate: () => null,
}

export function getTriggerDescriptor(type: string): TriggerDescriptor {
  return TRIGGER_TYPES[type as TriggerTypeId] ?? UNKNOWN_TRIGGER
}

export function isKnownTriggerType(type: string): boolean {
  return type in TRIGGER_TYPES
}

/** Plain-English summary of a workflow's trigger, for canvas and list views. */
export function describeTrigger(type: string, config: Record<string, any>): string {
  return getTriggerDescriptor(type).summary(config || {})
}

/** Client-side validation, or null when the config is acceptable. */
export function validateTrigger(
  type: string,
  config: Record<string, any>
): string | null {
  return getTriggerDescriptor(type).validate(config || {})
}
