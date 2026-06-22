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
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-medium">
            <CheckCircle className="w-3.5 h-3.5" />
            Connected
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 text-red-700 border border-red-200 rounded-full text-xs font-medium">
            <AlertCircle className="w-3.5 h-3.5" />
            Error
          </div>
        );
      case 'pending':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded-full text-xs font-medium">
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
      oauth2: { text: 'OAuth 2.0', color: 'bg-violet-50 text-violet-700 border border-violet-200' },
      api_key: { text: 'API Key', color: 'bg-blue-50 text-blue-700 border border-blue-200' },
      basic: { text: 'Basic Auth', color: 'bg-slate-100 text-slate-600 border border-slate-200' },
    };
    const badge = badges[integration.authType];
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.color}`}>
        {badge.text}
      </span>
    );
  };

  const isConnected = integration.status === 'connected';

  return (
    <div
      className={`bg-white rounded-xl border transition-all overflow-hidden cursor-pointer group ${
        isConnected
          ? 'border-emerald-200 shadow-sm hover:shadow-md'
          : integration.status === 'error'
          ? 'border-red-200 shadow-sm hover:shadow-md'
          : 'border-slate-200 shadow-sm hover:shadow-md hover:border-blue-300'
      }`}
      onClick={onConnect}
    >
      {/* Connected stripe */}
      {isConnected && <div className="h-1 w-full bg-gradient-to-r from-emerald-400 to-teal-500" />}

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center flex-shrink-0 shadow-sm">
              <span className="text-white text-sm font-bold leading-none">
                {integration.name.slice(0, 2).toUpperCase()}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <h3 className="font-semibold text-slate-900 leading-tight">{integration.name}</h3>
                {integration.popular && (
                  <Zap className="w-3.5 h-3.5 text-amber-500 fill-amber-400" title="Popular" />
                )}
              </div>
              {getAuthTypeBadge()}
            </div>
          </div>
          {getStatusBadge()}
        </div>

        {/* Description */}
        <p className="text-sm text-slate-500 mb-3 line-clamp-2 min-h-[2.5rem]">
          {integration.description}
        </p>

        {/* Features */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {integration.features.slice(0, 3).map((feature, idx) => (
            <span key={idx} className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs border border-slate-200">
              {feature}
            </span>
          ))}
          {integration.features.length > 3 && (
            <span className="px-2 py-0.5 bg-slate-100 text-slate-400 rounded text-xs border border-slate-200">
              +{integration.features.length - 3} more
            </span>
          )}
        </div>

        {/* Action Button */}
        {isConnected ? (
          <button
            onClick={(e) => { e.stopPropagation(); onConnect(); }}
            className="w-full flex items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Manage
            <ArrowRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); onConnect(); }}
            className="w-full flex items-center justify-center gap-2 rounded-md gradient-primary px-3 py-2 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm"
          >
            Connect
            <ArrowRight className="w-4 h-4" />
          </button>
        )}

        {isConnected && integration.connectedAt && (
          <p className="text-xs text-slate-400 mt-2 text-center">
            Connected {new Date(integration.connectedAt).toLocaleDateString()}
          </p>
        )}
      </div>
    </div>
  );
};
