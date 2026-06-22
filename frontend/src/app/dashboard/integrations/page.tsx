'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Filter, CheckCircle, Clock, XCircle } from 'lucide-react';
import { IntegrationCard } from '@/components/integrations/IntegrationCard';

import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api';
import { API_ENDPOINTS } from '@/lib/constants';

interface Integration {
  id: string;
  slug: string;
  name: string;
  description: string;
  category: 'crm' | 'calendar' | 'communication' | 'productivity' | 'analytics' | 'phone' | 'cloud' | 'other';
  icon: string;
  authType: 'oauth2' | 'api_key' | 'basic';
  status?: 'connected' | 'error' | 'pending' | null;
  connectedAt?: string;
  features: string[];
  popular: boolean;
}

interface ApiConnection {
  id: string;
  status: string;
  connector: { slug: string };
  created_at: string;
}

// Static catalog — icons, features, and metadata that aren't stored in the DB
const integrationCatalog: Integration[] = [
  // CRM
  { id: '1',  slug: 'salesforce',      name: 'Salesforce',          description: 'Sync contacts, leads, and opportunities with Salesforce CRM',              category: 'crm',           icon: '🔷', authType: 'oauth2',   features: ['Contact Sync', 'Lead Management', 'Opportunity Tracking', 'Custom Fields'],      popular: true },
  { id: '2',  slug: 'hubspot',         name: 'HubSpot',             description: 'Connect HubSpot CRM to manage contacts and track customer interactions',    category: 'crm',           icon: '🟠', authType: 'oauth2',   features: ['Contact Management', 'Deal Pipeline', 'Email Tracking', 'Analytics'],          popular: true },
  { id: '3',  slug: 'pipedrive',       name: 'Pipedrive',           description: 'Sales pipeline CRM to track deals and contacts from voice calls',          category: 'crm',           icon: '🟢', authType: 'oauth2',   features: ['Deal Tracking', 'Contact Sync', 'Pipeline Management', 'Activity Logging'],   popular: false },
  { id: '4',  slug: 'zendesk',         name: 'Zendesk',             description: 'Create and update support tickets from voice interactions',                 category: 'crm',           icon: '🎫', authType: 'oauth2',   features: ['Ticket Management', 'Customer Profiles', 'Automation', 'Reporting'],          popular: false },
  { id: '5',  slug: 'intercom',        name: 'Intercom',            description: 'Create conversations and update contacts in Intercom from calls',          category: 'crm',           icon: '💬', authType: 'oauth2',   features: ['Conversation Sync', 'Contact Management', 'Notes & Tags', 'Event Tracking'],  popular: false },
  // Calendar
  { id: '6',  slug: 'google-calendar', name: 'Google Calendar',     description: 'Schedule appointments and manage events from voice conversations',         category: 'calendar',      icon: '📅', authType: 'oauth2',   features: ['Event Creation', 'Availability Check', 'Reminders', 'Multi-Calendar'],       popular: true },
  { id: '7',  slug: 'calendly',        name: 'Calendly',            description: 'Book appointments using your Calendly scheduling links',                   category: 'calendar',      icon: '🗓️', authType: 'oauth2',   features: ['Meeting Scheduling', 'Availability Sync', 'Custom Links', 'Reminders'],      popular: false },
  { id: '8',  slug: 'cal-com',         name: 'Cal.com',             description: 'Open-source scheduling — book meetings directly from voice calls',         category: 'calendar',      icon: '📆', authType: 'api_key',  features: ['Meeting Scheduling', 'Custom Event Types', 'Team Scheduling', 'Webhooks'],   popular: false },
  // Communication
  { id: '9',  slug: 'slack',           name: 'Slack',               description: 'Send notifications and updates to your Slack channels',                    category: 'communication', icon: '💬', authType: 'oauth2',   features: ['Channel Messages', 'Direct Messages', 'File Sharing', 'Webhooks'],           popular: true },
  { id: '10', slug: 'microsoft-teams', name: 'Microsoft Teams',     description: 'Send messages and notifications to Teams channels',                        category: 'communication', icon: '👥', authType: 'oauth2',   features: ['Channel Messages', 'Chat', 'File Sharing', 'Meeting Integration'],           popular: false },
  { id: '11', slug: 'twilio',          name: 'Twilio',              description: 'Enhanced telephony features and SMS capabilities',                         category: 'communication', icon: '📞', authType: 'api_key',  features: ['Voice Calls', 'SMS', 'WhatsApp', 'Call Recording'],                         popular: false },
  { id: '12', slug: 'sendgrid',        name: 'SendGrid',            description: 'Send transactional emails from voice conversations',                       category: 'communication', icon: '✉️', authType: 'api_key',  features: ['Transactional Email', 'Templates', 'Analytics', 'List Management'],         popular: false },
  // Productivity
  { id: '13', slug: 'zapier',          name: 'Zapier',              description: 'Connect to 5000+ apps through Zapier automation',                          category: 'productivity',  icon: '⚡', authType: 'oauth2',   features: ['Workflow Automation', 'Custom Triggers', 'Multi-Step Zaps', 'Webhooks'],    popular: true },
  { id: '14', slug: 'make',            name: 'Make (Integromat)',   description: 'Visual automation platform — connect Voicecon to any app',                category: 'productivity',  icon: '🔧', authType: 'api_key',  features: ['Visual Automation', 'Webhooks', '1000+ Apps', 'Data Mapping'],              popular: false },
  { id: '15', slug: 'google-sheets',   name: 'Google Sheets',       description: 'Log call data and customer information to spreadsheets',                   category: 'productivity',  icon: '📊', authType: 'oauth2',   features: ['Data Logging', 'Real-time Updates', 'Custom Columns', 'Formulas'],          popular: false },
  { id: '16', slug: 'google-drive',    name: 'Google Drive',        description: 'Save call recordings and transcripts to Google Drive',                    category: 'productivity',  icon: '💾', authType: 'oauth2',   features: ['File Upload', 'Folder Organization', 'Sharing', 'Search'],                 popular: false },
  { id: '17', slug: 'airtable',        name: 'Airtable',            description: 'Store and organize conversation data in flexible databases',               category: 'productivity',  icon: '🗂️', authType: 'api_key',  features: ['Database Sync', 'Custom Fields', 'Views', 'Automation'],                    popular: false },
  // Payment
  { id: '18', slug: 'stripe',          name: 'Stripe',              description: 'Process payments and manage subscriptions during calls',                   category: 'other',         icon: '💳', authType: 'api_key',  features: ['Payment Processing', 'Subscription Management', 'Invoicing', 'Webhooks'],  popular: true },
  // CRM (extended)
  { id: '19', slug: 'gohighlevel',     name: 'GoHighLevel',         description: 'All-in-one CRM — sync contacts, pipelines, and SMS from voice calls',     category: 'crm',           icon: '🚀', authType: 'api_key',  features: ['Contact Sync', 'Pipeline Management', 'SMS Campaigns', 'Appointment Booking'], popular: true },
  { id: '20', slug: 'notion',          name: 'Notion',              description: 'Create and update Notion pages and databases from voice conversations',    category: 'productivity',  icon: '📝', authType: 'oauth2',   features: ['Page Creation', 'Database Updates', 'Notes', 'Task Tracking'],              popular: false },
  { id: '21', slug: 'monday',          name: 'Monday.com',          description: 'Update boards and items in Monday.com from call outcomes',                 category: 'productivity',  icon: '📋', authType: 'oauth2',   features: ['Board Updates', 'Item Creation', 'Status Tracking', 'Automations'],         popular: false },
  // Phone Providers
  { id: '22', slug: 'telnyx',          name: 'Telnyx',              description: 'Carrier-grade VoIP and SIP trunking for voice AI deployments',             category: 'phone',         icon: '📱', authType: 'api_key',  features: ['SIP Trunking', 'Phone Numbers', 'SMS', 'Call Control API'],                popular: true },
  { id: '23', slug: 'vonage',          name: 'Vonage (Nexmo)',      description: 'Global cloud communications — calls, SMS, and phone number management',   category: 'phone',         icon: '☎️', authType: 'api_key',  features: ['Voice Calls', 'SMS', 'Phone Numbers', 'WebRTC'],                           popular: false },
  // Analytics / Observability
  { id: '24', slug: 'langfuse',        name: 'Langfuse',            description: 'Open-source LLM observability — trace, evaluate, and debug AI calls',    category: 'analytics',     icon: '🔭', authType: 'api_key',  features: ['LLM Tracing', 'Prompt Management', 'Evaluation', 'Cost Tracking'],        popular: true },
  // Cloud Storage
  { id: '25', slug: 'aws-s3',          name: 'AWS S3',              description: 'Store call recordings, transcripts, and files in Amazon S3 buckets',      category: 'cloud',         icon: '🪣', authType: 'api_key',  features: ['File Storage', 'Bucket Management', 'CDN', 'Access Control'],             popular: true },
  { id: '26', slug: 'azure-blob',      name: 'Azure Blob Storage',  description: 'Store and manage call data in Microsoft Azure Blob Storage',              category: 'cloud',         icon: '🔵', authType: 'api_key',  features: ['Blob Storage', 'Container Management', 'SAS Tokens', 'Access Tiers'],     popular: false },
  { id: '27', slug: 'gcs',             name: 'Google Cloud Storage',description: 'Store recordings and data in Google Cloud Storage buckets',               category: 'cloud',         icon: '☁️', authType: 'api_key',  features: ['Object Storage', 'Bucket Policies', 'Lifecycle Rules', 'CDN Integration'], popular: false },
  { id: '28', slug: 'cloudflare-r2',   name: 'Cloudflare R2',       description: 'Zero-egress object storage for recordings and call artifacts',            category: 'cloud',         icon: '🔶', authType: 'api_key',  features: ['Object Storage', 'Zero Egress Fees', 'S3-compatible API', 'Global CDN'],  popular: false },
  { id: '29', slug: 'supabase',        name: 'Supabase',            description: 'Open-source Firebase alternative — store call data in Postgres',          category: 'cloud',         icon: '⚡', authType: 'api_key',  features: ['Postgres Database', 'Realtime', 'Storage', 'Edge Functions'],              popular: false },
];

const categories = [
  { id: 'all', name: 'All Integrations' },
  { id: 'crm', name: 'CRM' },
  { id: 'calendar', name: 'Calendar' },
  { id: 'communication', name: 'Communication' },
  { id: 'productivity', name: 'Productivity' },
  { id: 'phone', name: 'Phone Providers' },
  { id: 'cloud', name: 'Cloud Storage' },
  { id: 'analytics', name: 'Analytics' },
  { id: 'other', name: 'Payment' },
];

export default function IntegrationsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  // slug → { connectionId, status }
  const [connectionMap, setConnectionMap] = useState<
    Record<string, { connectionId: string; status: 'connected' | 'error' | 'pending' }>
  >({});
  const [loading, setLoading] = useState(true);

  const fetchConnections = useCallback(async () => {
    try {
      const res = await apiClient.get<{ connections: ApiConnection[]; total: number }>(
        API_ENDPOINTS.INTEGRATION_CONNECTIONS
      );
      const map: typeof connectionMap = {};
      for (const conn of res.data.connections) {
        const slug = conn.connector?.slug;
        if (!slug) continue;
        const s =
          conn.status === 'active'
            ? 'connected'
            : conn.status === 'error' || conn.status === 'expired'
            ? 'error'
            : 'pending';
        map[slug] = { connectionId: conn.id, status: s };
      }
      setConnectionMap(map);
    } catch {
      // API not available; fall back to empty — no localStorage
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const filteredIntegrations = integrationCatalog.filter((integration) => {
    const matchesSearch =
      integration.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      integration.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory =
      selectedCategory === 'all' || integration.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const sortedIntegrations = [...filteredIntegrations].sort((a, b) => {
    const aConnected = !!connectionMap[a.slug];
    const bConnected = !!connectionMap[b.slug];
    if (aConnected !== bConnected) return aConnected ? -1 : 1;
    if (a.popular !== b.popular) return a.popular ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  const categoriesWithCount = categories.map((cat) => ({
    ...cat,
    count:
      cat.id === 'all'
        ? integrationCatalog.length
        : integrationCatalog.filter((i) => i.category === cat.id).length,
  }));

  const connectedCount = Object.keys(connectionMap).length;
  const errorCount = Object.values(connectionMap).filter((c) => c.status === 'error').length;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Integrations</h1>
          <p className="text-slate-500 mt-1">
            Connect your favorite tools to enhance your voice AI capabilities
          </p>
        </div>
        <button
          onClick={() => router.push('/dashboard/integrations/connected')}
          className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
        >
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          View Connected ({loading ? '…' : connectedCount})
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center flex-shrink-0">
            <CheckCircle className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500 font-medium">Connected</p>
            <p className="text-2xl font-bold text-slate-900">{loading ? '—' : connectedCount}</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center flex-shrink-0">
            <Clock className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500 font-medium">Available</p>
            <p className="text-2xl font-bold text-slate-900">{loading ? '—' : integrationCatalog.length - connectedCount}</p>
          </div>
        </div>
        {errorCount > 0 && (
          <div className="bg-white rounded-xl border border-red-200 shadow-sm p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-red-50 border border-red-100 flex items-center justify-center flex-shrink-0">
              <XCircle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500 font-medium">Errors</p>
              <p className="text-2xl font-bold text-red-600">{errorCount}</p>
            </div>
          </div>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <Input
          type="text"
          placeholder="Search integrations..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 bg-white border-slate-200"
        />
      </div>

      {/* Body: sidebar + grid */}
      <div className="flex gap-6 items-start">
        {/* Category sidebar */}
        <div className="w-56 flex-shrink-0">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-3 sticky top-6">
            <div className="flex items-center gap-2 text-slate-700 mb-3 px-1">
              <Filter className="w-4 h-4" />
              <h3 className="font-semibold text-sm">Categories</h3>
            </div>
            <div className="space-y-0.5">
              {categoriesWithCount.map((category) => (
                <button
                  key={category.id}
                  onClick={() => setSelectedCategory(category.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all font-medium ${
                    selectedCategory === category.id
                      ? 'gradient-primary text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span>{category.name}</span>
                    <span className={`text-xs ${selectedCategory === category.id ? 'text-blue-100' : 'text-slate-400'}`}>
                      {category.count}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Integration grid */}
        <div className="flex-1 min-w-0">
          {sortedIntegrations.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {sortedIntegrations.map((integration) => {
                const conn = connectionMap[integration.slug];
                return (
                  <IntegrationCard
                    key={integration.id}
                    integration={{
                      ...integration,
                      status: conn ? conn.status : null,
                    }}
                    onConnect={() => router.push(`/dashboard/integrations/${integration.slug}`)}
                  />
                );
              })}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
              <Search className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-slate-900 mb-1">No integrations found</h3>
              <p className="text-sm text-slate-500">Try adjusting your search or filter</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
