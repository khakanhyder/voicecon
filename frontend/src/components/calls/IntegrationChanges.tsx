'use client'

import { useEffect, useState } from 'react'
import { CalendarClock, AlertCircle, History, Trash2 } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

interface Change {
  id: string
  connector_slug: string
  action: string
  operation: 'update' | 'delete'
  record_id: string | null
  parameters: Record<string, unknown> | null
  before: Record<string, unknown> | null
  success: boolean
  error_message: string | null
  created_at: string | null
}

const APP_NAMES: Record<string, string> = {
  'google-calendar': 'Google Calendar',
  google_calendar: 'Google Calendar',
  clickup: 'ClickUp',
  trello: 'Trello',
  airtable: 'Airtable',
  hubspot: 'HubSpot',
  salesforce: 'Salesforce',
  gohighlevel: 'GoHighLevel',
  stripe: 'Stripe',
  'google-sheets': 'Google Sheets',
  'cal-com': 'Cal.com',
  calendly: 'Calendly',
  notion: 'Notion',
  zendesk: 'Zendesk',
  pipedrive: 'Pipedrive',
  supabase: 'Supabase',
  monday: 'monday.com',
  intercom: 'Intercom',
  slack: 'Slack',
  sendgrid: 'SendGrid',
}

const ACTION_LABELS: Record<string, string> = {
  update_event: 'Rescheduled appointment',
  delete_event: 'Cancelled appointment',
  update_task: 'Updated task',
  update_card: 'Updated card',
  update_record: 'Updated record',
  update_contact: 'Updated contact',
  delete_contact: 'Deleted contact',
  update_deal: 'Updated deal',
  update_lead: 'Updated lead',
  update_customer: 'Updated customer',
  cancel_subscription: 'Cancelled subscription',
  cancel_payment_intent: 'Cancelled payment',
  update_row: 'Updated row',
  upsert_row: 'Saved row',
  delete_row: 'Deleted row',
  reschedule_appointment: 'Rescheduled appointment',
  cancel_appointment: 'Cancelled appointment',
  update_opportunity: 'Updated opportunity',
  reschedule_booking: 'Rescheduled booking',
  cancel_booking: 'Cancelled booking',
  cancel_event: 'Cancelled booking',
  update_database_item: 'Updated row',
  update_page_title: 'Renamed page',
  archive_page: 'Archived page',
  update_ticket: 'Updated ticket',
  update_person: 'Updated person',
  delete_person: 'Deleted person',
  delete_deal: 'Deleted deal',
  delete_task: 'Deleted task',
  archive_card: 'Archived card',
  delete_record: 'Deleted record',
  update_item: 'Updated item',
  archive_item: 'Archived item',
  archive_contact: 'Archived contact',
  close_conversation: 'Closed conversation',
  update_message: 'Edited message',
  delete_message: 'Deleted message',
  add_contact: 'Saved contact',
  remove_contact_from_list: 'Removed from list',
}

/** A human name for the record, from whatever shape the app returned. */
function recordName(change: Change): string {
  const b = (change.before || {}) as Record<string, unknown>
  const props = (b.properties || b.fields || b.values || {}) as Record<string, unknown>
  const first = (b.first_name ?? b.FirstName ?? props.firstname) as string | undefined
  const last = (b.last_name ?? b.LastName ?? props.lastname) as string | undefined
  const candidates = [
    b.summary, b.name, b.title, b.Name, props.dealname, props.Name,
    (b.ticket as Record<string, unknown> | undefined)?.subject,
    typeof (b.row as Record<string, unknown> | undefined)?.name === 'string' ? (b.row as Record<string, unknown>).name : undefined,
    [first, last].filter(Boolean).join(' '), b.email, b.Email, props.email,
  ]
  const found = candidates.find((c) => typeof c === 'string' && c.trim())
  return (found as string) || change.record_id || 'Record'
}

function when(value: unknown): string | null {
  const raw = typeof value === 'object' && value ? (value as { dateTime?: string; date?: string }).dateTime ?? (value as { date?: string }).date : value
  if (typeof raw !== 'string') return null
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? raw : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** What the change did, in one line: "Cleaning - Sara: Oct 1, 3:00 PM → Oct 2, 11:00 AM". */
function summary(change: Change): string {
  const title = recordName(change)
  if (change.action === 'update_event') {
    const from = when(change.before?.start)
    const to = when(change.parameters?.start_time)
    if (from && to) return `${title}: ${from} → ${to}`
  }
  if (change.action === 'delete_event') {
    const at = when(change.before?.start)
    if (at) return `${title} (${at})`
  }
  const changed = Object.keys(change.parameters || {}).filter(
    (k) => !/(_id|^id|calendar|table_name)$/.test(k) && change.parameters?.[k] != null,
  )
  return changed.length && change.operation === 'update'
    ? `${title}: changed ${changed.map((k) => k.replace(/_/g, ' ')).join(', ')}`
    : title
}

/**
 * Updates and deletes the agent made in connected apps during this call, with
 * what each record looked like before. Renders nothing when there were none.
 */
export function IntegrationChanges({ callId }: { callId: string }) {
  const [changes, setChanges] = useState<Change[]>([])

  useEffect(() => {
    apiClient
      .get<{ changes: Change[] }>(API_ENDPOINTS.INTEGRATION_CHANGES, { params: { call_id: callId } })
      .then((res) => setChanges(res.data.changes || []))
      .catch(() => setChanges([]))
  }, [callId])

  if (changes.length === 0) return null

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5">
      <h3 className="flex items-center gap-2 text-[14px] font-bold font-poppins text-[#000000] mb-3">
        <History className="h-4 w-4 text-black/50" />
        Changes in connected apps
      </h3>
      <ul className="space-y-3">
        {changes.map((change) => {
          const Icon = !change.success ? AlertCircle : change.operation === 'delete' ? Trash2 : CalendarClock
          return (
            <li key={change.id} className="flex items-start gap-2.5 text-[12px] font-poppins">
              <Icon
                className={`mt-0.5 h-4 w-4 shrink-0 ${!change.success ? 'text-amber-600' : change.operation === 'delete' ? 'text-red-600' : 'text-[#106959]'}`}
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="font-semibold text-black/80">
                  {ACTION_LABELS[change.action] || change.action.replace(/_/g, ' ')}
                  <span className="font-normal text-black/40"> · {APP_NAMES[change.connector_slug] || change.connector_slug}</span>
                  {!change.success && <span className="ml-1 font-normal text-amber-700">(failed)</span>}
                </p>
                <p className="break-words text-black/60">{summary(change)}</p>
                {!change.success && change.error_message && (
                  <p className="mt-0.5 break-words text-amber-700">{change.error_message}</p>
                )}
                {change.created_at && <p className="mt-0.5 text-black/40">{when(change.created_at + 'Z')}</p>}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
