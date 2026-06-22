'use client'

import React, { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { IntegrationSetup } from '@/components/integrations/IntegrationSetup'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

interface ApiConnection { id: string; status: string; connector: { id: string; slug: string } }
interface Connector { id: string; slug: string; name: string; auth_type: string }

// Full integration catalog — static metadata (icons, features, setup steps)
const integrationData: Record<string, any> = {
  salesforce: {
    slug: 'salesforce', name: 'Salesforce', icon: '🔷',
    description: 'Sync contacts, leads, and opportunities with your Salesforce CRM',
    category: 'crm', authType: 'oauth2',
    features: ['Contact Sync', 'Lead Management', 'Opportunity Tracking', 'Custom Fields'],
    popular: true,
    permissions: ['Read and write contacts', 'Read and write leads', 'Read and write opportunities', 'Access user information'],
    scopes: ['api', 'refresh_token'],
    oauthUrl: 'https://login.salesforce.com/services/oauth2/authorize',
    setupSteps: ['Click "Connect" to authorize Voicecon', 'Sign in to your Salesforce account', 'Review and approve permissions', 'You will be redirected back'],
  },
  hubspot: {
    slug: 'hubspot', name: 'HubSpot', icon: '🟠',
    description: 'Connect HubSpot CRM to manage contacts and track interactions',
    category: 'crm', authType: 'oauth2',
    features: ['Contact Management', 'Deal Pipeline', 'Email Tracking', 'Analytics'],
    popular: true,
    permissions: ['Read and write contacts', 'Read and write deals', 'Access timeline events'],
    scopes: ['contacts', 'crm.objects.deals.read', 'crm.objects.deals.write'],
    oauthUrl: 'https://app.hubspot.com/oauth/authorize',
    setupSteps: ['Click "Connect" to start OAuth', 'Select your HubSpot account', 'Grant permissions', 'Return to Voicecon'],
  },
  pipedrive: {
    slug: 'pipedrive', name: 'Pipedrive', icon: '🟢',
    description: 'Sales pipeline CRM to track deals and contacts from voice calls',
    category: 'crm', authType: 'oauth2',
    features: ['Deal Tracking', 'Contact Sync', 'Pipeline Management', 'Activity Logging'],
    popular: false,
    permissions: ['Read and write deals', 'Read and write contacts', 'Access pipeline data'],
    scopes: ['deals:full', 'contacts:full', 'activities:full'],
    oauthUrl: 'https://oauth.pipedrive.com/oauth/authorize',
    setupSteps: ['Click "Connect with Pipedrive"', 'Log in to your Pipedrive account', 'Authorize Voicecon', 'Configure which pipeline to use'],
  },
  zendesk: {
    slug: 'zendesk', name: 'Zendesk', icon: '🎫',
    description: 'Create and update support tickets from voice interactions',
    category: 'crm', authType: 'oauth2',
    features: ['Ticket Management', 'Customer Profiles', 'Automation', 'Reporting'],
    popular: false,
    permissions: ['Create and update tickets', 'Read user information', 'Access ticket history'],
    scopes: ['tickets:write', 'users:read'],
    oauthUrl: 'https://your-subdomain.zendesk.com/oauth/authorizations/new',
    setupSteps: ['Enter your Zendesk subdomain', 'Authorize Voicecon', 'Configure ticket fields', 'Set up automation rules'],
  },
  intercom: {
    slug: 'intercom', name: 'Intercom', icon: '💬',
    description: 'Create conversations and update contacts in Intercom from calls',
    category: 'crm', authType: 'oauth2',
    features: ['Conversation Sync', 'Contact Management', 'Notes & Tags', 'Event Tracking'],
    popular: false,
    permissions: ['Read and write conversations', 'Manage contacts', 'Add notes and tags'],
    scopes: ['read_conversations', 'write_conversations', 'manage_contacts'],
    oauthUrl: 'https://app.intercom.com/oauth',
    setupSteps: ['Connect your Intercom workspace', 'Select permission scopes', 'Authorize Voicecon', 'Configure contact sync'],
  },
  'google-calendar': {
    slug: 'google-calendar', name: 'Google Calendar', icon: '📅',
    description: 'Schedule appointments and manage events from voice conversations',
    category: 'calendar', authType: 'oauth2',
    features: ['Event Creation', 'Availability Check', 'Reminders', 'Multi-Calendar'],
    popular: true,
    permissions: ['View and manage calendars', 'Create and edit events', 'Set event reminders'],
    scopes: ['https://www.googleapis.com/auth/calendar'],
    oauthUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    setupSteps: ['Click "Connect with Google"', 'Choose your Google account', 'Allow Voicecon calendar access', 'Configure which calendars to use'],
  },
  calendly: {
    slug: 'calendly', name: 'Calendly', icon: '🗓️',
    description: 'Book appointments using your Calendly scheduling links',
    category: 'calendar', authType: 'oauth2',
    features: ['Meeting Scheduling', 'Availability Sync', 'Custom Links', 'Reminders'],
    popular: false,
    permissions: ['Access your event types', 'Schedule meetings', 'View availability'],
    scopes: ['default'],
    oauthUrl: 'https://auth.calendly.com/oauth/authorize',
    setupSteps: ['Connect your Calendly account', 'Select event types to use', 'Configure scheduling preferences', 'Test booking flow'],
  },
  'cal-com': {
    slug: 'cal-com', name: 'Cal.com', icon: '📆',
    description: 'Open-source scheduling — book meetings directly from voice calls',
    category: 'calendar', authType: 'api_key',
    features: ['Meeting Scheduling', 'Custom Event Types', 'Team Scheduling', 'Webhooks'],
    popular: false,
    permissions: ['Access event types', 'Book appointments', 'Manage availability'],
    setupSteps: ['Go to Cal.com Settings → API Keys', 'Generate a new API key', 'Enter the key below', 'Test scheduling'],
    apiKeyFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'username', label: 'Cal.com Username', type: 'text', required: true },
    ],
  },
  slack: {
    slug: 'slack', name: 'Slack', icon: '💬',
    description: 'Send notifications and updates to your Slack channels',
    category: 'communication', authType: 'oauth2',
    features: ['Channel Messages', 'Direct Messages', 'File Sharing', 'Webhooks'],
    popular: true,
    permissions: ['Send messages to channels', 'Send direct messages', 'Read channel information'],
    scopes: ['chat:write', 'channels:read', 'users:read'],
    oauthUrl: 'https://slack.com/oauth/v2/authorize',
    setupSteps: ['Click "Add to Slack"', 'Select your workspace', 'Choose channels', 'Authorize Voicecon'],
  },
  'microsoft-teams': {
    slug: 'microsoft-teams', name: 'Microsoft Teams', icon: '👥',
    description: 'Send messages and notifications to Teams channels',
    category: 'communication', authType: 'oauth2',
    features: ['Channel Messages', 'Chat', 'File Sharing', 'Meeting Integration'],
    popular: false,
    permissions: ['Send channel messages', 'Send chat messages', 'Read team information'],
    scopes: ['ChannelMessage.Send', 'Chat.ReadWrite'],
    oauthUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
    setupSteps: ['Sign in with Microsoft account', 'Select your organization', 'Grant Teams permissions', 'Choose channels to use'],
  },
  twilio: {
    slug: 'twilio', name: 'Twilio', icon: '📞',
    description: 'Enhanced telephony features and SMS capabilities',
    category: 'communication', authType: 'api_key',
    features: ['Voice Calls', 'SMS', 'WhatsApp', 'Call Recording'],
    popular: false,
    permissions: ['Make and receive calls', 'Send and receive SMS', 'Access call logs', 'Manage phone numbers'],
    setupSteps: ['Get your Account SID from Twilio Console', 'Generate an Auth Token', 'Enter credentials below', 'Test the connection'],
    apiKeyFields: [
      { name: 'account_sid', label: 'Account SID', type: 'text', required: true },
      { name: 'auth_token', label: 'Auth Token', type: 'password', required: true },
      { name: 'phone_number', label: 'Phone Number (optional)', type: 'text', required: false },
    ],
  },
  sendgrid: {
    slug: 'sendgrid', name: 'SendGrid', icon: '✉️',
    description: 'Send transactional emails from voice conversations',
    category: 'communication', authType: 'api_key',
    features: ['Transactional Email', 'Templates', 'Analytics', 'List Management'],
    popular: false,
    permissions: ['Send emails', 'Manage email templates', 'Access analytics'],
    setupSteps: ['Log in to SendGrid', 'Go to Settings → API Keys', 'Create a new API key with Mail Send permissions', 'Paste below'],
    apiKeyFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'from_email', label: 'From Email Address', type: 'email', required: true },
    ],
  },
  zapier: {
    slug: 'zapier', name: 'Zapier', icon: '⚡',
    description: 'Connect to 5000+ apps through Zapier automation',
    category: 'productivity', authType: 'oauth2',
    features: ['Workflow Automation', 'Custom Triggers', 'Multi-Step Zaps', 'Webhooks'],
    popular: true,
    permissions: ['Create and manage Zaps', 'Trigger automation workflows', 'Access connected apps'],
    scopes: ['zap:read', 'zap:write'],
    oauthUrl: 'https://zapier.com/oauth/authorize',
    setupSteps: ['Connect your Zapier account', 'Create Zaps using Voicecon triggers', 'Configure automation workflows', 'Test your Zaps'],
  },
  make: {
    slug: 'make', name: 'Make (Integromat)', icon: '🔧',
    description: 'Visual automation platform — connect Voicecon to any app',
    category: 'productivity', authType: 'api_key',
    features: ['Visual Automation', 'Webhooks', '1000+ Apps', 'Data Mapping'],
    popular: false,
    permissions: ['Trigger scenarios', 'Send data to Make', 'Receive webhook data'],
    setupSteps: ['Create a Make account at make.com', 'Create a new scenario with a Webhook module', 'Copy the webhook URL', 'Paste it below'],
    apiKeyFields: [
      { name: 'webhook_url', label: 'Make Webhook URL', type: 'text', required: true },
    ],
  },
  'google-sheets': {
    slug: 'google-sheets', name: 'Google Sheets', icon: '📊',
    description: 'Log call data and customer information to spreadsheets',
    category: 'productivity', authType: 'oauth2',
    features: ['Data Logging', 'Real-time Updates', 'Custom Columns', 'Formulas'],
    popular: false,
    permissions: ['Create and edit spreadsheets', 'Read spreadsheet data'],
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    oauthUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    setupSteps: ['Authorize Google Sheets access', 'Select or create a spreadsheet', 'Map data fields to columns', 'Configure update frequency'],
  },
  'google-drive': {
    slug: 'google-drive', name: 'Google Drive', icon: '💾',
    description: 'Save call recordings and transcripts to Google Drive',
    category: 'productivity', authType: 'oauth2',
    features: ['File Upload', 'Folder Organization', 'Sharing', 'Search'],
    popular: false,
    permissions: ['Upload files to Drive', 'Create and manage folders', 'Access file metadata'],
    scopes: ['https://www.googleapis.com/auth/drive.file'],
    oauthUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    setupSteps: ['Click "Connect with Google"', 'Choose your Google account', 'Allow Drive access', 'Select a folder for recordings'],
  },
  airtable: {
    slug: 'airtable', name: 'Airtable', icon: '🗂️',
    description: 'Store and organize conversation data in flexible databases',
    category: 'productivity', authType: 'api_key',
    features: ['Database Sync', 'Custom Fields', 'Views', 'Automation'],
    popular: false,
    permissions: ['Read and write records', 'Access base structure', 'Manage fields'],
    setupSteps: ['Copy your Airtable API key', 'Enter your Base ID', 'Paste credentials below', 'Select tables to sync'],
    apiKeyFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'base_id', label: 'Base ID', type: 'text', required: true },
    ],
  },
  stripe: {
    slug: 'stripe', name: 'Stripe', icon: '💳',
    description: 'Process payments and manage subscriptions during calls',
    category: 'payment', authType: 'api_key',
    features: ['Payment Processing', 'Subscription Management', 'Invoicing', 'Webhooks'],
    popular: true,
    permissions: ['Process payments', 'Manage customers', 'Create subscriptions', 'Access payment data'],
    setupSteps: ['Get your Stripe API keys from dashboard.stripe.com', 'Enter Secret Key below', 'Configure webhook endpoints', 'Test payment processing'],
    apiKeyFields: [
      { name: 'secret_key', label: 'Secret Key', type: 'password', required: true },
      { name: 'publishable_key', label: 'Publishable Key', type: 'text', required: true },
    ],
  },
  // GoHighLevel
  gohighlevel: {
    slug: 'gohighlevel', name: 'GoHighLevel', icon: '🚀',
    description: 'All-in-one CRM — sync contacts, pipelines, and SMS from voice calls',
    category: 'crm', authType: 'api_key',
    features: ['Contact Sync', 'Pipeline Management', 'SMS Campaigns', 'Appointment Booking'],
    popular: true,
    permissions: ['Read and write contacts', 'Manage pipelines', 'Send SMS', 'Manage appointments'],
    setupSteps: ['Log in to your GoHighLevel account', 'Go to Settings → API → API Keys', 'Create a new API key', 'Enter your Location ID and API key below'],
    apiKeyFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'location_id', label: 'Location ID', type: 'text', required: true },
    ],
  },
  // Notion
  notion: {
    slug: 'notion', name: 'Notion', icon: '📝',
    description: 'Create and update Notion pages and databases from voice conversations',
    category: 'productivity', authType: 'oauth2',
    features: ['Page Creation', 'Database Updates', 'Notes', 'Task Tracking'],
    popular: false,
    permissions: ['Create and edit pages', 'Read and update databases', 'Access workspace'],
    scopes: ['read_content', 'update_content', 'insert_content'],
    oauthUrl: 'https://api.notion.com/v1/oauth/authorize',
    setupSteps: ['Click "Connect with Notion"', 'Select your workspace', 'Choose pages/databases to share', 'Authorize Voicecon'],
  },
  // Monday.com
  monday: {
    slug: 'monday', name: 'Monday.com', icon: '📋',
    description: 'Update boards and items in Monday.com from call outcomes',
    category: 'productivity', authType: 'oauth2',
    features: ['Board Updates', 'Item Creation', 'Status Tracking', 'Automations'],
    popular: false,
    permissions: ['Read boards and items', 'Create and update items', 'Manage workspaces'],
    scopes: ['boards:read', 'boards:write'],
    oauthUrl: 'https://auth.monday.com/oauth2/authorize',
    setupSteps: ['Click "Connect with Monday.com"', 'Select your workspace', 'Grant board permissions', 'Choose default boards'],
  },
  // Phone Providers
  telnyx: {
    slug: 'telnyx', name: 'Telnyx', icon: '📱',
    description: 'Carrier-grade VoIP and SIP trunking for voice AI deployments',
    category: 'phone', authType: 'api_key',
    features: ['SIP Trunking', 'Phone Numbers', 'SMS', 'Call Control API'],
    popular: true,
    permissions: ['Manage phone numbers', 'Make and receive calls', 'Send SMS', 'Access call logs'],
    setupSteps: ['Log in to portal.telnyx.com', 'Go to Auth → API Keys', 'Create a new API key', 'Enter the key below'],
    apiKeyFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'sip_connection_id', label: 'SIP Connection ID (optional)', type: 'text', required: false },
    ],
  },
  vonage: {
    slug: 'vonage', name: 'Vonage (Nexmo)', icon: '☎️',
    description: 'Global cloud communications — calls, SMS, and phone number management',
    category: 'phone', authType: 'api_key',
    features: ['Voice Calls', 'SMS', 'Phone Numbers', 'WebRTC'],
    popular: false,
    permissions: ['Make and receive calls', 'Send SMS', 'Manage phone numbers', 'Access call logs'],
    setupSteps: ['Go to dashboard.nexmo.com', 'Navigate to API Settings', 'Copy your API Key and API Secret', 'Enter both below'],
    apiKeyFields: [
      { name: 'api_key', label: 'API Key', type: 'text', required: true },
      { name: 'api_secret', label: 'API Secret', type: 'password', required: true },
      { name: 'application_id', label: 'Application ID (optional)', type: 'text', required: false },
    ],
  },
  // Analytics / Observability
  langfuse: {
    slug: 'langfuse', name: 'Langfuse', icon: '🔭',
    description: 'Open-source LLM observability — trace, evaluate, and debug AI calls',
    category: 'analytics', authType: 'api_key',
    features: ['LLM Tracing', 'Prompt Management', 'Evaluation', 'Cost Tracking'],
    popular: true,
    permissions: ['Send traces and spans', 'Log LLM requests', 'Access evaluation metrics'],
    setupSteps: ['Create an account at langfuse.com (or self-host)', 'Go to Settings → API Keys', 'Create a new API key pair', 'Enter public and secret keys below'],
    apiKeyFields: [
      { name: 'public_key', label: 'Public Key', type: 'text', required: true },
      { name: 'secret_key', label: 'Secret Key', type: 'password', required: true },
      { name: 'host', label: 'Host URL (leave blank for cloud)', type: 'text', required: false },
    ],
  },
  // Cloud Storage
  'aws-s3': {
    slug: 'aws-s3', name: 'AWS S3', icon: '🪣',
    description: 'Store call recordings, transcripts, and files in Amazon S3 buckets',
    category: 'cloud', authType: 'api_key',
    features: ['File Storage', 'Bucket Management', 'CDN', 'Access Control'],
    popular: true,
    permissions: ['Upload and download files', 'List and manage buckets', 'Manage object permissions'],
    setupSteps: ['Open AWS Console → IAM → Users', 'Create a new user with S3 permissions', 'Generate Access Key ID and Secret', 'Enter credentials and your bucket name below'],
    apiKeyFields: [
      { name: 'access_key_id', label: 'Access Key ID', type: 'text', required: true },
      { name: 'secret_access_key', label: 'Secret Access Key', type: 'password', required: true },
      { name: 'bucket_name', label: 'Bucket Name', type: 'text', required: true },
      { name: 'region', label: 'Region (e.g. us-east-1)', type: 'text', required: true },
    ],
  },
  'azure-blob': {
    slug: 'azure-blob', name: 'Azure Blob Storage', icon: '🔵',
    description: 'Store and manage call data in Microsoft Azure Blob Storage',
    category: 'cloud', authType: 'api_key',
    features: ['Blob Storage', 'Container Management', 'SAS Tokens', 'Access Tiers'],
    popular: false,
    permissions: ['Upload and download blobs', 'Manage containers', 'Generate SAS URLs'],
    setupSteps: ['Open Azure Portal → Storage Accounts', 'Create or select a storage account', 'Go to Access Keys and copy the connection string', 'Paste below'],
    apiKeyFields: [
      { name: 'connection_string', label: 'Connection String', type: 'password', required: true },
      { name: 'container_name', label: 'Container Name', type: 'text', required: true },
    ],
  },
  gcs: {
    slug: 'gcs', name: 'Google Cloud Storage', icon: '☁️',
    description: 'Store recordings and data in Google Cloud Storage buckets',
    category: 'cloud', authType: 'api_key',
    features: ['Object Storage', 'Bucket Policies', 'Lifecycle Rules', 'CDN Integration'],
    popular: false,
    permissions: ['Upload and manage objects', 'Read bucket metadata', 'Create signed URLs'],
    setupSteps: ['Open Google Cloud Console → IAM → Service Accounts', 'Create a service account with Storage Object Admin role', 'Download the JSON key file', 'Paste the JSON content below'],
    apiKeyFields: [
      { name: 'service_account_json', label: 'Service Account JSON', type: 'password', required: true },
      { name: 'bucket_name', label: 'Bucket Name', type: 'text', required: true },
    ],
  },
  'cloudflare-r2': {
    slug: 'cloudflare-r2', name: 'Cloudflare R2', icon: '🔶',
    description: 'Zero-egress object storage for recordings and call artifacts',
    category: 'cloud', authType: 'api_key',
    features: ['Object Storage', 'Zero Egress Fees', 'S3-compatible API', 'Global CDN'],
    popular: false,
    permissions: ['Upload and download objects', 'Manage buckets', 'Generate presigned URLs'],
    setupSteps: ['Log in to Cloudflare Dashboard', 'Go to R2 → Manage R2 API Tokens', 'Create a token with Object Read & Write permissions', 'Enter your Account ID, token, and bucket name below'],
    apiKeyFields: [
      { name: 'account_id', label: 'Account ID', type: 'text', required: true },
      { name: 'access_key_id', label: 'Access Key ID', type: 'text', required: true },
      { name: 'secret_access_key', label: 'Secret Access Key', type: 'password', required: true },
      { name: 'bucket_name', label: 'Bucket Name', type: 'text', required: true },
    ],
  },
  supabase: {
    slug: 'supabase', name: 'Supabase', icon: '⚡',
    description: 'Open-source Firebase alternative — store call data in Postgres',
    category: 'cloud', authType: 'api_key',
    features: ['Postgres Database', 'Realtime', 'Storage', 'Edge Functions'],
    popular: false,
    permissions: ['Read and write database records', 'Upload files to Storage', 'Call Edge Functions'],
    setupSteps: ['Log in to app.supabase.com', 'Select your project → Settings → API', 'Copy the Project URL and service_role key', 'Enter both below'],
    apiKeyFields: [
      { name: 'project_url', label: 'Project URL', type: 'text', required: true },
      { name: 'service_role_key', label: 'Service Role Key', type: 'password', required: true },
    ],
  },
}

export default function IntegrationDetailPage() {
  const router = useRouter()
  const params = useParams()
  const slug = params?.slug as string

  const [integration, setIntegration] = useState<any>(null)
  const [connectorId, setConnectorId] = useState<string | undefined>()
  const [existingConnectionId, setExistingConnectionId] = useState<string | undefined>()
  const [loading, setLoading] = useState(true)

  // Load static catalog entry
  useEffect(() => {
    const data = integrationData[slug]
    if (data) setIntegration(data)
    setLoading(false)
  }, [slug])

  // Look up backend connector ID and existing connection in parallel
  useEffect(() => {
    if (!slug) return
    Promise.allSettled([
      apiClient.get<{ connectors: Connector[]; total: number }>(
        API_ENDPOINTS.INTEGRATION_CONNECTORS + `?search=${slug}`
      ),
      apiClient.get<{ connections: ApiConnection[] }>(API_ENDPOINTS.INTEGRATION_CONNECTIONS),
    ]).then(([connRes, connxRes]) => {
      if (connRes.status === 'fulfilled') {
        const match = connRes.value.data.connectors?.find((c) => c.slug === slug)
        if (match) setConnectorId(match.id)
      }
      if (connxRes.status === 'fulfilled') {
        const conns = connxRes.value.data.connections || (connxRes.value.data as any) || []
        const match = (Array.isArray(conns) ? conns : []).find(
          (c: ApiConnection) => c.connector?.slug === slug
        )
        if (match) setExistingConnectionId(match.id)
      }
    })
  }, [slug])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-500">Loading integration…</p>
        </div>
      </div>
    )
  }

  if (!integration) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Integration Not Found</h2>
          <p className="text-slate-500 mb-6">The integration you&apos;re looking for doesn&apos;t exist.</p>
          <Button onClick={() => router.push('/dashboard/integrations')}>
            <ArrowLeft className="w-4 h-4 mr-2" /> Back to Integrations
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <Button variant="ghost" onClick={() => router.push('/dashboard/integrations')} className="mb-4 gap-2 -ml-2 text-slate-600">
          <ArrowLeft className="w-4 h-4" /> Back to Integrations
        </Button>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-700 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm">
              <span className="text-white text-2xl font-bold leading-none">
                {integration.name.slice(0, 2).toUpperCase()}
              </span>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-2xl font-bold text-slate-900">{integration.name}</h1>
                {connectorId ? (
                  <span className="rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs px-2.5 py-1 font-medium">
                    Ready to Connect
                  </span>
                ) : (
                  <span className="rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-xs px-2.5 py-1 font-medium">
                    Requires Server Config
                  </span>
                )}
              </div>
              <p className="text-slate-500">{integration.description}</p>
            </div>
          </div>
        </div>
      </div>

      <IntegrationSetup
        integration={integration}
        connectorId={connectorId}
        existingConnectionId={existingConnectionId}
        onDisconnected={() => setExistingConnectionId(undefined)}
        onConnected={(id) => setExistingConnectionId(id)}
      />
    </div>
  )
}
