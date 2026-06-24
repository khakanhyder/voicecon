'use client'

import { useState, useEffect } from 'react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  Wrench, Plus, Search, Phone, PhoneForwarded, PhoneOff,
  MessageSquare, Voicemail, Hash, ArrowLeftRight, Bot,
  Database, Zap, Globe, Sheet, Calendar, Trash2,
  X, ChevronRight, ToggleLeft, ToggleRight, FlaskConical,
  Loader2, CheckCircle2, XCircle, Settings2, Pencil,
  Link2, Puzzle, Users,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ToolParameter {
  name: string
  type: 'string' | 'number' | 'boolean' | 'object' | 'array'
  description: string
  required: boolean
  enum?: string[]
}

interface Tool {
  id: string
  name: string
  description: string | null
  tool_type: string
  category: string
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

interface ActiveIntegration {
  id: string
  slug: string
  name: string
  status: string
}

interface AvailableAction {
  action: string
  label: string
  description: string
  parameters: {
    type: string
    properties: Record<string, { type: string; description: string }>
    required?: string[]
  }
}

interface AvailableConnection {
  connection_id: string
  connector_slug: string
  connector_name: string
  display_name: string
  action_count: number
}

// ── Tool type metadata ─────────────────────────────────────────────────────────

const TOOL_TYPES = {
  phone_call: {
    label: 'Phone Call Tools',
    icon: Phone,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    tools: [
      { type: 'transfer_call',         label: 'Transfer Call',        icon: PhoneForwarded,  description: 'Transfer the call to another number or extension' },
      { type: 'hang_up',               label: 'Hang Up',              icon: PhoneOff,        description: 'End the current call gracefully' },
      { type: 'leave_voicemail',        label: 'Leave Voicemail',      icon: Voicemail,       description: 'Leave a voicemail message for the caller' },
      { type: 'dtmf',                  label: 'DTMF',                 icon: Hash,            description: 'Send DTMF (touch-tone) signals into the call' },
      { type: 'send_sms',              label: 'Send Text',            icon: MessageSquare,   description: 'Send an SMS to the caller or any number' },
      { type: 'sip_request',           label: 'SIP Request',          icon: ArrowLeftRight,  description: 'Make a custom SIP protocol request' },
    ],
  },
  assistant: {
    label: 'Assistant Tools',
    icon: Bot,
    color: 'text-violet-600',
    bg: 'bg-violet-50',
    border: 'border-violet-200',
    tools: [
      { type: 'handoff',               label: 'Handoff',              icon: Users,           description: 'Hand off conversation to a human agent or queue' },
      { type: 'query_knowledge_base',  label: 'Query Knowledge Base', icon: Database,        description: 'Query a knowledge base for specific information' },
    ],
  },
  integration: {
    label: 'Integration Tools',
    icon: Zap,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    tools: [
      { type: 'connected_integration',  label: 'Connected Integration', icon: Link2,          description: 'Use a connected integration (HubSpot, Salesforce, Google Calendar, Slack, etc.) as an AI-callable tool' },
      { type: 'api_request',           label: 'API Request',          icon: Globe,           description: 'Make a custom HTTP API request to any server' },
      { type: 'mcp',                   label: 'MCP',                  icon: Settings2,       description: 'Call a Model Context Protocol server tool' },
      { type: 'slack',                 label: 'Slack',                icon: MessageSquare,   description: 'Send a message to a Slack channel via webhook' },
      { type: 'google_sheets',         label: 'Google Sheets',        icon: Sheet,           description: 'Append or update rows in a Google Sheet' },
      { type: 'google_calendar',       label: 'Google Calendar',      icon: Calendar,        description: 'Create or retrieve Google Calendar events' },
      { type: 'gohighlevel',           label: 'GoHighLevel',          icon: Users,           description: 'Create contacts, update pipelines, and trigger workflows in GoHighLevel CRM' },
      { type: 'custom_tool',           label: 'Custom Tool',          icon: Puzzle,          description: 'Fully custom webhook tool — define your own server URL and parameters' },
    ],
  },
}

type CatKey = keyof typeof TOOL_TYPES
const ALL_TOOL_TYPES = Object.values(TOOL_TYPES).flatMap(c => c.tools)

function getTypeMeta(toolType: string) { return ALL_TOOL_TYPES.find(t => t.type === toolType) }
function getCategoryMeta(cat: string) { return TOOL_TYPES[cat as CatKey] }

// Integration slugs that have AI-callable actions (surfaces quick-create button in banner)
const INTEGRATION_TOOL_SLUGS: Record<string, { label: string; icon: string; toolType: string }> = {
  slack:            { label: 'Slack',           icon: '💬', toolType: 'connected_integration' },
  hubspot:          { label: 'HubSpot',         icon: '🟠', toolType: 'connected_integration' },
  salesforce:       { label: 'Salesforce',      icon: '☁️',  toolType: 'connected_integration' },
  google_calendar:  { label: 'Google Calendar', icon: '📅', toolType: 'connected_integration' },
  sendgrid:         { label: 'SendGrid',        icon: '📧', toolType: 'connected_integration' },
  'google-sheets':  { label: 'Google Sheets',   icon: '📊', toolType: 'connected_integration' },
  'google-calendar':{ label: 'Google Calendar', icon: '📅', toolType: 'connected_integration' },
  gohighlevel:      { label: 'GoHighLevel',     icon: '🏢', toolType: 'connected_integration' },
}

// ── Shared UI primitives ──────────────────────────────────────────────────────

function Field({ label, required, hint, children }: {
  label: string; required?: boolean; hint?: string; children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  )
}
function TI({ value, onChange, placeholder, mono }: { value:string; onChange:(v:string)=>void; placeholder?:string; mono?:boolean }) {
  return <input type="text" value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} className={`w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 ${mono?'font-mono':''}`} />
}
function TA({ value, onChange, placeholder, rows=3, mono }: { value:string; onChange:(v:string)=>void; placeholder?:string; rows?:number; mono?:boolean }) {
  return <textarea value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} rows={rows} className={`w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 resize-none ${mono?'font-mono':''}`} />
}
function SI({ value, onChange, children }: { value:string; onChange:(v:string)=>void; children:React.ReactNode }) {
  return <select value={value} onChange={e=>onChange(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 bg-white">{children}</select>
}

// ── Parameter builder ──────────────────────────────────────────────────────────

function ParameterBuilder({ params, onChange }: { params: ToolParameter[]; onChange: (p: ToolParameter[]) => void }) {
  const add = () => onChange([...params, { name:'', type:'string', description:'', required:false }])
  const upd = (i:number, u: Partial<ToolParameter>) => { const n=[...params]; n[i]={...n[i],...u}; onChange(n) }
  const del = (i:number) => onChange(params.filter((_,idx)=>idx!==i))

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-slate-700">Parameters</label>
        <button type="button" onClick={add} className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"><Plus className="h-3.5 w-3.5"/>Add parameter</button>
      </div>
      {params.length === 0 ? (
        <div onClick={add} className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 py-6 cursor-pointer hover:border-blue-300 hover:bg-blue-50 transition-colors">
          <Plus className="h-5 w-5 text-slate-400 mb-1"/>
          <p className="text-xs text-slate-500">Define what data the AI should collect</p>
        </div>
      ) : (
        <div className="space-y-3">
          {params.map((p,i) => (
            <div key={i} className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Parameter {i+1}</span>
                <button type="button" onClick={()=>del(i)} className="rounded p-0.5 text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"><X className="h-3.5 w-3.5"/></button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Name" required><TI value={p.name} onChange={v=>upd(i,{name:v})} placeholder="customer_name" mono/></Field>
                <Field label="Type">
                  <SI value={p.type} onChange={v=>upd(i,{type:v as ToolParameter['type']})}>
                    <option value="string">string</option><option value="number">number</option>
                    <option value="boolean">boolean</option><option value="object">object</option><option value="array">array</option>
                  </SI>
                </Field>
              </div>
              <Field label="Description" hint="Helps the AI understand what value to collect">
                <TI value={p.description} onChange={v=>upd(i,{description:v})} placeholder="The customer's full name"/>
              </Field>
              {p.type === 'string' && (
                <Field label="Allowed values (optional)" hint="Comma-separated">
                  <TI value={p.enum?.join(',')||''} onChange={v=>upd(i,{enum:v?v.split(',').map(s=>s.trim()):undefined})} placeholder="yes, no, maybe"/>
                </Field>
              )}
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" checked={p.required} onChange={e=>upd(i,{required:e.target.checked})} className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"/>
                <span className="text-sm text-slate-600">Required</span>
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Connected integration config ──────────────────────────────────────────────

function ConnectedIntegrationConfig({ config, onCfg, onParams }: {
  config: Record<string, string>
  onCfg: (k: string, v: string) => void
  onParams: (p: ToolParameter[]) => void
}) {
  const [connections, setConnections] = useState<AvailableConnection[]>([])
  const [actions, setActions] = useState<AvailableAction[]>([])
  const [loadingConns, setLoadingConns] = useState(true)
  const [loadingActions, setLoadingActions] = useState(false)

  useEffect(() => {
    apiClient.get<{ connections: AvailableConnection[] }>(API_ENDPOINTS.INTEGRATIONS_AVAILABLE_FOR_TOOLS)
      .then(res => setConnections(res.data.connections || []))
      .catch(() => {})
      .finally(() => setLoadingConns(false))
  }, [])

  useEffect(() => {
    if (!config.connection_id) { setActions([]); return }
    setLoadingActions(true)
    apiClient.get<{ actions: AvailableAction[] }>(API_ENDPOINTS.INTEGRATION_CONNECTION_ACTIONS(config.connection_id))
      .then(res => setActions(res.data.actions || []))
      .catch(() => setActions([]))
      .finally(() => setLoadingActions(false))
  }, [config.connection_id])

  const selectedAction = actions.find(a => a.action === config.action)

  const handleConnectionChange = (connectionId: string) => {
    const conn = connections.find(c => c.connection_id === connectionId)
    onCfg('connection_id', connectionId)
    onCfg('connector_slug', conn?.connector_slug || '')
    onCfg('action', '')
    onParams([])
  }

  const handleActionChange = (action: string) => {
    onCfg('action', action)
    const actionDef = actions.find(a => a.action === action)
    if (actionDef?.parameters?.properties) {
      const { properties, required = [] } = actionDef.parameters
      const newParams: ToolParameter[] = Object.entries(properties).map(([name, def]) => ({
        name,
        type: (def.type as ToolParameter['type']) || 'string',
        description: def.description || '',
        required: required.includes(name),
      }))
      onParams(newParams)
    }
  }

  if (loadingConns) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400 py-4">
        <Loader2 className="h-4 w-4 animate-spin"/>Loading connected integrations…
      </div>
    )
  }

  if (connections.length === 0) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        <strong>No connected integrations found.</strong>
        <p className="mt-1 text-xs">Go to <span className="font-medium">Integrations</span> in the sidebar to connect HubSpot, Salesforce, Google Calendar, Slack, or SendGrid first.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800">
        <strong>AI Integration Tool</strong> — The AI will call this action on your connected integration during a live voice call whenever it decides to use this tool.
      </div>

      <Field label="Connected Integration" required hint="Select which connected integration to use">
        <SI value={config.connection_id || ''} onChange={handleConnectionChange}>
          <option value="">— Select integration —</option>
          {connections.map(c => (
            <option key={c.connection_id} value={c.connection_id}>
              {c.display_name || c.connector_name} ({c.action_count} action{c.action_count !== 1 ? 's' : ''})
            </option>
          ))}
        </SI>
      </Field>

      {config.connection_id && (
        loadingActions ? (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin"/>Loading actions…
          </div>
        ) : (
          <Field label="Action" required hint="What should the AI do with this integration?">
            <SI value={config.action || ''} onChange={handleActionChange}>
              <option value="">— Select action —</option>
              {actions.map(a => (
                <option key={a.action} value={a.action}>{a.label}</option>
              ))}
            </SI>
          </Field>
        )
      )}

      {selectedAction && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          <p className="font-medium text-slate-700 mb-1">{selectedAction.label}</p>
          <p>{selectedAction.description}</p>
        </div>
      )}

      {selectedAction && Object.keys(selectedAction.parameters?.properties || {}).length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <label className="text-sm font-medium text-slate-700">Parameters</label>
            <span className="text-xs text-slate-400 bg-slate-100 rounded-full px-2 py-0.5">auto-populated from action schema</span>
          </div>
          <div className="space-y-2">
            {Object.entries(selectedAction.parameters.properties).map(([name, def]) => {
              const isRequired = (selectedAction.parameters.required || []).includes(name)
              return (
                <div key={name} className="flex items-start rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs">
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-semibold text-slate-800">{name}</span>
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-500">{def.type}</span>
                      {isRequired && <span className="rounded bg-red-50 px-1.5 py-0.5 text-red-600 font-medium">required</span>}
                    </div>
                    <p className="text-slate-500 mt-0.5">{def.description}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Type-specific config panels ────────────────────────────────────────────────

function ToolConfigFields({ toolType, config, params, onCfg, onParams }: {
  toolType: string
  config: Record<string,string>
  params: ToolParameter[]
  onCfg: (k:string,v:string)=>void
  onParams: (p:ToolParameter[])=>void
}) {
  const s = (k:string) => (v:string) => onCfg(k,v)

  switch (toolType) {
    case 'connected_integration':
      return <ConnectedIntegrationConfig config={config} onCfg={onCfg} onParams={onParams}/>

    case 'transfer_call':
      return <div className="space-y-4">
        <Field label="Transfer Destination" required hint="Phone number or SIP URI"><TI value={config.destination||''} onChange={s('destination')} placeholder="+15551234567"/></Field>
        <Field label="Announcement message" hint="Spoken before transferring"><TI value={config.message||''} onChange={s('message')} placeholder="Please hold while I connect you…"/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'leave_voicemail':
      return <div className="space-y-4">
        <Field label="Voicemail Message" required><TA value={config.message||''} onChange={s('message')} placeholder="Hello, this is an automated message…" rows={3}/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'send_sms':
      return <div className="space-y-4">
        <Field label="Recipient Number" required><TI value={config.to||''} onChange={s('to')} placeholder="+15551234567 or {{caller_number}}"/></Field>
        <Field label="Message Template" required hint="Use {{variable}} for dynamic values"><TA value={config.message||''} onChange={s('message')} placeholder="Hi {{name}}, your appointment is confirmed for {{date}}." rows={3}/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'dtmf':
      return <div className="space-y-4">
        <Field label="DTMF Digits" required hint="Digits to press, e.g. 1 to select option 1"><TI value={config.digits||''} onChange={s('digits')} placeholder="1234#" mono/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'sip_request':
      return <div className="space-y-4">
        <Field label="SIP URI" required><TI value={config.sip_uri||''} onChange={s('sip_uri')} placeholder="sip:user@domain.com" mono/></Field>
        <Field label="Method"><SI value={config.method||'INVITE'} onChange={s('method')}><option>INVITE</option><option>BYE</option><option>REFER</option></SI></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'handoff':
      return <div className="space-y-4">
        <Field label="Destination Queue / Agent" required><TI value={config.destination||''} onChange={s('destination')} placeholder="support-queue"/></Field>
        <Field label="Handoff Message"><TI value={config.message||''} onChange={s('message')} placeholder="Transferring you to a specialist…"/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'query_knowledge_base':
      return <div className="space-y-4">
        <Field label="Knowledge Base ID" required><TI value={config.knowledge_base_id||''} onChange={s('knowledge_base_id')} placeholder="kb_xxxxxxxx" mono/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'api_request':
      return <div className="space-y-4">
        <div className="grid grid-cols-3 gap-2">
          <div className="col-span-2"><Field label="Server URL" required><TI value={config.url||''} onChange={s('url')} placeholder="https://api.example.com/endpoint" mono/></Field></div>
          <Field label="Method"><SI value={config.method||'POST'} onChange={s('method')}><option>GET</option><option>POST</option><option>PUT</option><option>PATCH</option><option>DELETE</option></SI></Field>
        </div>
        <Field label="Timeout (seconds)"><TI value={config.timeout||'20'} onChange={s('timeout')} placeholder="20"/></Field>
        <Field label="Headers (JSON)" hint="Authorization, Content-Type, etc.">
          <TA value={config.headers||'{\n  "Content-Type": "application/json"\n}'} onChange={s('headers')} placeholder={'{"Authorization":"Bearer TOKEN"}'} rows={4} mono/>
        </Field>
        <Field label="Body Template (JSON)" hint="Use {{param_name}} to insert AI-collected values">
          <TA value={config.body||'{}'} onChange={s('body')} placeholder={'{\n  "name": "{{customer_name}}",\n  "email": "{{email}}"\n}'} rows={5} mono/>
        </Field>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
          <strong>Tip:</strong> Define parameters below to tell the AI what data to collect, then reference them as <code className="font-mono bg-blue-100 px-1 rounded">{'{{param_name}}'}</code> in the body template.
        </div>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'mcp':
      return <div className="space-y-4">
        <Field label="MCP Server URL" required><TI value={config.server_url||''} onChange={s('server_url')} placeholder="https://mcp.example.com" mono/></Field>
        <Field label="Tool Name" required hint="The MCP tool function to invoke"><TI value={config.tool_name||''} onChange={s('tool_name')} placeholder="search_crm" mono/></Field>
        <Field label="Timeout (seconds)"><TI value={config.timeout||'20'} onChange={s('timeout')} placeholder="20"/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'slack':
      return <div className="space-y-4">
        <Field label="Slack Webhook URL" required hint="Get from Slack App → Incoming Webhooks"><TI value={config.webhook_url||''} onChange={s('webhook_url')} placeholder="https://hooks.slack.com/services/T…/B…/…" mono/></Field>
        <Field label="Message Template" required hint="Use {{variable}} for dynamic values"><TA value={config.message||''} onChange={s('message')} placeholder="New lead from {{caller_name}}: {{summary}}" rows={3}/></Field>
        <Field label="Channel (optional)" hint="Override the default channel, e.g. #leads"><TI value={config.channel||''} onChange={s('channel')} placeholder="#sales"/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'google_sheets':
      return <div className="space-y-4">
        <Field label="Spreadsheet ID" required hint="Found in the Google Sheets URL"><TI value={config.spreadsheet_id||''} onChange={s('spreadsheet_id')} placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms" mono/></Field>
        <Field label="Sheet Name"><TI value={config.sheet_name||''} onChange={s('sheet_name')} placeholder="Sheet1"/></Field>
        <Field label="Row Template (JSON array)" hint="Values to append as a new row">
          <TA value={config.row||''} onChange={s('row')} placeholder={'["{{caller_name}}", "{{phone}}", "{{date}}"]'} rows={3} mono/>
        </Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'google_calendar':
      return <div className="space-y-4">
        <Field label="Calendar ID"><TI value={config.calendar_id||''} onChange={s('calendar_id')} placeholder="primary" mono/></Field>
        <Field label="Event Title Template"><TI value={config.title||''} onChange={s('title')} placeholder="Appointment with {{customer_name}}"/></Field>
        <Field label="Duration (minutes)"><TI value={config.duration||'30'} onChange={s('duration')} placeholder="30"/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'gohighlevel':
      return <div className="space-y-4">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
          <strong>GoHighLevel CRM</strong> — Create contacts, update opportunities, and trigger automations from voice calls.
        </div>
        <Field label="API Key" required hint="Get from GHL Settings → API Keys"><TI value={config.api_key||''} onChange={s('api_key')} placeholder="eyJhbGciOi…" mono/></Field>
        <Field label="Location ID" required hint="Found in GHL Settings → Business Profile"><TI value={config.location_id||''} onChange={s('location_id')} placeholder="ve9EPM428h8vShlRW1KT" mono/></Field>
        <Field label="Action">
          <SI value={config.action||'create_contact'} onChange={s('action')}>
            <option value="create_contact">Create Contact</option>
            <option value="update_contact">Update Contact</option>
            <option value="create_opportunity">Create Opportunity</option>
            <option value="add_note">Add Note to Contact</option>
            <option value="trigger_workflow">Trigger Workflow</option>
          </SI>
        </Field>
        <Field label="Pipeline ID (for opportunities)" hint="Optional — required for Create Opportunity action"><TI value={config.pipeline_id||''} onChange={s('pipeline_id')} placeholder="YlWd2wuCAZQVi18AI…" mono/></Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'custom_tool':
      return <div className="space-y-4">
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs text-slate-600">
          <strong>Custom Tool</strong> — Define your own server webhook. The AI will call this URL with the parameters you define below whenever it invokes this tool.
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="col-span-2"><Field label="Server URL" required><TI value={config.url||''} onChange={s('url')} placeholder="https://your-server.com/tool-handler" mono/></Field></div>
          <Field label="Method"><SI value={config.method||'POST'} onChange={s('method')}><option>POST</option><option>GET</option><option>PUT</option><option>PATCH</option></SI></Field>
        </div>
        <Field label="Timeout (seconds)"><TI value={config.timeout||'20'} onChange={s('timeout')} placeholder="20"/></Field>
        <Field label="Authentication">
          <SI value={config.auth_type||'none'} onChange={s('auth_type')}>
            <option value="none">No authentication</option>
            <option value="bearer">Bearer token</option>
            <option value="basic">Basic auth</option>
            <option value="custom_header">Custom header</option>
          </SI>
        </Field>
        {config.auth_type === 'bearer' && (
          <Field label="Bearer Token"><TI value={config.auth_token||''} onChange={s('auth_token')} placeholder="your-secret-token" mono/></Field>
        )}
        {config.auth_type === 'basic' && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Username"><TI value={config.auth_user||''} onChange={s('auth_user')} placeholder="user"/></Field>
            <Field label="Password"><TI value={config.auth_pass||''} onChange={s('auth_pass')} placeholder="pass"/></Field>
          </div>
        )}
        {config.auth_type === 'custom_header' && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Header name"><TI value={config.auth_header||''} onChange={s('auth_header')} placeholder="X-API-Key" mono/></Field>
            <Field label="Header value"><TI value={config.auth_value||''} onChange={s('auth_value')} placeholder="your-key" mono/></Field>
          </div>
        )}
        <Field label="Extra Headers (JSON)" hint="Optional additional headers">
          <TA value={config.headers||'{}'} onChange={s('headers')} placeholder='{"Content-Type": "application/json"}' rows={3} mono/>
        </Field>
        <ParameterBuilder params={params} onChange={onParams}/>
      </div>

    case 'hang_up':
      return <div className="space-y-4">
        <Field label="Farewell message" hint="Spoken before hanging up"><TI value={config.message||''} onChange={s('message')} placeholder="Thank you for calling. Goodbye!"/></Field>
      </div>

    default:
      return <p className="text-sm text-slate-400">No additional configuration for this tool type.</p>
  }
}

// ── Tool form (create + edit) ─────────────────────────────────────────────────

function ToolForm({ initial, initialType, onClose, onSaved }: { initial?: Tool; initialType?: string; onClose:()=>void; onSaved:(t:Tool)=>void }) {
  const isEdit = !!initial
  const [step, setStep] = useState<'pick_type'|'configure'>((isEdit||!!initialType)?'configure':'pick_type')
  const [selectedType, setSelectedType] = useState(initial?.tool_type||initialType||'')
  const [name, setName] = useState(initial?.name||'')
  const [description, setDescription] = useState(initial?.description||'')
  const [config, setConfig] = useState<Record<string,string>>(
    Object.fromEntries(Object.entries(initial?.config||{}).map(([k,v])=>[k,typeof v==='string'?v:JSON.stringify(v)]))
  )
  const [params, setParams] = useState<ToolParameter[]>(() => {
    if (initial?.config?.parameters) {
      try {
        const raw = initial.config.parameters as Record<string,unknown>
        return Object.entries((raw.properties as Record<string,unknown>)||{}).map(([pName,pDef])=>{
          const def = pDef as Record<string,unknown>
          return { name:pName, type:(def.type as ToolParameter['type'])||'string', description:(def.description as string)||'', required:((raw.required as string[])||[]).includes(pName), enum:def.enum as string[]|undefined }
        })
      } catch { return [] }
    }
    return []
  })
  const [saving, setSaving] = useState(false)

  const typeMeta = getTypeMeta(selectedType)
  const setCfg = (k:string,v:string) => setConfig(prev=>({...prev,[k]:v}))

  const buildPayload = () => {
    const paramSchema = params.length>0 ? {
      type:'object',
      properties: Object.fromEntries(params.map(p=>[p.name,{type:p.type,description:p.description,...(p.enum&&p.enum.length>0?{enum:p.enum}:{})}])),
      required: params.filter(p=>p.required).map(p=>p.name),
    } : undefined
    return { name:name.trim(), description:description.trim()||null, tool_type:selectedType, config:{...config,...(paramSchema?{parameters:paramSchema}:{})} }
  }

  const handleSave = async () => {
    if (!name.trim()) { toast.error('Name is required'); return }
    setSaving(true)
    try {
      const payload = buildPayload()
      const res: { data: Tool } = isEdit && initial
        ? await apiClient.patch<Tool>(API_ENDPOINTS.TOOL(initial.id), payload)
        : await apiClient.post<Tool>(API_ENDPOINTS.TOOLS, payload)
      toast.success(isEdit ? 'Tool updated' : 'Tool created')
      onSaved(res.data)
      onClose()
    } catch (err) { toast.error(getErrorMessage(err)) }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[92vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Wrench className="h-5 w-5 text-blue-600"/>
            <h2 className="text-lg font-semibold text-slate-900">
              {isEdit ? `Edit: ${initial!.name}` : step==='pick_type' ? 'Select Tool Type' : 'Configure Tool'}
            </h2>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"><X className="h-5 w-5"/></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {step === 'pick_type' ? (
            <div className="space-y-5">
              {Object.entries(TOOL_TYPES).map(([catKey,cat])=>{
                const CatIcon = cat.icon
                return (
                  <div key={catKey}>
                    <div className="flex items-center gap-2 mb-2.5">
                      <CatIcon className={`h-4 w-4 ${cat.color}`}/>
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{cat.label}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {cat.tools.map(t=>{
                        const TIcon = t.icon
                        return (
                          <button key={t.type} onClick={()=>{setSelectedType(t.type);setName(t.label);setStep('configure')}}
                            className="flex items-start gap-2.5 p-3 rounded-xl border-2 border-slate-200 text-left transition-all hover:border-blue-300 hover:bg-blue-50">
                            <div className={`mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg ${cat.bg} border ${cat.border}`}>
                              <TIcon className={`h-3.5 w-3.5 ${cat.color}`}/>
                            </div>
                            <div>
                              <p className="text-sm font-medium text-slate-800 leading-tight">{t.label}</p>
                              <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{t.description}</p>
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="space-y-4">
              {!isEdit && typeMeta && (
                <div className="flex items-center gap-2 text-sm">
                  <button onClick={()=>setStep('pick_type')} className="flex items-center gap-1 text-blue-600 hover:text-blue-700 font-medium">
                    <ChevronRight className="h-3.5 w-3.5 rotate-180"/>Back
                  </button>
                  <span className="text-slate-300">|</span>
                  <span className="text-slate-500">Type: <span className="font-medium text-slate-700">{typeMeta.label}</span></span>
                </div>
              )}
              <Field label="Tool Name" required><TI value={name} onChange={setName} placeholder="My Tool"/></Field>
              <Field label="Description" hint="Tells the AI when to use this tool">
                <TA value={description} onChange={setDescription} placeholder="Use this tool to book an appointment. Collect the customer's name and preferred time." rows={2}/>
              </Field>
              <div className="border-t border-slate-100"/>
              <ToolConfigFields toolType={selectedType} config={config} params={params} onCfg={setCfg} onParams={setParams}/>
            </div>
          )}
        </div>

        {step === 'configure' && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 flex-shrink-0">
            <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors">Cancel</button>
            <button onClick={handleSave} disabled={saving}
              className="flex items-center gap-2 rounded-lg gradient-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm disabled:opacity-50">
              {saving ? <Loader2 className="h-4 w-4 animate-spin"/> : isEdit ? <Pencil className="h-4 w-4"/> : <Plus className="h-4 w-4"/>}
              {isEdit ? 'Save Changes' : 'Create Tool'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tool card ──────────────────────────────────────────────────────────────────

function ToolCard({ tool, onEdit, onDelete, onToggle }: {
  tool: Tool; onEdit:(t:Tool)=>void; onDelete:(id:string)=>void; onToggle:(id:string,v:boolean)=>void
}) {
  const typeMeta = getTypeMeta(tool.tool_type)
  const catMeta  = getCategoryMeta(tool.category)
  const [testing,  setTesting]  = useState(false)
  const [testResult, setTestResult] = useState<{success:boolean;message:string}|null>(null)

  const Icon    = typeMeta?.icon || Wrench
  const CatIcon = catMeta?.icon  || Wrench

  const handleTest = async (e: React.MouseEvent) => {
    e.stopPropagation(); setTesting(true); setTestResult(null)
    try {
      const res = await apiClient.post<{success:boolean;message:string}>(API_ENDPOINTS.TOOL_TEST(tool.id), { parameters:{} })
      setTestResult({ success:res.data.success, message:res.data.message })
    } catch (err) { setTestResult({ success:false, message:getErrorMessage(err) }) }
    finally { setTesting(false) }
  }

  const c = tool.config as Record<string,string>
  const configPreview = c.url||c.destination||c.webhook_url||c.server_url||c.api_key?.slice(0,8)+'…'||null
  const paramCount = (() => { const p=(tool.config as any)?.parameters?.properties; return p?Object.keys(p).length:0 })()

  return (
    <div onClick={()=>onEdit(tool)} className="bg-white rounded-xl border border-slate-200 hover:border-blue-300 hover:shadow-md transition-all overflow-hidden cursor-pointer group">
      <div className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl ${catMeta?.bg||'bg-slate-50'} border ${catMeta?.border||'border-slate-200'}`}>
              <Icon className={`h-5 w-5 ${catMeta?.color||'text-slate-500'}`}/>
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 leading-tight group-hover:text-blue-600 transition-colors">{tool.name}</h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <CatIcon className={`h-3 w-3 ${catMeta?.color||'text-slate-400'}`}/>
                <span className="text-xs text-slate-400">{typeMeta?.label||tool.tool_type}</span>
                {paramCount>0 && <span className="text-xs text-slate-300">· {paramCount} param{paramCount!==1?'s':''}</span>}
              </div>
            </div>
          </div>
          <button onClick={e=>{e.stopPropagation();onToggle(tool.id,!tool.is_active)}} className="ml-2 flex-shrink-0" title={tool.is_active?'Deactivate':'Activate'}>
            {tool.is_active ? <ToggleRight className="h-6 w-6 text-blue-500"/> : <ToggleLeft className="h-6 w-6 text-slate-300"/>}
          </button>
        </div>
        {tool.description && <p className="text-xs text-slate-500 mb-2 line-clamp-2">{tool.description}</p>}
        {configPreview && <p className="text-xs text-slate-400 font-mono truncate">{configPreview}</p>}
        {testResult && (
          <div className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs mt-3 ${testResult.success?'bg-emerald-50 text-emerald-700':'bg-red-50 text-red-700'}`}>
            {testResult.success ? <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 mt-0.5"/> : <XCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5"/>}
            <span className="line-clamp-2">{testResult.message}</span>
          </div>
        )}
      </div>
      <div className="border-t border-slate-100 bg-slate-50 px-5 py-3 flex items-center justify-between">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${tool.is_active?'bg-emerald-50 text-emerald-700 border-emerald-200':'bg-slate-100 text-slate-500 border-slate-200'}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${tool.is_active?'bg-emerald-500':'bg-slate-400'}`}/>{tool.is_active?'Active':'Inactive'}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={e=>{e.stopPropagation();onEdit(tool)}} className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:bg-white hover:text-blue-600 hover:border hover:border-slate-200 transition-all">
            <Pencil className="h-3.5 w-3.5"/>Edit
          </button>
          <button onClick={handleTest} disabled={testing} className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:bg-white hover:text-slate-700 hover:border hover:border-slate-200 transition-all disabled:opacity-50">
            {testing?<Loader2 className="h-3.5 w-3.5 animate-spin"/>:<FlaskConical className="h-3.5 w-3.5"/>}Test
          </button>
          <button onClick={e=>{e.stopPropagation();onDelete(tool.id)}} className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 transition-all">
            <Trash2 className="h-3.5 w-3.5"/>Delete
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Active integrations banner ─────────────────────────────────────────────────

function ActiveIntegrationsBanner({ integrations, onCreateFromIntegration }: {
  integrations: ActiveIntegration[]
  onCreateFromIntegration: (slug: string) => void
}) {
  if (integrations.length === 0) return null
  const relevant = integrations.filter(i => INTEGRATION_TOOL_SLUGS[i.slug])
  if (relevant.length === 0) return null

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Link2 className="h-4 w-4 text-blue-600"/>
        <span className="text-sm font-semibold text-blue-800">Connected integrations</span>
        <span className="text-xs text-blue-600 bg-blue-100 rounded-full px-2 py-0.5">{relevant.length} active</span>
      </div>
      <p className="text-xs text-blue-700 mb-3">These integrations are connected. Click to create a ready-to-use tool from them.</p>
      <div className="flex flex-wrap gap-2">
        {relevant.map(i => {
          const meta = INTEGRATION_TOOL_SLUGS[i.slug]
          return (
            <button
              key={i.id}
              onClick={() => onCreateFromIntegration(i.slug)}
              className="flex items-center gap-1.5 rounded-lg bg-white border border-blue-200 px-3 py-1.5 text-xs font-medium text-blue-700 hover:border-blue-400 hover:bg-blue-50 transition-colors shadow-sm"
            >
              <span>{meta.icon}</span>
              {meta.label}
              <Plus className="h-3 w-3"/>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ToolsPage() {
  const [tools,            setTools]            = useState<Tool[]>([])
  const [activeIntegrations, setActiveIntegrations] = useState<ActiveIntegration[]>([])
  const [isLoading,        setIsLoading]        = useState(true)
  const [search,           setSearch]           = useState('')
  const [activeCategory,   setActiveCategory]   = useState<string|null>(null)
  const [formTool,         setFormTool]         = useState<Tool|'new'|null>(null)
  const [prefillType,      setPrefillType]      = useState<string|null>(null)

  useEffect(() => {
    fetchTools()
    fetchActiveIntegrations()
  }, [])

  const fetchTools = async () => {
    try {
      const res = await apiClient.get<{tools:Tool[];total:number}>(API_ENDPOINTS.TOOLS)
      setTools(res.data.tools||[])
    } catch (err) { toast.error(getErrorMessage(err)) }
    finally { setIsLoading(false) }
  }

  const fetchActiveIntegrations = async () => {
    try {
      const res = await apiClient.get<{connections:any[]}>(API_ENDPOINTS.INTEGRATION_CONNECTIONS)
      const conns = res.data.connections||[]
      setActiveIntegrations(conns
        .filter((c:any) => c.status==='active')
        .map((c:any) => ({ id:c.id, slug:c.connector?.slug||'', name:c.connector?.name||c.name||'', status:c.status }))
      )
    } catch { /* ignore if API unavailable */ }
  }

  const handleToggle = async (id:string, isActive:boolean) => {
    try {
      const res = await apiClient.patch<Tool>(API_ENDPOINTS.TOOL(id), { is_active:isActive })
      setTools(prev=>prev.map(t=>t.id===id?res.data:t))
    } catch (err) { toast.error(getErrorMessage(err)) }
  }

  const handleDelete = async (id:string) => {
    if (!confirm('Delete this tool? It will be removed from all agents.')) return
    try {
      await apiClient.delete(API_ENDPOINTS.TOOL(id))
      setTools(prev=>prev.filter(t=>t.id!==id))
      toast.success('Tool deleted')
    } catch (err) { toast.error(getErrorMessage(err)) }
  }

  const handleSaved = (tool:Tool) => {
    setTools(prev => { const exists=prev.find(t=>t.id===tool.id); return exists?prev.map(t=>t.id===tool.id?tool:t):[tool,...prev] })
    setPrefillType(null)
  }

  const handleCreateFromIntegration = (slug: string) => {
    const meta = INTEGRATION_TOOL_SLUGS[slug]
    if (meta) { setPrefillType(meta.toolType); setFormTool('new') }
  }

  const filtered = tools.filter(t => {
    const ms = !search || t.name.toLowerCase().includes(search.toLowerCase()) || (t.description?.toLowerCase()||'').includes(search.toLowerCase()) || t.tool_type.toLowerCase().includes(search.toLowerCase())
    const mc = !activeCategory || t.category===activeCategory
    return ms && mc
  })

  const categoryCounts = Object.fromEntries(Object.keys(TOOL_TYPES).map(cat=>[cat, tools.filter(t=>t.category===cat).length]))

  // Custom form with prefilled type from integration banner
  const FormWithPrefill = () => {
    const isNew = formTool === 'new'
    return <ToolForm
      initial={isNew ? undefined : formTool as Tool}
      initialType={isNew && prefillType ? prefillType : undefined}
      onClose={()=>{setFormTool(null);setPrefillType(null)}}
      onSaved={handleSaved}
    />
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-7 w-24 bg-slate-200 rounded-lg animate-pulse"/>
          <div className="h-9 w-28 bg-slate-200 rounded-lg animate-pulse"/>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1,2,3].map(i=><div key={i} className="bg-white rounded-xl border border-slate-200 p-5 h-40 animate-pulse"><div className="flex gap-3 mb-4"><div className="h-10 w-10 bg-slate-100 rounded-xl"/><div className="flex-1"><div className="h-4 w-32 bg-slate-100 rounded"/></div></div></div>)}
        </div>
      </div>
    )
  }

  return (
    <>
      {formTool !== null && <FormWithPrefill/>}

      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400"/>
            <input type="text" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search tools…"
              className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 transition-all"/>
          </div>
          <button onClick={()=>{setPrefillType(null);setFormTool('new')}}
            className="flex items-center gap-2 rounded-lg gradient-primary px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm whitespace-nowrap">
            <Plus className="h-4 w-4"/>New Tool
          </button>
        </div>

        {/* Active integrations banner */}
        <ActiveIntegrationsBanner integrations={activeIntegrations} onCreateFromIntegration={handleCreateFromIntegration}/>

        {/* Category tabs */}
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={()=>setActiveCategory(null)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-all border ${!activeCategory?'bg-slate-900 text-white border-slate-900':'bg-white text-slate-600 border-slate-200 hover:border-slate-300'}`}>
            All <span className={`rounded-full px-1.5 py-0.5 text-xs font-semibold ${!activeCategory?'bg-white/20 text-white':'bg-slate-100 text-slate-500'}`}>{tools.length}</span>
          </button>
          {Object.entries(TOOL_TYPES).map(([key,cat])=>{
            const CatIcon = cat.icon; const isActive = activeCategory===key
            return (
              <button key={key} onClick={()=>setActiveCategory(isActive?null:key)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-all border ${isActive?`${cat.bg} ${cat.border} ${cat.color}`:'bg-white text-slate-600 border-slate-200 hover:border-slate-300'}`}>
                <CatIcon className="h-3.5 w-3.5"/>{cat.label}
                {categoryCounts[key]>0 && <span className={`rounded-full px-1.5 py-0.5 text-xs font-semibold ${isActive?'bg-white/40':'bg-slate-100 text-slate-500'}`}>{categoryCounts[key]}</span>}
              </button>
            )
          })}
        </div>

        {/* Grid */}
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-white py-20 px-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 mb-5"><Wrench className="h-8 w-8 text-blue-400"/></div>
            {search||activeCategory ? (
              <><h3 className="text-lg font-semibold text-slate-800">No tools match your filter</h3>
              <p className="text-slate-500 text-sm mt-1.5">Try a different search or category</p>
              <button onClick={()=>{setSearch('');setActiveCategory(null)}} className="mt-4 text-sm text-blue-600 hover:text-blue-700 font-medium">Clear filters</button></>
            ) : (
              <><h3 className="text-lg font-semibold text-slate-800">No tools yet</h3>
              <p className="text-slate-500 text-sm mt-1.5 max-w-sm">Create tools to give your AI agents superpowers — transfer calls, send messages, query APIs, and more</p>
              <button onClick={()=>{setPrefillType(null);setFormTool('new')}} className="mt-6 flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm">
                <Plus className="h-4 w-4"/>Create your first tool
              </button></>
            )}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map(tool=>(
              <ToolCard key={tool.id} tool={tool} onEdit={setFormTool} onDelete={handleDelete} onToggle={handleToggle}/>
            ))}
            <button onClick={()=>{setPrefillType(null);setFormTool('new')}}
              className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-8 min-h-40 hover:border-blue-300 hover:bg-blue-50 transition-all group cursor-pointer">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border-2 border-dashed border-slate-300 group-hover:border-blue-400 transition-colors mb-3">
                <Plus className="h-5 w-5 text-slate-400 group-hover:text-blue-500 transition-colors"/>
              </div>
              <p className="text-sm font-medium text-slate-500 group-hover:text-blue-600 transition-colors">Add tool</p>
            </button>
          </div>
        )}
      </div>
    </>
  )
}
