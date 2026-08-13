'use client'

import React, { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ConnectionDefaults } from '@/components/integrations/ConnectionDefaults'
import { IntegrationSetup } from '@/components/integrations/IntegrationSetup'
import { getIconUrl } from '@/components/integrations/IntegrationCard'
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
    category: 'crm', authType: 'api_key',
    features: ['Deal Tracking', 'Contact Sync', 'Pipeline Management', 'Activity Logging'],
    popular: false,
    permissions: ['Read and write deals', 'Read and write people', 'Add notes to records'],
    setupSteps: [
      'In Pipedrive, open Settings → Personal preferences → API',
      'Copy your personal API token',
      'Paste it below',
    ],
    apiKeyFields: [
      { name: 'api_token', label: 'API Token', type: 'password', required: true },
    ],
  },
  zendesk: {
    slug: 'zendesk', name: 'Zendesk', icon: '🎫',
    description: 'Create and update support tickets from voice interactions',
    category: 'crm', authType: 'api_key',
    features: ['Ticket Management', 'Customer Profiles', 'Comments', 'Search'],
    popular: false,
    permissions: ['Create and update tickets', 'Read user information', 'Search ticket history'],
    setupSteps: [
      'In Zendesk, open Admin Center → Apps and integrations → Zendesk API',
      'Enable token access and add an API token',
      'Enter your subdomain, the email of the agent account, and the token below',
    ],
    apiKeyFields: [
      { name: 'subdomain_url', label: 'Zendesk Subdomain (e.g. acme)', type: 'text', required: true },
      { name: 'email', label: 'Agent Email', type: 'text', required: true },
      { name: 'api_token', label: 'API Token', type: 'password', required: true },
    ],
  },
  intercom: {
    slug: 'intercom', name: 'Intercom', icon: '💬',
    description: 'Create conversations and update contacts in Intercom from calls',
    category: 'crm', authType: 'api_key',
    features: ['Conversation Sync', 'Contact Management', 'Notes', 'Search'],
    popular: false,
    permissions: ['Read and write conversations', 'Manage contacts', 'Add notes'],
    setupSteps: [
      'Open the Intercom Developer Hub and select your app',
      'Go to Authentication and copy the Access Token',
      'Paste it below',
    ],
    apiKeyFields: [
      { name: 'access_token', label: 'Access Token', type: 'password', required: true },
    ],
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
    category: 'communication', authType: 'api_key',
    features: ['Channel Messages', 'Rich Cards', 'Alerts'],
    popular: false,
    permissions: ['Post messages to the connected channel'],
    setupSteps: [
      'In Teams, open the channel you want messages in',
      'Click ⋯ → Connectors (or Workflows) → Incoming Webhook',
      'Name it, create it, and copy the URL',
      'Paste it below',
    ],
    apiKeyFields: [
      { name: 'webhook_url', label: 'Incoming Webhook URL', type: 'text', required: true },
    ],
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
    category: 'productivity', authType: 'api_key',
    features: ['Workflow Automation', 'Custom Triggers', 'Multi-Step Zaps', 'Webhooks'],
    popular: true,
    permissions: ['Send call data to your Zap'],
    setupSteps: [
      'In Zapier, create a Zap with the "Webhooks by Zapier" trigger',
      'Choose "Catch Hook" and copy the custom webhook URL',
      'Paste it below — we will send a test payload so Zapier can learn the shape',
    ],
    apiKeyFields: [
      { name: 'webhook_url', label: 'Catch Hook URL', type: 'text', required: true },
    ],
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
    permissions: ['Upload and download blobs', 'List container contents', 'Generate SAS URLs'],
    setupSteps: [
      'Open Azure Portal → Storage accounts → your account',
      'Recommended: Containers → your container → Shared access tokens → generate a SAS with Read/Write/List',
      'Or use Access keys → Key → Show, for full-account access',
      'Enter the account name, container, and whichever credential you generated',
    ],
    apiKeyFields: [
      { name: 'account_name', label: 'Storage Account Name', type: 'text', required: true },
      { name: 'container_name', label: 'Container Name', type: 'text', required: true },
      { name: 'sas_token', label: 'SAS Token (recommended)', type: 'password', required: false },
      { name: 'account_key', label: 'Account Key (full access — use only if you have no SAS)', type: 'password', required: false },
    ],
  },
  gcs: {
    slug: 'gcs', name: 'Google Cloud Storage', icon: '☁️',
    description: 'Store recordings and data in Google Cloud Storage buckets',
    category: 'cloud', authType: 'api_key',
    features: ['Object Storage', 'Signed URLs', 'Prefix Listing', 'Lifecycle Rules'],
    popular: false,
    permissions: ['Upload and manage objects', 'List bucket contents', 'Create signed URLs'],
    setupSteps: [
      'Open Google Cloud Console → Cloud Storage → Settings → Interoperability',
      'Under "Access keys for your user account", click Create a key',
      'Copy the Access Key and Secret',
      'Enter them with your bucket name below',
    ],
    apiKeyFields: [
      { name: 'access_key_id', label: 'HMAC Access Key', type: 'text', required: true },
      { name: 'secret_access_key', label: 'HMAC Secret', type: 'password', required: true },
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
  // ── Email (SMTP) ──────────────────────────────────────────────────────────
  // One backend connector with three presets. Gmail and Outlook prefill host
  // and port; Custom SMTP asks for them. All three need an *app password*
  // rather than the account password whenever 2FA is on — both providers
  // reject the account password with "username and password not accepted",
  // which sends people looking for the wrong problem.
  gmail: {
    slug: 'gmail', name: 'Gmail SMTP', icon: '📧',
    description: 'Send email from your Gmail account during and after calls',
    category: 'email', authType: 'api_key',
    features: ['Send Email', 'HTML Bodies', 'CC & Reply-To'],
    popular: false,
    permissions: ['Send email as your Gmail address'],
    setupSteps: [
      'Make sure 2-Step Verification is on for your Google account',
      'Go to myaccount.google.com/apppasswords and create an app password for "Mail"',
      'Enter your Gmail address and that 16-character app password below',
      'Your normal Google password will not work here',
    ],
    apiKeyFields: [
      { name: 'username', label: 'Gmail Address', type: 'text', required: true },
      { name: 'password', label: 'App Password', type: 'password', required: true },
      { name: 'from_name', label: 'From Name (optional)', type: 'text', required: false },
    ],
  },
  outlook: {
    slug: 'outlook', name: 'Outlook SMTP', icon: '📨',
    description: 'Send email from your Outlook or Microsoft 365 account',
    category: 'email', authType: 'api_key',
    features: ['Send Email', 'HTML Bodies', 'CC & Reply-To'],
    popular: false,
    permissions: ['Send email as your Outlook address'],
    setupSteps: [
      'Go to account.microsoft.com/security → Advanced security options',
      'Create an app password under "App passwords"',
      'Enter your Outlook address and that app password below',
      'If your organisation has disabled SMTP AUTH, an admin must enable it first',
    ],
    apiKeyFields: [
      { name: 'username', label: 'Outlook Address', type: 'text', required: true },
      { name: 'password', label: 'App Password', type: 'password', required: true },
      { name: 'from_name', label: 'From Name (optional)', type: 'text', required: false },
    ],
  },
  'custom-smtp': {
    slug: 'custom-smtp', name: 'Custom SMTP', icon: '✉️',
    description: 'Send email through any SMTP server you control',
    category: 'email', authType: 'api_key',
    features: ['Send Email', 'HTML Bodies', 'CC & Reply-To', 'Any Provider'],
    popular: false,
    permissions: ['Send email through your SMTP server'],
    setupSteps: [
      'Find your provider\u2019s SMTP host and port',
      'Port 587 uses STARTTLS; port 465 uses implicit SSL — we pick the right one from the port',
      'Enter the host, port, username and password below',
    ],
    apiKeyFields: [
      { name: 'host', label: 'SMTP Host (e.g. smtp.mailgun.org)', type: 'text', required: true },
      { name: 'port', label: 'Port (587 or 465)', type: 'text', required: true },
      { name: 'username', label: 'Username', type: 'text', required: true },
      { name: 'password', label: 'Password', type: 'password', required: true },
      { name: 'from_email', label: 'From Address (defaults to username)', type: 'text', required: false },
      { name: 'from_name', label: 'From Name (optional)', type: 'text', required: false },
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
  clickup: {
    slug: 'clickup', name: 'ClickUp', icon: '✅',
    description: 'Create and manage ClickUp tasks from voice calls and workflows',
    category: 'productivity', authType: 'oauth2',
    features: ['Create Tasks', 'List Tasks', 'Comments', 'Workspaces & Lists'],
    popular: true,
    permissions: ['Access selected workspace', 'Read and write tasks'],
    setupSteps: ['Click "Connect with ClickUp"', 'Choose your workspace', 'Authorize', 'Done'],
  },
  trello: {
    slug: 'trello', name: 'Trello', icon: '📋',
    description: 'Create and manage Trello cards, lists, and boards from voice calls',
    category: 'productivity', authType: 'oauth2',
    features: ['Create Cards', 'List Boards & Lists', 'Comments', 'Update Cards'],
    popular: false,
    permissions: ['Read your boards', 'Create and update cards'],
    setupSteps: ['Click "Connect with Trello"', 'Approve access on Trello', 'Done'],
  },
  whatsapp: {
    slug: 'whatsapp', name: 'WhatsApp', icon: '💬',
    description: 'Send WhatsApp messages via the WhatsApp Business Cloud API (your own number)',
    category: 'communication', authType: 'api_key',
    features: ['Send Messages', 'Message Templates', 'Business Cloud API'],
    popular: true,
    permissions: ['Send messages from your WhatsApp Business number'],
    setupSteps: [
      'In Meta Business → WhatsApp, get your Phone Number ID',
      'Generate a permanent access token (System User)',
      'Paste the Access Token and Phone Number ID below',
      'Test by sending a message',
    ],
    apiKeyFields: [
      { name: 'access_token', label: 'Access Token', type: 'password', required: true },
      { name: 'phone_number_id', label: 'Phone Number ID', type: 'text', required: true },
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
  const [iconFailed, setIconFailed] = useState(false)

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
          (c: ApiConnection) => c.connector?.slug === slug && c.status !== 'disconnected'
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
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 bg-white border border-slate-200 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm overflow-hidden">
              {getIconUrl(integration.slug) && !iconFailed ? (
                <img
                  src={getIconUrl(integration.slug)!}
                  alt={integration.name}
                  className="w-10 h-10 object-contain"
                  onError={() => setIconFailed(true)}
                />
              ) : (
                <span className="text-3xl leading-none">
                  {integration.icon || integration.name.slice(0, 2).toUpperCase()}
                </span>
              )}
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

      {/* Asked once, here, so no workflow ever has to. Only shown after the
          integration is connected — there is nothing to list before that. */}
      {existingConnectionId && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white shadow-sm">
          <ConnectionDefaults connectionId={existingConnectionId} />
        </div>
      )}
    </div>
  )
}
