'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Search, Settings, Trash2, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ConnectionStatus } from '@/components/integrations/ConnectionStatus';

interface ConnectedIntegration {
  slug: string;
  name: string;
  icon: string;
  category: string;
  connectedAt: string;
  status: 'connected' | 'error' | 'pending';
  lastSync?: string;
  authType: string;
}

const integrationMetadata: Record<string, { name: string; icon: string; category: string }> = {
  salesforce: { name: 'Salesforce', icon: '🔷', category: 'crm' },
  hubspot: { name: 'HubSpot', icon: '🟠', category: 'crm' },
  'google-calendar': { name: 'Google Calendar', icon: '📅', category: 'calendar' },
  slack: { name: 'Slack', icon: '💬', category: 'communication' },
  twilio: { name: 'Twilio', icon: '📞', category: 'communication' },
  zapier: { name: 'Zapier', icon: '⚡', category: 'productivity' },
  'google-sheets': { name: 'Google Sheets', icon: '📊', category: 'productivity' },
  airtable: { name: 'Airtable', icon: '🗂️', category: 'productivity' },
  stripe: { name: 'Stripe', icon: '💳', category: 'other' },
  calendly: { name: 'Calendly', icon: '🗓️', category: 'calendar' },
  zendesk: { name: 'Zendesk', icon: '🎫', category: 'crm' },
  'microsoft-teams': { name: 'Microsoft Teams', icon: '👥', category: 'communication' },
};

export default function ConnectedIntegrationsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [connectedIntegrations, setConnectedIntegrations] = useState<ConnectedIntegration[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConnectedIntegrations();
  }, []);

  const loadConnectedIntegrations = () => {
    setLoading(true);

    // Load from localStorage (in production, fetch from API)
    const connected = localStorage.getItem('connected_integrations');
    const statuses = JSON.parse(localStorage.getItem('integration_statuses') || '{}');

    if (connected) {
      try {
        const slugs = JSON.parse(connected);
        const integrations: ConnectedIntegration[] = slugs.map((slug: string) => {
          const connectionData = localStorage.getItem(`integration_${slug}`);
          const data = connectionData ? JSON.parse(connectionData) : {};
          const metadata = integrationMetadata[slug] || {
            name: slug,
            icon: '🔗',
            category: 'other',
          };

          return {
            slug,
            ...metadata,
            connectedAt: data.connectedAt || new Date().toISOString(),
            status: statuses[slug] || 'connected',
            lastSync: data.lastSync,
            authType: data.authType || 'oauth2',
          };
        });

        setConnectedIntegrations(integrations);
      } catch (error) {
        console.error('Error loading connected integrations:', error);
      }
    }

    setLoading(false);
  };

  const handleDisconnect = (slug: string) => {
    if (!confirm(`Are you sure you want to disconnect ${integrationMetadata[slug]?.name || slug}?`)) {
      return;
    }

    // Remove from connected integrations
    const connected = localStorage.getItem('connected_integrations');
    if (connected) {
      const connectedSet = new Set(JSON.parse(connected));
      connectedSet.delete(slug);
      localStorage.setItem('connected_integrations', JSON.stringify([...connectedSet]));
    }

    // Remove status
    const statuses = JSON.parse(localStorage.getItem('integration_statuses') || '{}');
    delete statuses[slug];
    localStorage.setItem('integration_statuses', JSON.stringify(statuses));

    // Remove connection data
    localStorage.removeItem(`integration_${slug}`);

    // Reload
    loadConnectedIntegrations();
  };

  const handleTestConnection = async (slug: string) => {
    // Update status to pending
    const statuses = JSON.parse(localStorage.getItem('integration_statuses') || '{}');
    statuses[slug] = 'pending';
    localStorage.setItem('integration_statuses', JSON.stringify(statuses));
    loadConnectedIntegrations();

    // Simulate connection test
    setTimeout(() => {
      const success = Math.random() > 0.2; // 80% success rate
      const statuses = JSON.parse(localStorage.getItem('integration_statuses') || '{}');
      statuses[slug] = success ? 'connected' : 'error';
      localStorage.setItem('integration_statuses', JSON.stringify(statuses));

      // Update last sync
      const connectionData = localStorage.getItem(`integration_${slug}`);
      if (connectionData) {
        const data = JSON.parse(connectionData);
        data.lastSync = new Date().toISOString();
        localStorage.setItem(`integration_${slug}`, JSON.stringify(data));
      }

      loadConnectedIntegrations();
    }, 2000);
  };

  const filteredIntegrations = connectedIntegrations.filter(
    (integration) =>
      integration.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      integration.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const connectedCount = connectedIntegrations.filter((i) => i.status === 'connected').length;
  const errorCount = connectedIntegrations.filter((i) => i.status === 'error').length;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-6xl mx-auto px-6 py-8">
          <Button
            variant="ghost"
            onClick={() => router.push('/integrations')}
            className="mb-4 gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to All Integrations
          </Button>

          <div className="flex items-start justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Connected Integrations</h1>
              <p className="text-gray-600">
                Manage your active integration connections
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-blue-700 mb-1">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm font-medium">Total Connected</span>
              </div>
              <div className="text-2xl font-bold text-blue-900">
                {connectedIntegrations.length}
              </div>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-green-700 mb-1">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm font-medium">Active</span>
              </div>
              <div className="text-2xl font-bold text-green-900">{connectedCount}</div>
            </div>
            {errorCount > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-red-700 mb-1">
                  <AlertCircle className="w-5 h-5" />
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
              placeholder="Search connected integrations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Loading integrations...</p>
          </div>
        ) : filteredIntegrations.length > 0 ? (
          <div className="space-y-4">
            {filteredIntegrations.map((integration) => (
              <ConnectionStatus
                key={integration.slug}
                integration={integration}
                onTest={() => handleTestConnection(integration.slug)}
                onDisconnect={() => handleDisconnect(integration.slug)}
                onConfigure={() => router.push(`/integrations/${integration.slug}`)}
              />
            ))}
          </div>
        ) : (
          <div className="bg-white border rounded-lg p-12 text-center">
            {searchQuery ? (
              <>
                <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No integrations found
                </h3>
                <p className="text-gray-600 mb-6">
                  Try adjusting your search query
                </p>
              </>
            ) : (
              <>
                <CheckCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No Connected Integrations
                </h3>
                <p className="text-gray-600 mb-6">
                  Start by connecting your first integration
                </p>
                <Button onClick={() => router.push('/integrations')}>
                  Browse Integrations
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
