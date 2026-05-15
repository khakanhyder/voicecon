'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Filter, CheckCircle, Clock, XCircle } from 'lucide-react';
import { IntegrationCard } from '@/components/integrations/IntegrationCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface Integration {
  id: string;
  slug: string;
  name: string;
  description: string;
  category: 'crm' | 'calendar' | 'communication' | 'productivity' | 'analytics' | 'other';
  icon: string;
  authType: 'oauth2' | 'api_key' | 'basic';
  status?: 'connected' | 'error' | 'pending' | null;
  connectedAt?: string;
  features: string[];
  popular: boolean;
}

const integrations: Integration[] = [
  {
    id: '1',
    slug: 'salesforce',
    name: 'Salesforce',
    description: 'Sync contacts, leads, and opportunities with your Salesforce CRM',
    category: 'crm',
    icon: '🔷',
    authType: 'oauth2',
    features: ['Contact Sync', 'Lead Management', 'Opportunity Tracking', 'Custom Fields'],
    popular: true,
  },
  {
    id: '2',
    slug: 'hubspot',
    name: 'HubSpot',
    description: 'Connect your HubSpot CRM to manage contacts and track customer interactions',
    category: 'crm',
    icon: '🟠',
    authType: 'oauth2',
    features: ['Contact Management', 'Deal Pipeline', 'Email Tracking', 'Analytics'],
    popular: true,
  },
  {
    id: '3',
    slug: 'google-calendar',
    name: 'Google Calendar',
    description: 'Schedule appointments and manage events directly from voice conversations',
    category: 'calendar',
    icon: '📅',
    authType: 'oauth2',
    features: ['Event Creation', 'Availability Check', 'Reminders', 'Multi-Calendar'],
    popular: true,
  },
  {
    id: '4',
    slug: 'slack',
    name: 'Slack',
    description: 'Send notifications and updates to your Slack channels',
    category: 'communication',
    icon: '💬',
    authType: 'oauth2',
    features: ['Channel Messages', 'Direct Messages', 'File Sharing', 'Webhooks'],
    popular: true,
  },
  {
    id: '5',
    slug: 'twilio',
    name: 'Twilio',
    description: 'Enhanced telephony features and SMS capabilities',
    category: 'communication',
    icon: '📞',
    authType: 'api_key',
    features: ['Voice Calls', 'SMS', 'WhatsApp', 'Call Recording'],
    popular: false,
  },
  {
    id: '6',
    slug: 'zapier',
    name: 'Zapier',
    description: 'Connect to 5000+ apps through Zapier automation',
    category: 'productivity',
    icon: '⚡',
    authType: 'oauth2',
    features: ['Workflow Automation', 'Custom Triggers', 'Multi-Step Zaps', 'Webhooks'],
    popular: true,
  },
  {
    id: '7',
    slug: 'google-sheets',
    name: 'Google Sheets',
    description: 'Log call data and customer information to spreadsheets',
    category: 'productivity',
    icon: '📊',
    authType: 'oauth2',
    features: ['Data Logging', 'Real-time Updates', 'Custom Columns', 'Formulas'],
    popular: false,
  },
  {
    id: '8',
    slug: 'airtable',
    name: 'Airtable',
    description: 'Store and organize conversation data in flexible databases',
    category: 'productivity',
    icon: '🗂️',
    authType: 'api_key',
    features: ['Database Sync', 'Custom Fields', 'Views', 'Automation'],
    popular: false,
  },
  {
    id: '9',
    slug: 'stripe',
    name: 'Stripe',
    description: 'Process payments and manage subscriptions during calls',
    category: 'other',
    icon: '💳',
    authType: 'api_key',
    features: ['Payment Processing', 'Subscription Management', 'Invoicing', 'Webhooks'],
    popular: true,
  },
  {
    id: '10',
    slug: 'calendly',
    name: 'Calendly',
    description: 'Book appointments using your Calendly scheduling links',
    category: 'calendar',
    icon: '🗓️',
    authType: 'oauth2',
    features: ['Meeting Scheduling', 'Availability Sync', 'Custom Links', 'Reminders'],
    popular: false,
  },
  {
    id: '11',
    slug: 'zendesk',
    name: 'Zendesk',
    description: 'Create and update support tickets from voice interactions',
    category: 'crm',
    icon: '🎫',
    authType: 'oauth2',
    features: ['Ticket Management', 'Customer Profiles', 'Automation', 'Reporting'],
    popular: false,
  },
  {
    id: '12',
    slug: 'microsoft-teams',
    name: 'Microsoft Teams',
    description: 'Send messages and notifications to Teams channels',
    category: 'communication',
    icon: '👥',
    authType: 'oauth2',
    features: ['Channel Messages', 'Chat', 'File Sharing', 'Meeting Integration'],
    popular: false,
  },
];

const categories = [
  { id: 'all', name: 'All Integrations', count: integrations.length },
  { id: 'crm', name: 'CRM', count: integrations.filter((i) => i.category === 'crm').length },
  {
    id: 'calendar',
    name: 'Calendar',
    count: integrations.filter((i) => i.category === 'calendar').length,
  },
  {
    id: 'communication',
    name: 'Communication',
    count: integrations.filter((i) => i.category === 'communication').length,
  },
  {
    id: 'productivity',
    name: 'Productivity',
    count: integrations.filter((i) => i.category === 'productivity').length,
  },
  {
    id: 'analytics',
    name: 'Analytics',
    count: integrations.filter((i) => i.category === 'analytics').length,
  },
];

export default function IntegrationsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [connectedIntegrations, setConnectedIntegrations] = useState<Set<string>>(new Set());
  const [integrationStatuses, setIntegrationStatuses] = useState<
    Record<string, 'connected' | 'error' | 'pending'>
  >({});

  // Load connected integrations from localStorage (in production, fetch from API)
  useEffect(() => {
    const connected = localStorage.getItem('connected_integrations');
    if (connected) {
      try {
        const parsed = JSON.parse(connected);
        setConnectedIntegrations(new Set(parsed));
      } catch (error) {
        console.error('Error parsing connected integrations:', error);
      }
    }

    const statuses = localStorage.getItem('integration_statuses');
    if (statuses) {
      try {
        setIntegrationStatuses(JSON.parse(statuses));
      } catch (error) {
        console.error('Error parsing integration statuses:', error);
      }
    }
  }, []);

  const filteredIntegrations = integrations.filter((integration) => {
    const matchesSearch =
      integration.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      integration.description.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory =
      selectedCategory === 'all' || integration.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  // Sort: popular first, then connected, then alphabetical
  const sortedIntegrations = [...filteredIntegrations].sort((a, b) => {
    // Connected integrations first
    const aConnected = connectedIntegrations.has(a.slug);
    const bConnected = connectedIntegrations.has(b.slug);
    if (aConnected !== bConnected) return aConnected ? -1 : 1;

    // Then popular integrations
    if (a.popular !== b.popular) return a.popular ? -1 : 1;

    // Then alphabetical
    return a.name.localeCompare(b.name);
  });

  const handleConnect = (slug: string) => {
    router.push(`/dashboard/integrations/${slug}`);
  };

  const connectedCount = connectedIntegrations.size;
  const errorCount = Object.values(integrationStatuses).filter((s) => s === 'error').length;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex items-start justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Integrations</h1>
              <p className="text-gray-600">
                Connect your favorite tools to enhance your voice AI capabilities
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => router.push('/dashboard/integrations/connected')}
              className="gap-2"
            >
              <CheckCircle className="w-4 h-4" />
              View Connected ({connectedCount})
            </Button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-green-700 mb-1">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm font-medium">Connected</span>
              </div>
              <div className="text-2xl font-bold text-green-900">{connectedCount}</div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-blue-700 mb-1">
                <Clock className="w-5 h-5" />
                <span className="text-sm font-medium">Available</span>
              </div>
              <div className="text-2xl font-bold text-blue-900">
                {integrations.length - connectedCount}
              </div>
            </div>
            {errorCount > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-red-700 mb-1">
                  <XCircle className="w-5 h-5" />
                  <span className="text-sm font-medium">Errors</span>
                </div>
                <div className="text-2xl font-bold text-red-900">{errorCount}</div>
              </div>
            )}
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <Input
              type="text"
              placeholder="Search integrations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex gap-8">
          {/* Sidebar - Categories */}
          <div className="w-64 flex-shrink-0">
            <div className="bg-white border rounded-lg p-4 sticky top-6">
              <div className="flex items-center gap-2 text-gray-700 mb-4">
                <Filter className="w-4 h-4" />
                <h3 className="font-semibold">Categories</h3>
              </div>
              <div className="space-y-1">
                {categories.map((category) => (
                  <button
                    key={category.id}
                    onClick={() => setSelectedCategory(category.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                      selectedCategory === category.id
                        ? 'bg-indigo-100 text-indigo-700 font-medium'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span>{category.name}</span>
                      <span className="text-sm text-gray-500">{category.count}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Integration Grid */}
          <div className="flex-1">
            {sortedIntegrations.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {sortedIntegrations.map((integration) => (
                  <IntegrationCard
                    key={integration.id}
                    integration={{
                      ...integration,
                      status: connectedIntegrations.has(integration.slug)
                        ? integrationStatuses[integration.slug] || 'connected'
                        : null,
                    }}
                    onConnect={() => handleConnect(integration.slug)}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-white border rounded-lg p-12 text-center">
                <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No integrations found
                </h3>
                <p className="text-gray-600">
                  Try adjusting your search or filter criteria
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
