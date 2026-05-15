'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { IntegrationSetup } from '@/components/integrations/IntegrationSetup';

// This would come from an API in production
const integrationData: Record<string, any> = {
  salesforce: {
    id: '1',
    slug: 'salesforce',
    name: 'Salesforce',
    description: 'Sync contacts, leads, and opportunities with your Salesforce CRM',
    category: 'crm',
    icon: '🔷',
    authType: 'oauth2',
    features: ['Contact Sync', 'Lead Management', 'Opportunity Tracking', 'Custom Fields'],
    popular: true,
    permissions: [
      'Read and write contacts',
      'Read and write leads',
      'Read and write opportunities',
      'Read custom objects',
      'Access user information',
    ],
    scopes: ['api', 'refresh_token', 'full'],
    oauthUrl: 'https://login.salesforce.com/services/oauth2/authorize',
    setupSteps: [
      'Click "Connect" to authorize Voicecon',
      'Sign in to your Salesforce account',
      'Review and approve the requested permissions',
      'You will be redirected back to complete the setup',
    ],
  },
  hubspot: {
    id: '2',
    slug: 'hubspot',
    name: 'HubSpot',
    description: 'Connect your HubSpot CRM to manage contacts and track customer interactions',
    category: 'crm',
    icon: '🟠',
    authType: 'oauth2',
    features: ['Contact Management', 'Deal Pipeline', 'Email Tracking', 'Analytics'],
    popular: true,
    permissions: [
      'Read and write contacts',
      'Read and write deals',
      'Read and write companies',
      'Access timeline events',
    ],
    scopes: ['contacts', 'crm.objects.deals.read', 'crm.objects.deals.write', 'timeline'],
    oauthUrl: 'https://app.hubspot.com/oauth/authorize',
    setupSteps: [
      'Click "Connect" to start OAuth flow',
      'Select your HubSpot account',
      'Grant the requested permissions',
      'Return to Voicecon to complete setup',
    ],
  },
  'google-calendar': {
    id: '3',
    slug: 'google-calendar',
    name: 'Google Calendar',
    description: 'Schedule appointments and manage events directly from voice conversations',
    category: 'calendar',
    icon: '📅',
    authType: 'oauth2',
    features: ['Event Creation', 'Availability Check', 'Reminders', 'Multi-Calendar'],
    popular: true,
    permissions: [
      'View and manage your calendars',
      'Create and edit events',
      'See event details',
      'Set event reminders',
    ],
    scopes: ['https://www.googleapis.com/auth/calendar'],
    oauthUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    setupSteps: [
      'Click "Connect with Google"',
      'Choose your Google account',
      'Allow Voicecon to access your calendars',
      'Configure which calendars to use',
    ],
  },
  slack: {
    id: '4',
    slug: 'slack',
    name: 'Slack',
    description: 'Send notifications and updates to your Slack channels',
    category: 'communication',
    icon: '💬',
    authType: 'oauth2',
    features: ['Channel Messages', 'Direct Messages', 'File Sharing', 'Webhooks'],
    popular: true,
    permissions: [
      'Send messages to channels',
      'Send direct messages',
      'Upload files',
      'Read channel information',
    ],
    scopes: ['chat:write', 'files:write', 'channels:read', 'users:read'],
    oauthUrl: 'https://slack.com/oauth/v2/authorize',
    setupSteps: [
      'Click "Add to Slack"',
      'Select your workspace',
      'Choose which channels to use',
      'Authorize the Voicecon app',
    ],
  },
  twilio: {
    id: '5',
    slug: 'twilio',
    name: 'Twilio',
    description: 'Enhanced telephony features and SMS capabilities',
    category: 'communication',
    icon: '📞',
    authType: 'api_key',
    features: ['Voice Calls', 'SMS', 'WhatsApp', 'Call Recording'],
    popular: false,
    permissions: [
      'Make and receive calls',
      'Send and receive SMS',
      'Access call logs',
      'Manage phone numbers',
    ],
    setupSteps: [
      'Get your Account SID from Twilio Console',
      'Generate an Auth Token',
      'Enter credentials below',
      'Test the connection',
    ],
    apiKeyFields: [
      { name: 'account_sid', label: 'Account SID', type: 'text', required: true },
      { name: 'auth_token', label: 'Auth Token', type: 'password', required: true },
      { name: 'phone_number', label: 'Phone Number (optional)', type: 'text', required: false },
    ],
  },
  zapier: {
    id: '6',
    slug: 'zapier',
    name: 'Zapier',
    description: 'Connect to 5000+ apps through Zapier automation',
    category: 'productivity',
    icon: '⚡',
    authType: 'oauth2',
    features: ['Workflow Automation', 'Custom Triggers', 'Multi-Step Zaps', 'Webhooks'],
    popular: true,
    permissions: [
      'Create and manage Zaps',
      'Trigger automation workflows',
      'Access connected apps',
    ],
    scopes: ['zap:read', 'zap:write'],
    oauthUrl: 'https://zapier.com/oauth/authorize',
    setupSteps: [
      'Connect your Zapier account',
      'Create Zaps using Voicecon triggers',
      'Configure automation workflows',
      'Test your Zaps',
    ],
  },
  'google-sheets': {
    id: '7',
    slug: 'google-sheets',
    name: 'Google Sheets',
    description: 'Log call data and customer information to spreadsheets',
    category: 'productivity',
    icon: '📊',
    authType: 'oauth2',
    features: ['Data Logging', 'Real-time Updates', 'Custom Columns', 'Formulas'],
    popular: false,
    permissions: [
      'Create and edit spreadsheets',
      'Read spreadsheet data',
      'Manage spreadsheet formatting',
    ],
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    oauthUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    setupSteps: [
      'Authorize Google Sheets access',
      'Select or create a spreadsheet',
      'Map data fields to columns',
      'Configure update frequency',
    ],
  },
  airtable: {
    id: '8',
    slug: 'airtable',
    name: 'Airtable',
    description: 'Store and organize conversation data in flexible databases',
    category: 'productivity',
    icon: '🗂️',
    authType: 'api_key',
    features: ['Database Sync', 'Custom Fields', 'Views', 'Automation'],
    popular: false,
    permissions: [
      'Read and write records',
      'Access base structure',
      'Manage fields and tables',
    ],
    setupSteps: [
      'Copy your Airtable API key',
      'Enter your Base ID',
      'Paste credentials below',
      'Select tables to sync',
    ],
    apiKeyFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'base_id', label: 'Base ID', type: 'text', required: true },
    ],
  },
  stripe: {
    id: '9',
    slug: 'stripe',
    name: 'Stripe',
    description: 'Process payments and manage subscriptions during calls',
    category: 'other',
    icon: '💳',
    authType: 'api_key',
    features: ['Payment Processing', 'Subscription Management', 'Invoicing', 'Webhooks'],
    popular: true,
    permissions: [
      'Process payments',
      'Manage customers',
      'Create and update subscriptions',
      'Access payment data',
    ],
    setupSteps: [
      'Get your Stripe API keys',
      'Enter Secret Key below',
      'Configure webhook endpoints',
      'Test payment processing',
    ],
    apiKeyFields: [
      { name: 'secret_key', label: 'Secret Key', type: 'password', required: true },
      { name: 'publishable_key', label: 'Publishable Key', type: 'text', required: true },
    ],
  },
  calendly: {
    id: '10',
    slug: 'calendly',
    name: 'Calendly',
    description: 'Book appointments using your Calendly scheduling links',
    category: 'calendar',
    icon: '🗓️',
    authType: 'oauth2',
    features: ['Meeting Scheduling', 'Availability Sync', 'Custom Links', 'Reminders'],
    popular: false,
    permissions: [
      'Access your event types',
      'Schedule meetings',
      'View availability',
      'Manage invitees',
    ],
    scopes: ['default'],
    oauthUrl: 'https://auth.calendly.com/oauth/authorize',
    setupSteps: [
      'Connect your Calendly account',
      'Select event types to use',
      'Configure scheduling preferences',
      'Test booking flow',
    ],
  },
  zendesk: {
    id: '11',
    slug: 'zendesk',
    name: 'Zendesk',
    description: 'Create and update support tickets from voice interactions',
    category: 'crm',
    icon: '🎫',
    authType: 'oauth2',
    features: ['Ticket Management', 'Customer Profiles', 'Automation', 'Reporting'],
    popular: false,
    permissions: [
      'Create and update tickets',
      'Read user information',
      'Access ticket history',
      'Manage ticket status',
    ],
    scopes: ['tickets:write', 'users:read', 'organizations:read'],
    oauthUrl: 'https://your-subdomain.zendesk.com/oauth/authorizations/new',
    setupSteps: [
      'Enter your Zendesk subdomain',
      'Authorize Voicecon',
      'Configure ticket fields',
      'Set up automation rules',
    ],
  },
  'microsoft-teams': {
    id: '12',
    slug: 'microsoft-teams',
    name: 'Microsoft Teams',
    description: 'Send messages and notifications to Teams channels',
    category: 'communication',
    icon: '👥',
    authType: 'oauth2',
    features: ['Channel Messages', 'Chat', 'File Sharing', 'Meeting Integration'],
    popular: false,
    permissions: [
      'Send channel messages',
      'Send chat messages',
      'Read team information',
      'Access user profile',
    ],
    scopes: ['ChannelMessage.Send', 'Chat.ReadWrite', 'Team.ReadBasic.All'],
    oauthUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
    setupSteps: [
      'Sign in with your Microsoft account',
      'Select your organization',
      'Grant permissions to Teams',
      'Choose channels to use',
    ],
  },
};

export default function IntegrationDetailPage() {
  const router = useRouter();
  const params = useParams();
  const slug = params?.slug as string;

  const [integration, setIntegration] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In production, fetch from API
    const data = integrationData[slug];
    if (data) {
      setIntegration(data);
    }
    setLoading(false);
  }, [slug]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading integration...</p>
        </div>
      </div>
    );
  }

  if (!integration) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Integration Not Found</h2>
          <p className="text-gray-600 mb-6">
            The integration you&apos;re looking for doesn&apos;t exist.
          </p>
          <Button onClick={() => router.push('/dashboard/integrations')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Integrations
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-6 py-6">
          <Button
            variant="ghost"
            onClick={() => router.push('/dashboard/integrations')}
            className="mb-4 gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Integrations
          </Button>

          <div className="flex items-start gap-4">
            <div className="w-16 h-16 bg-gradient-to-br from-gray-100 to-gray-200 rounded-xl flex items-center justify-center text-3xl">
              {integration.icon}
            </div>
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">{integration.name}</h1>
              <p className="text-gray-600">{integration.description}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Setup Component */}
      <div className="max-w-4xl mx-auto px-6 py-8">
        <IntegrationSetup integration={integration} />
      </div>
    </div>
  );
}
