/** Display names for integration slugs ("hubspot" → "HubSpot"). */
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

/**
 * The product name for an integration slug. Unknown slugs are title-cased
 * ("google-drive" → "Google Drive") rather than shown raw.
 */
export function appDisplayName(slug: string): string {
  if (!slug) return slug
  return (
    APP_NAMES[slug] ??
    slug
      .split(/[-_]/)
      .filter(Boolean)
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ')
  )
}
