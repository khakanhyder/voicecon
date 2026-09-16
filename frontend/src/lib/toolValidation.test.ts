/**
 * The tool builder's save gate. Mirrors backend/tests/unit/test_tool_validation.py;
 * the cases that matter most are the ones that used to save and then fail on a
 * live call.
 */
import { describe, expect, it } from 'vitest'
import { isHttpUrl, isToolPhoneNumber, validateTool, type ToolParameterInput } from './toolValidation'

const base = { name: 'My tool', description: 'Use it when asked.', params: [] as ToolParameterInput[] }
const check = (toolType: string, config: Record<string, string> = {}, extra: Partial<typeof base> = {}) =>
  validateTool({ ...base, ...extra, toolType, config })

describe('validateTool', () => {
  it('blocks the reported case: a transfer with no destination', () => {
    expect(check('transfer_call')).toHaveProperty('destination')
  })

  it('requires a name and a description for every type', () => {
    const errors = check('hang_up', {}, { name: '  ', description: '' })
    expect(Object.keys(errors).sort()).toEqual(['description', 'name'])
  })

  it.each([
    ['workflow', 'workflow_id'],
    ['connected_integration', 'connection_id'],
    ['leave_voicemail', 'message'],
    ['send_sms', 'to'],
    ['dtmf', 'digits'],
    ['sip_request', 'sip_uri'],
    ['handoff', 'destination'],
    ['query_knowledge_base', 'knowledge_base_id'],
    ['api_request', 'url'],
    ['mcp', 'tool_name'],
    ['slack', 'webhook_url'],
    ['custom_tool', 'url'],
  ])('%s requires %s', (type, field) => {
    expect(check(type)).toHaveProperty(field)
  })

  it('accepts a complete transfer call', () => {
    expect(check('transfer_call', { destination: '+15551234567' })).toEqual({})
  })

  it('rejects malformed JSON headers but keeps a cleared box valid', () => {
    expect(check('api_request', { url: 'https://api.example.com', headers: '{bad' })).toHaveProperty('headers')
    expect(check('api_request', { url: 'https://api.example.com', headers: '' })).toEqual({})
  })

  it('requires the credentials of the chosen auth mode', () => {
    expect(check('custom_tool', { url: 'https://x.example.com', auth_type: 'bearer' })).toHaveProperty('auth_token')
    expect(check('custom_tool', { url: 'https://x.example.com', auth_type: 'none' })).toEqual({})
  })

  it('flags blank, invalid and duplicate parameter names by index', () => {
    const p = (name: string): ToolParameterInput => ({ name, type: 'string', description: '', required: false })
    const errors = check('hang_up', {}, { params: [p(''), p('first name'), p('email'), p('email')] })
    expect(Object.keys(errors).sort()).toEqual(['param.0.name', 'param.1.name', 'param.3.name'])
  })

  it('refuses retired types', () => {
    expect(check('google_sheets')).toHaveProperty('tool_type')
  })
})

describe('field helpers', () => {
  it.each(['+15551234567', '+44 20 7946 0958'])('%s is a dialable number', v => expect(isToolPhoneNumber(v)).toBe(true))
  it.each(['5551234567', '+12', 'call me'])('%s is not', v => expect(isToolPhoneNumber(v)).toBe(false))
  it.each(['https://api', 'api.example.com', 'ftp://x.com'])('%s is not a usable URL', v => expect(isHttpUrl(v)).toBe(false))
})
