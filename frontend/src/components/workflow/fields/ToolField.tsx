'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

interface WorkspaceTool {
  id: string
  name: string
  tool_type: string
  is_active: boolean
}

const SELECT_CLASS =
  'h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60'

/** Tool type slugs rendered as the labels used everywhere else in the app. */
const TYPE_LABELS: Record<string, string> = {
  workflow: 'Run Workflow',
  transfer_call: 'Transfer Call',
  hang_up: 'Hang Up',
  leave_voicemail: 'Leave Voicemail',
  dtmf: 'DTMF',
  send_sms: 'Send Text',
  sip_request: 'SIP Request',
  handoff: 'Handoff',
  query_knowledge_base: 'Query Knowledge Base',
  connected_integration: 'Connected Integration',
  api_request: 'API Request',
  mcp: 'MCP',
  slack: 'Slack',
  google_sheets: 'Google Sheets',
  google_calendar: 'Google Calendar',
  gohighlevel: 'GoHighLevel',
  custom_tool: 'Custom Tool',
}

/**
 * Picks one of the workspace's tools for a Run Tool node.
 *
 * This was a free-text box whose placeholder read `tool_xxxxxxxx`, while the
 * engine requires the tool's UUID — and the Tools page does not print an id
 * anywhere. So the field could not be filled in correctly from the interface at
 * all: every Run Tool node failed at execution with "Invalid tool_id".
 *
 * A picker also scopes the choice to this workspace, which is what the engine
 * enforces on the way through: naming another tenant's tool is refused there,
 * so offering the possibility here would only produce a confusing failure.
 */
export function ToolField({
  id,
  value,
  onChange,
}: {
  id: string
  value: string
  onChange: (value: string) => void
}) {
  const [tools, setTools] = useState<WorkspaceTool[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    apiClient
      .get<{ tools: WorkspaceTool[] }>(API_ENDPOINTS.TOOLS)
      .then((res) => {
        if (!cancelled) setTools(res.data.tools ?? [])
      })
      .catch(() => {
        if (!cancelled) setError('Could not load tools')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (isLoading) {
    return (
      <div className="flex h-10 items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading tools…
      </div>
    )
  }

  if (error) return <p className="text-sm text-destructive">{error}</p>

  if (tools.length === 0) {
    return (
      <p className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
        No tools yet. Create one in the Tools section, then pick it here.
      </p>
    )
  }

  // A tool the workflow already names but which has since been deleted would
  // otherwise vanish from the select, silently blanking the node's config on
  // the next save. Keep it visible and say what happened.
  const isMissing = Boolean(value) && !tools.some((tool) => tool.id === value)

  return (
    <div className="space-y-1.5">
      <select
        id={id}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className={SELECT_CLASS}
      >
        <option value="">Select a tool…</option>
        {isMissing && (
          <option value={value}>This tool no longer exists — pick another</option>
        )}
        {tools.map((tool) => (
          <option key={tool.id} value={tool.id}>
            {tool.name}
            {TYPE_LABELS[tool.tool_type]
              ? ` (${TYPE_LABELS[tool.tool_type]})`
              : ''}
            {tool.is_active === false ? ' — inactive' : ''}
          </option>
        ))}
      </select>

      {isMissing && (
        <p className="text-xs text-destructive">
          The tool this step points at has been deleted. The run will fail here
          until you choose another.
        </p>
      )}
    </div>
  )
}
