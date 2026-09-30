import React, { useState } from 'react';
import {
  CheckCircle,
  XCircle,
  Clock,
  Settings,
  Trash2,
  RefreshCw,
  Shield,
  Key,
  Calendar,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getIconUrl } from './IntegrationCard';
import { RelativeTime } from '@/components/ui/relative-time';

interface ConnectionStatusProps {
  integration: {
    slug: string;
    name: string;
    icon: string;
    category: string;
    connectedAt: string;
    status: 'connected' | 'error' | 'pending';
    lastSync?: string;
    authType: string;
  };
  onTest: () => void;
  onDisconnect: () => void;
  onConfigure: () => void;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  integration,
  onTest,
  onDisconnect,
  onConfigure,
}) => {
  const [iconFailed, setIconFailed] = useState(false);

  const getStatusBadge = () => {
    switch (integration.status) {
      case 'connected':
        return (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-100 text-green-700 rounded-full text-sm font-medium">
            <CheckCircle className="w-4 h-4" />
            Connected
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-red-100 text-red-700 rounded-full text-sm font-medium">
            <XCircle className="w-4 h-4" />
            Error
          </div>
        );
      case 'pending':
        return (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-full text-sm font-medium">
            <Clock className="w-4 h-4 animate-pulse" />
            Testing...
          </div>
        );
      default:
        return null;
    }
  };

  const getAuthIcon = () => {
    if (integration.authType === 'oauth2') {
      return <Shield className="w-4 h-4 text-blue-600" />;
    }
    return <Key className="w-4 h-4 text-purple-600" />;
  };

  return (
    <div
      className={`border rounded-2xl p-6 transition-all ${
        integration.status === 'connected'
          ? 'border-slate-200 bg-white'
          : integration.status === 'error'
          ? 'border-red-500 bg-red-50/30'
          : 'border-yellow-500 bg-yellow-50/30'
      }`}
    >
      <div className="flex items-start justify-between">
        {/* Left Side - Integration Info */}
        <div className="flex items-start gap-4 flex-1">
          {/* Icon */}
          <div className="w-14 h-14 bg-white border border-slate-200 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm overflow-hidden">
            {getIconUrl(integration.slug) && !iconFailed ? (
              <img
                src={getIconUrl(integration.slug)!}
                alt={`${integration.name} icon`}
                className="w-8 h-8 object-contain"
                onError={() => setIconFailed(true)}
              />
            ) : (
              <span className="text-2xl leading-none">{integration.icon}</span>
            )}
          </div>

          {/* Details */}
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-black text-[18px] tracking-wide font-poppins font-bold">{integration.name}</h3>
              {getStatusBadge()}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                {getAuthIcon()}
                <span className="capitalize">{integration.authType.replace('_', ' ')}</span>
                <span className="text-gray-400">•</span>
                <span className="capitalize">{integration.category}</span>
              </div>

              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Calendar className="w-4 h-4" />
                <span>Connected <RelativeTime value={integration.connectedAt} /></span>
              </div>

              {integration.lastSync && integration.status === 'connected' && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <RefreshCw className="w-4 h-4" />
                  <span>Last synced <RelativeTime value={integration.lastSync} /></span>
                </div>
              )}

              {integration.status === 'error' && (
                <div className="text-sm text-red-600 mt-2">
                  <div className="flex items-center gap-2">
                    <XCircle className="w-4 h-4" />
                    <span>Connection error - authentication failed or expired</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Side - Actions */}
        <div className="flex items-center gap-2 ml-4">
          <Button
            variant="outline"
            size="sm"
            onClick={onTest}
            disabled={integration.status === 'pending'}
            className="gap-2"
            title="Test Connection"
          >
            <RefreshCw
              className={`w-4 h-4 ${integration.status === 'pending' ? 'animate-spin' : ''}`}
            />
            Test
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onConfigure}
            className="gap-2"
            title="Configure"
          >
            <Settings className="w-4 h-4" />
            Settings
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onDisconnect}
            className="gap-2 text-red-600 hover:text-red-700 hover:bg-red-50"
            title="Disconnect"
          >
            <Trash2 className="w-4 h-4" />
            Disconnect
          </Button>
        </div>
      </div>

      {/* Additional Info for Error State */}
      {integration.status === 'error' && (
        <div className="mt-4 pt-4 border-t border-red-200">
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-700 mb-2">
              <strong>Recommended Actions:</strong>
            </p>
            <ul className="text-sm text-red-600 space-y-1 list-disc list-inside">
              <li>Test the connection to verify the error</li>
              <li>Check if your API credentials are still valid</li>
              <li>Reconnect the integration if needed</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
