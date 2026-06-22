'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Search, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ConnectionStatus } from '@/components/integrations/ConnectionStatus';
import { apiClient } from '@/lib/api';
import { API_ENDPOINTS } from '@/lib/constants';
import { toast } from 'sonner';

interface ApiConnection {
  id: string;
  name: string | null;
  status: string;
  is_active: boolean;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
  connector: {
    id: string;
    slug: string;
    name: string;
    category: string | null;
    auth_type: string;
  };
}

interface ConnectedIntegration {
  connectionId: string;
  slug: string;
  name: string;
  icon: string;
  category: string;
  connectedAt: string;
  status: 'connected' | 'error' | 'pending';
  lastSync?: string;
  authType: string;
}

const catalogMetadata: Record<string, { icon: string; category: string }> = {
  salesforce: { icon: '🔷', category: 'crm' },
  hubspot: { icon: '🟠', category: 'crm' },
  'google-calendar': { icon: '📅', category: 'calendar' },
  slack: { icon: '💬', category: 'communication' },
  twilio: { icon: '📞', category: 'communication' },
  zapier: { icon: '⚡', category: 'productivity' },
  'google-sheets': { icon: '📊', category: 'productivity' },
  airtable: { icon: '🗂️', category: 'productivity' },
  stripe: { icon: '💳', category: 'other' },
  calendly: { icon: '🗓️', category: 'calendar' },
  zendesk: { icon: '🎫', category: 'crm' },
  'microsoft-teams': { icon: '👥', category: 'communication' },
};

function apiStatusToDisplay(s: string): 'connected' | 'error' | 'pending' {
  if (s === 'active') return 'connected';
  if (s === 'error' || s === 'expired') return 'error';
  return 'pending';
}

export default function ConnectedIntegrationsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [connectedIntegrations, setConnectedIntegrations] = useState<ConnectedIntegration[]>([]);
  const [loading, setLoading] = useState(true);

  const loadConnectedIntegrations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<{ connections: ApiConnection[]; total: number }>(
        API_ENDPOINTS.INTEGRATION_CONNECTIONS
      );
      const mapped: ConnectedIntegration[] = res.data.connections.map((conn) => {
        const slug = conn.connector.slug;
        const meta = catalogMetadata[slug] || { icon: '🔗', category: 'other' };
        return {
          connectionId: conn.id,
          slug,
          name: conn.connector.name,
          icon: meta.icon,
          category: conn.connector.category || meta.category,
          connectedAt: conn.created_at,
          status: apiStatusToDisplay(conn.status),
          lastSync: conn.last_sync_at || undefined,
          authType: conn.connector.auth_type,
        };
      });
      setConnectedIntegrations(mapped);
    } catch {
      setConnectedIntegrations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConnectedIntegrations();
  }, [loadConnectedIntegrations]);

  const handleDisconnect = async (slug: string) => {
    const integration = connectedIntegrations.find((i) => i.slug === slug);
    if (!integration) return;
    if (!confirm(`Are you sure you want to disconnect ${integration.name}?`)) return;

    try {
      await apiClient.delete(API_ENDPOINTS.INTEGRATION_CONNECTION(integration.connectionId));
      toast.success(`${integration.name} disconnected`);
      await loadConnectedIntegrations();
    } catch {
      toast.error('Failed to disconnect integration');
    }
  };

  const handleTestConnection = async (slug: string) => {
    const integration = connectedIntegrations.find((i) => i.slug === slug);
    if (!integration) return;

    // Optimistically set to pending
    setConnectedIntegrations((prev) =>
      prev.map((i) => (i.slug === slug ? { ...i, status: 'pending' } : i))
    );

    try {
      await apiClient.post(
        API_ENDPOINTS.INTEGRATION_CONNECTION_TEST(integration.connectionId)
      );
      toast.success(`${integration.name} connection verified`);
    } catch {
      toast.error(`${integration.name} connection test failed`);
    } finally {
      await loadConnectedIntegrations();
    }
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
            onClick={() => router.push('/dashboard/integrations')}
            className="mb-4 gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to All Integrations
          </Button>

          <div className="flex items-start justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Connected Integrations</h1>
              <p className="text-gray-600">Manage your active integration connections</p>
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
                {loading ? '—' : connectedIntegrations.length}
              </div>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-green-700 mb-1">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm font-medium">Active</span>
              </div>
              <div className="text-2xl font-bold text-green-900">
                {loading ? '—' : connectedCount}
              </div>
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
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-600">Loading integrations...</p>
          </div>
        ) : filteredIntegrations.length > 0 ? (
          <div className="space-y-4">
            {filteredIntegrations.map((integration) => (
              <ConnectionStatus
                key={integration.connectionId}
                integration={integration}
                onTest={() => handleTestConnection(integration.slug)}
                onDisconnect={() => handleDisconnect(integration.slug)}
                onConfigure={() =>
                  router.push(`/dashboard/integrations/${integration.slug}`)
                }
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
                <p className="text-gray-600 mb-6">Try adjusting your search query</p>
              </>
            ) : (
              <>
                <CheckCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No Connected Integrations
                </h3>
                <p className="text-gray-600 mb-6">Start by connecting your first integration</p>
                <Button onClick={() => router.push('/dashboard/integrations')}>
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
