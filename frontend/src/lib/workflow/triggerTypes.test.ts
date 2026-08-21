/**
 * Unit tests for the trigger registry.
 *
 * The schedule form is deliberately lossy in one direction — "every day at
 * 09:00" and "every Monday at 09:00" both compile to cron — so the risk is the
 * *reverse* trip: reopening a saved workflow must not silently rewrite its
 * schedule into something else. Most of these tests are therefore round trips.
 *
 * The config shapes asserted here are contracts with the backend, not internal
 * details: `TriggerValidator` accepts or rejects them, and `WorkflowScheduler`
 * reads `cron_expression` / `interval_seconds` / `scheduled_at` by those exact
 * names.
 */
import { describe, expect, it } from 'vitest'

import {
  INTEGRATION_TYPES,
  TRIGGER_ORDER,
  describeTrigger,
  defaultScheduleForm,
  getTriggerDescriptor,
  isKnownTriggerType,
  isValidCron,
  scheduleConfigFromForm,
  scheduleFormFromConfig,
  validateTrigger,
  type ScheduleForm,
} from './triggerTypes'

function form(overrides: Partial<ScheduleForm> = {}): ScheduleForm {
  return { ...defaultScheduleForm(), timezone: 'UTC', ...overrides }
}

describe('trigger descriptors', () => {
  it('offers every type it can describe', () => {
    for (const type of TRIGGER_ORDER) {
      expect(isKnownTriggerType(type)).toBe(true)
    }
  })

  it('seeds a ready-to-run config wherever a default is meaningful', () => {
    // Switching type replaces the config wholesale, so a default that fails
    // validation would leave the trigger unsavable through no user action.
    // `integration_event` is the one type that cannot have one: the event name
    // is the whole point of the trigger and nothing can guess it.
    for (const type of TRIGGER_ORDER) {
      if (type === 'integration_event') continue
      const config = getTriggerDescriptor(type).defaultConfig()
      expect(validateTrigger(type, config)).toBeNull()
    }
  })

  it('marks a freshly-picked integration event as needing input', () => {
    const config = getTriggerDescriptor('integration_event').defaultConfig()
    expect(validateTrigger('integration_event', config)).toBeTruthy()
  })

  it('does not overwrite the config of a type it does not know', () => {
    const descriptor = getTriggerDescriptor('some_future_trigger')
    expect(isKnownTriggerType('some_future_trigger')).toBe(false)
    // No fields, so opening the panel cannot rewrite what the backend stored.
    expect(descriptor.defaultConfig()).toEqual({})
    expect(descriptor.validate({ anything: true })).toBeNull()
  })
})

describe('cron validation', () => {
  it('accepts the expressions the presets generate', () => {
    expect(isValidCron('0 9 * * *')).toBe(true)
    expect(isValidCron('30 14 * * 1')).toBe(true)
    expect(isValidCron('0 0 15 * *')).toBe(true)
  })

  it('accepts ranges, steps and lists', () => {
    expect(isValidCron('0 9 * * 1-5')).toBe(true)
    expect(isValidCron('*/15 * * * *')).toBe(true)
    expect(isValidCron('0 9,17 * * *')).toBe(true)
  })

  it('rejects the wrong number of fields', () => {
    expect(isValidCron('0 9 * *')).toBe(false)
    expect(isValidCron('0 9 * * * *')).toBe(false)
    expect(isValidCron('')).toBe(false)
  })

  it('rejects non-cron text', () => {
    expect(isValidCron('every day at 9')).toBe(false)
    expect(isValidCron('@daily')).toBe(false)
  })
})

describe('schedule round trip', () => {
  it('keeps a minute interval', () => {
    const config = scheduleConfigFromForm(form({ preset: 'minutes', every: 15 }))
    expect(config).toEqual({ schedule_type: 'interval', interval_seconds: 900 })

    const reopened = scheduleFormFromConfig(config)
    expect(reopened.preset).toBe('minutes')
    expect(reopened.every).toBe(15)
  })

  it('reopens whole-hour intervals as hours, not 60-minute steps', () => {
    const config = scheduleConfigFromForm(form({ preset: 'hours', every: 6 }))
    expect(config).toEqual({ schedule_type: 'interval', interval_seconds: 21600 })

    const reopened = scheduleFormFromConfig(config)
    expect(reopened.preset).toBe('hours')
    expect(reopened.every).toBe(6)
  })

  it('keeps a daily schedule', () => {
    const config = scheduleConfigFromForm(
      form({ preset: 'daily', hour: 9, minute: 30 })
    )
    expect(config.cron_expression).toBe('30 9 * * *')

    const reopened = scheduleFormFromConfig(config)
    expect(reopened.preset).toBe('daily')
    expect(reopened.hour).toBe(9)
    expect(reopened.minute).toBe(30)
  })

  it('keeps a weekly schedule, including the day', () => {
    const config = scheduleConfigFromForm(
      form({ preset: 'weekly', weekday: 5, hour: 17, minute: 0 })
    )
    expect(config.cron_expression).toBe('0 17 * * 5')

    const reopened = scheduleFormFromConfig(config)
    expect(reopened.preset).toBe('weekly')
    expect(reopened.weekday).toBe(5)
    expect(reopened.hour).toBe(17)
  })

  it('keeps a monthly schedule, including the day of month', () => {
    const config = scheduleConfigFromForm(
      form({ preset: 'monthly', day: 15, hour: 8, minute: 45 })
    )
    expect(config.cron_expression).toBe('45 8 15 * *')

    const reopened = scheduleFormFromConfig(config)
    expect(reopened.preset).toBe('monthly')
    expect(reopened.day).toBe(15)
    expect(reopened.minute).toBe(45)
  })

  it('keeps a one-time schedule', () => {
    const config = scheduleConfigFromForm(
      form({ preset: 'once', at: '2026-09-01T14:30' })
    )
    expect(config).toEqual({
      schedule_type: 'one_time',
      scheduled_at: '2026-09-01T14:30',
    })
    expect(scheduleFormFromConfig(config).preset).toBe('once')
  })

  it('preserves the timezone through the round trip', () => {
    const config = scheduleConfigFromForm(
      form({ preset: 'daily', timezone: 'Asia/Karachi' })
    )
    expect(config.timezone).toBe('Asia/Karachi')
    expect(scheduleFormFromConfig(config).timezone).toBe('Asia/Karachi')
  })

  it('reopens an unrecognised cron shape as custom rather than guessing', () => {
    // A weekday-range expression matches no preset. Snapping it to "daily"
    // would quietly turn a weekdays-only job into a seven-day one.
    const reopened = scheduleFormFromConfig({
      schedule_type: 'cron',
      cron_expression: '0 9 * * 1-5',
    })
    expect(reopened.preset).toBe('cron')
    expect(reopened.expression).toBe('0 9 * * 1-5')
    expect(scheduleConfigFromForm(reopened).cron_expression).toBe('0 9 * * 1-5')
  })
})

describe('schedule validation', () => {
  it('requires a schedule type', () => {
    expect(validateTrigger('schedule', {})).toMatch(/how often/i)
  })

  it('rejects an empty or malformed cron expression', () => {
    expect(
      validateTrigger('schedule', { schedule_type: 'cron', cron_expression: '' })
    ).toBeTruthy()
    expect(
      validateTrigger('schedule', {
        schedule_type: 'cron',
        cron_expression: 'not a cron',
      })
    ).toBeTruthy()
  })

  it('rejects a non-positive or fractional interval', () => {
    expect(
      validateTrigger('schedule', { schedule_type: 'interval', interval_seconds: 0 })
    ).toBeTruthy()
    expect(
      validateTrigger('schedule', {
        schedule_type: 'interval',
        interval_seconds: 1.5,
      })
    ).toBeTruthy()
  })

  it('rejects an unparseable one-time date', () => {
    expect(
      validateTrigger('schedule', { schedule_type: 'one_time', scheduled_at: '' })
    ).toBeTruthy()
    expect(
      validateTrigger('schedule', {
        schedule_type: 'one_time',
        scheduled_at: 'tomorrow',
      })
    ).toBeTruthy()
    expect(
      validateTrigger('schedule', {
        schedule_type: 'one_time',
        scheduled_at: '2026-09-01T14:30',
      })
    ).toBeNull()
  })
})

describe('integration event validation', () => {
  it('requires an app the backend recognises', () => {
    expect(
      validateTrigger('integration_event', {
        integration_type: 'notion',
        event_type: 'page.created',
      })
    ).toBeTruthy()

    for (const integration of INTEGRATION_TYPES) {
      expect(
        validateTrigger('integration_event', {
          integration_type: integration.value,
          event_type: 'thing.happened',
        })
      ).toBeNull()
    }
  })

  it('requires a non-blank event name', () => {
    expect(
      validateTrigger('integration_event', {
        integration_type: 'stripe',
        event_type: '   ',
      })
    ).toBeTruthy()
  })
})

describe('webhook validation', () => {
  it('accepts a config with no key, which the server generates', () => {
    expect(validateTrigger('webhook', {})).toBeNull()
  })

  it('rejects a key shorter than the server minimum', () => {
    expect(validateTrigger('webhook', { webhook_key: 'short' })).toBeTruthy()
    expect(validateTrigger('webhook', { webhook_key: 'k'.repeat(32) })).toBeNull()
  })
})

describe('summaries', () => {
  it('describes each schedule shape in plain English', () => {
    expect(
      describeTrigger('schedule', {
        schedule_type: 'cron',
        cron_expression: '0 9 * * *',
        timezone: 'UTC',
      })
    ).toBe('Every day at 09:00 UTC')

    expect(
      describeTrigger('schedule', {
        schedule_type: 'cron',
        cron_expression: '30 17 * * 5',
        timezone: 'Asia/Karachi',
      })
    ).toBe('Every Friday at 17:30 Asia/Karachi')

    expect(
      describeTrigger('schedule', {
        schedule_type: 'interval',
        interval_seconds: 3600,
      })
    ).toBe('Every hour')

    expect(
      describeTrigger('schedule', {
        schedule_type: 'interval',
        interval_seconds: 900,
      })
    ).toBe('Every 15 minutes')
  })

  it('falls back to the raw expression for a custom cron', () => {
    expect(
      describeTrigger('schedule', {
        schedule_type: 'cron',
        cron_expression: '0 9 * * 1-5',
      })
    ).toBe('Cron: 0 9 * * 1-5 UTC')
  })

  it('says when a trigger is not configured yet', () => {
    expect(describeTrigger('schedule', {})).toBe('No schedule set')
    expect(describeTrigger('integration_event', {})).toBe('No app selected')
  })

  it('counts call filters', () => {
    expect(describeTrigger('call_completed', { filters: {} })).toBe(
      'After any call ends'
    )
    expect(
      describeTrigger('call_completed', { filters: { agent_id: 'a1' } })
    ).toBe('After a call ends (1 filter)')
  })
})
