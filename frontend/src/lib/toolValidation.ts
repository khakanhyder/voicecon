/**
 * What a tool needs before the builder will save it.
 *
 * Mirrors `backend/app/services/tools/validation.py`, which is the real gate —
 * this copy exists so the form can point at the field while the user is still
 * looking at it, instead of saving a Transfer Call with no destination that
 * only fails on a live call. Keep the two in step.
 *
 * Errors are keyed by the config field they belong to (`destination`, `url`,
 * …), plus `name`, `description`, and `param.<index>.<field>` for the
 * parameter builder, so each message can sit under its own input.
 */

export interface ToolParameterInput {
  name: string
  type: string
  description: string
  required: boolean
  enum?: string[]
}

export type ToolErrors = Record<string, string>

export const RETIRED_TOOL_TYPES = ['google_sheets', 'google_calendar', 'gohighlevel']

const MIN_TIMEOUT = 1
const MAX_TIMEOUT = 120

/** A leading +, then 7–15 digits — the carrier dials it as E.164. */
const PHONE = /^\+[\d\s().-]+$/
const SIP_URI = /^sips?:[^\s@]+@[^\s@]+$|^sips?:[^\s@]+\.[^\s@]+$/i
/** A value filled in during the call, such as `{{caller_number}}`. */
const TEMPLATE = /^\{\{\s*[A-Za-z_][\w.]*\s*\}\}$/
const DTMF = /^[0-9A-Da-d*#wW]+$/
const HEADER_NAME = /^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/
const PARAM_NAME = /^[A-Za-z_][A-Za-z0-9_]*$/

const HTTP_METHODS: Record<string, string[]> = {
  api_request: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
  custom_tool: ['GET', 'POST', 'PUT', 'PATCH'],
}

export function isToolPhoneNumber(value: string): boolean {
  const digits = value.replace(/\D/g, '')
  return PHONE.test(value) && digits.length >= 7 && digits.length <= 15
}

/** A full http(s) URL with a real host — `https://api` is a typo, not a server. */
export function isHttpUrl(value: string): boolean {
  if (/\s/.test(value)) return false
  try {
    const url = new URL(value)
    return (url.protocol === 'http:' || url.protocol === 'https:') && /[.:]/.test(url.hostname)
  } catch {
    return false
  }
}

function jsonObjectError(raw: string | undefined, label: string, headers = false): string | null {
  const text = (raw ?? '').trim()
  if (!text) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return `${label} must be valid JSON, like {"name": "value"}.`
  }
  if (parsed === null) return null
  if (typeof parsed !== 'object' || Array.isArray(parsed)) {
    return `${label} must be a JSON object, like {"name": "value"}.`
  }
  if (headers) {
    const bad = Object.entries(parsed as Record<string, unknown>).find(([, v]) => v !== null && typeof v === 'object')
    if (bad) return `${label}: "${bad[0]}" must be a single value, not an object or list.`
  }
  return null
}

export function validateTool(input: {
  toolType: string
  name: string
  description: string
  config: Record<string, string | undefined>
  params: ToolParameterInput[]
}): ToolErrors {
  const { toolType, config } = input
  const errors: ToolErrors = {}
  const text = (key: string) => (config[key] ?? '').trim()
  const require = (key: string, label: string) => {
    const value = text(key)
    if (!value) errors[key] = `${label} is required.`
    return value
  }
  const url = (key: string, label: string, httpsOnly = false) => {
    const value = require(key, label)
    if (!value) return
    if (!isHttpUrl(value)) errors[key] = `${label} must be a full URL starting with http:// or https://.`
    else if (httpsOnly && !value.toLowerCase().startsWith('https://')) errors[key] = `${label} must start with https://.`
  }
  const timeout = () => {
    const value = text('timeout')
    if (!value) return
    const seconds = Number(value)
    if (!Number.isFinite(seconds)) errors.timeout = 'Timeout must be a number of seconds.'
    else if (seconds < MIN_TIMEOUT || seconds > MAX_TIMEOUT) errors.timeout = `Timeout must be between ${MIN_TIMEOUT} and ${MAX_TIMEOUT} seconds.`
  }
  const method = (allowed: string[]) => {
    const value = text('method')
    if (value && !allowed.includes(value.toUpperCase())) errors.method = `Method must be one of ${allowed.join(', ')}.`
  }
  const json = (key: string, label: string, headers = false) => {
    const problem = jsonObjectError(config[key], label, headers)
    if (problem) errors[key] = problem
  }

  const name = input.name.trim()
  if (!name) errors.name = 'Tool name is required.'
  else if (name.length > 255) errors.name = 'Tool name cannot be longer than 255 characters.'

  if (!input.description.trim()) errors.description = 'Description is required — it tells the AI when to use this tool.'

  if (RETIRED_TOOL_TYPES.includes(toolType)) {
    errors.tool_type = 'This tool type is no longer supported. Create a Connected Integration tool instead.'
    return errors
  }

  switch (toolType) {
    case 'workflow':
      require('workflow_id', 'Workflow')
      break

    case 'connected_integration':
    case 'integration':
      require('connection_id', 'Connected integration')
      if (text('connection_id')) require('action', 'Action')
      break

    case 'transfer_call': {
      const destination = require('destination', 'Transfer destination')
      if (destination && !(isToolPhoneNumber(destination) || SIP_URI.test(destination) || TEMPLATE.test(destination))) {
        errors.destination = 'Enter a phone number with country code (e.g. +15551234567) or a SIP URI (e.g. sip:agent@example.com).'
      }
      break
    }

    case 'leave_voicemail':
      require('message', 'Voicemail message')
      break

    case 'send_sms': {
      const to = require('to', 'Recipient number')
      if (to && !(isToolPhoneNumber(to) || TEMPLATE.test(to))) {
        errors.to = 'Enter a phone number with country code (e.g. +15551234567) or {{caller_number}}.'
      }
      require('message', 'Message template')
      break
    }

    case 'dtmf': {
      const digits = require('digits', 'DTMF digits')
      if (digits && !DTMF.test(digits)) errors.digits = 'Use only 0-9, *, #, A-D, and w for a pause.'
      else if (digits.length > 64) errors.digits = 'DTMF digits cannot be longer than 64 characters.'
      break
    }

    case 'sip_request': {
      const sip = require('sip_uri', 'SIP URI')
      if (sip && !SIP_URI.test(sip)) errors.sip_uri = 'Enter a SIP URI such as sip:user@example.com.'
      method(['INVITE', 'BYE', 'REFER'])
      break
    }

    case 'handoff':
      require('destination', 'Destination queue / agent')
      break

    case 'query_knowledge_base':
      require('knowledge_base_id', 'Knowledge base')
      break

    case 'api_request':
      url('url', 'Server URL')
      method(HTTP_METHODS.api_request)
      timeout()
      json('headers', 'Headers', true)
      json('body', 'Body template')
      break

    case 'mcp': {
      url('server_url', 'MCP server URL')
      const toolName = require('tool_name', 'Tool name')
      if (toolName && /\s/.test(toolName)) errors.tool_name = 'Tool name cannot contain spaces.'
      timeout()
      break
    }

    case 'slack':
      url('webhook_url', 'Slack webhook URL', true)
      require('message', 'Message template')
      break

    case 'custom_tool': {
      url('url', 'Server URL')
      method(HTTP_METHODS.custom_tool)
      timeout()
      const auth = (text('auth_type') || 'none').toLowerCase()
      if (auth === 'bearer') require('auth_token', 'Bearer token')
      if (auth === 'basic') {
        require('auth_user', 'Username')
        require('auth_pass', 'Password')
      }
      if (auth === 'custom_header') {
        const header = require('auth_header', 'Header name')
        if (header && !HEADER_NAME.test(header)) errors.auth_header = 'Header name cannot contain spaces or special characters.'
        require('auth_value', 'Header value')
      }
      json('headers', 'Extra headers', true)
      break
    }
  }

  // Parameters become JSON keys the model fills in and `{{name}}` references
  // in templates, so a blank or duplicate name silently drops a value.
  const seen = new Map<string, number>()
  input.params.forEach((p, i) => {
    const paramName = p.name.trim()
    if (!paramName) {
      errors[`param.${i}.name`] = 'Parameter name is required.'
    } else if (!PARAM_NAME.test(paramName)) {
      errors[`param.${i}.name`] = 'Use letters, numbers and underscores only, not starting with a number.'
    } else if (seen.has(paramName)) {
      errors[`param.${i}.name`] = `"${paramName}" is already used by parameter ${seen.get(paramName)! + 1}.`
    } else {
      seen.set(paramName, i)
    }
  })

  return errors
}
