import React from 'react';
import { CheckCircle, AlertCircle, Clock, ArrowRight, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface IntegrationCardProps {
  integration: {
    id: string;
    slug: string;
    name: string;
    description: string;
    category: string;
    icon: string;
    authType: 'oauth2' | 'api_key' | 'basic';
    status?: 'connected' | 'error' | 'pending' | null;
    connectedAt?: string;
    features: string[];
    popular: boolean;
  };
  onConnect: () => void;
}

export const IntegrationCard: React.FC<IntegrationCardProps> = ({ integration, onConnect }) => {
  const getStatusBadge = () => {
    switch (integration.status) {
      case 'connected':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">
            <CheckCircle className="w-3.5 h-3.5" />
            Connected
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
            <AlertCircle className="w-3.5 h-3.5" />
            Error
          </div>
        );
      case 'pending':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">
            <Clock className="w-3.5 h-3.5" />
            Pending
          </div>
        );
      default:
        return null;
    }
  };

  const getAuthTypeBadge = () => {
    const badges = {
      oauth2: { text: 'OAuth 2.0', color: 'bg-blue-100 text-blue-700' },
      api_key: { text: 'API Key', color: 'bg-purple-100 text-purple-700' },
      basic: { text: 'Basic Auth', color: 'bg-gray-100 text-gray-700' },
    };

    const badge = badges[integration.authType];
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.color}`}>
        {badge.text}
      </span>
    );
  };

  const buttonText = integration.status === 'connected' ? 'Manage' : 'Connect';
  const buttonVariant = integration.status === 'connected' ? 'outline' : 'default';

  return (
    <div
      className={`bg-white border-2 rounded-lg p-5 hover:shadow-lg transition-all ${
        integration.status === 'connected'
          ? 'border-green-200 bg-green-50/30'
          : integration.status === 'error'
          ? 'border-red-200 bg-red-50/30'
          : 'border-gray-200 hover:border-indigo-300'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className="w-12 h-12 bg-gradient-to-br from-gray-100 to-gray-200 rounded-lg flex items-center justify-center text-2xl">
            {integration.icon}
          </div>

          {/* Name & Category */}
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-gray-900">{integration.name}</h3>
              {integration.popular && (
                <Zap className="w-4 h-4 text-yellow-500" title="Popular" />
              )}
            </div>
            <div className="flex items-center gap-2">
              {getAuthTypeBadge()}
            </div>
          </div>
        </div>

        {/* Status Badge */}
        {getStatusBadge()}
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 mb-4 line-clamp-2">{integration.description}</p>

      {/* Features */}
      <div className="mb-4">
        <div className="flex flex-wrap gap-1.5">
          {integration.features.slice(0, 3).map((feature, idx) => (
            <span
              key={idx}
              className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs"
            >
              {feature}
            </span>
          ))}
          {integration.features.length > 3 && (
            <span className="px-2 py-1 bg-gray-100 text-gray-500 rounded text-xs">
              +{integration.features.length - 3} more
            </span>
          )}
        </div>
      </div>

      {/* Action Button */}
      <Button
        onClick={onConnect}
        variant={buttonVariant}
        className="w-full gap-2"
        size="sm"
      >
        {buttonText}
        <ArrowRight className="w-4 h-4" />
      </Button>

      {/* Connected At */}
      {integration.status === 'connected' && integration.connectedAt && (
        <p className="text-xs text-gray-500 mt-2 text-center">
          Connected {new Date(integration.connectedAt).toLocaleDateString()}
        </p>
      )}
    </div>
  );
};
