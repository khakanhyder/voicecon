import React, { useState } from 'react';
import { CheckCircle, AlertCircle, Clock } from 'lucide-react';

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

/**
 * Brand icons bundled in `public/brand/apps-icons`. These take priority over
 * the icon CDN — they're the official marks and need no network round-trip.
 */
export const localIcons: Record<string, string> = {
  'google-calendar': 'calender.png',
  'clickup': 'clickup.png',
  'google-drive': 'gdrive.png',
  'gmail': 'gmail.png',
  'gohighlevel': 'gohightlevel.png',
  'hubspot': 'hubspot.png',
  'monday': 'moday.png',
  'outlook': 'outlook.png',
  'slack': 'slack.png',
  'stripe': 'stripe.png',
  'microsoft-teams': 'teams.png',
  'telnyx': 'telnyx.png',
  'trello': 'trello.png',
  'twilio': 'twilio.png',
  'zapier': 'zapier.png',
};

export const getIconUrl = (slug: string) => {
  if (localIcons[slug]) return `/brand/apps-icons/${localIcons[slug]}`;

  // Everything else still resolves from the icon CDN.
  const map: Record<string, string> = {
    'salesforce': 'salesforce',
    'hubspot': 'hubspot',
    'pipedrive': 'pipedrive',
    'zendesk': 'zendesk',
    'intercom': 'intercom',
    'google-calendar': 'googlecalendar',
    'calendly': 'calendly',
    'cal-com': 'caldotcom',
    'slack': 'slack',
    'microsoft-teams': 'microsoftteams',
    'twilio': 'twilio',
    'sendgrid': 'sendgrid',
    'zapier': 'zapier',
    'make': 'make',
    'google-sheets': 'googlesheets',
    'google-drive': 'googledrive',
    'airtable': 'airtable',
    'stripe': 'stripe',
    'notion': 'notion',
    'monday': 'mondaydotcom',
    'aws-s3': 'amazons3',
    'azure-blob': 'microsoftazure',
    'gcs': 'googlecloud',
    'cloudflare-r2': 'cloudflare',
    'supabase': 'supabase',
    'clickup': 'clickup',
    'trello': 'trello',
    'whatsapp': 'whatsapp',
    'gohighlevel': 'gohighlevel',
    'telnyx': 'telnyx',
    'vonage': 'vonage',
    'langfuse': 'langfuse',
    'gmail': 'gmail',
    'outlook': 'microsoftoutlook',
  };
  return map[slug] ? `https://cdn.simpleicons.org/${map[slug]}` : null;
};

export const IntegrationCard: React.FC<IntegrationCardProps> = ({ integration, onConnect }) => {
  const getStatusBadge = () => {
    switch (integration.status) {
      case 'connected':
        return (
          <span className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
            <CheckCircle className="h-3 w-3" />
            Connected
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-700">
            <AlertCircle className="h-3 w-3" />
            Error
          </span>
        );
      case 'pending':
        return (
          <span className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
            <Clock className="h-3 w-3" />
            Pending
          </span>
        );
      default:
        return null;
    }
  };

  const isConnected = integration.status === 'connected';
  const iconUrl = getIconUrl(integration.slug);
  // Not every slug exists on the icon CDN, and the CDN may be unreachable —
  // fall back to the catalog glyph so the tile is never empty.
  const [iconFailed, setIconFailed] = useState(false);

  return (
    <div
      className={`flex items-center justify-between px-3 sm:px-5 py-3 rounded-2xl border border-slate-200 bg-white cursor-pointer group gap-2 sm:gap-4 transition-all hover:border-slate-300 hover:shadow-[0_10px_24px_-18px_rgba(15,23,42,0.35)]`}
      onClick={onConnect}
    >
      <div className="flex items-center gap-2 sm:gap-4 flex-1 min-w-0">
        {/* Icon sits in a white rounded tile, per the design */}
        <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white sm:h-12 sm:w-12">
          {iconUrl && !iconFailed ? (
            <img
              src={iconUrl}
              alt={`${integration.name} icon`}
              className="h-6 w-6 object-contain sm:h-7 sm:w-7"
              onError={() => setIconFailed(true)}
            />
          ) : (
            <span className="text-xl leading-none sm:text-2xl">{integration.icon}</span>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
          <h3 className="max-w-full truncate text-[15px] tracking-wide text-black sm:text-[18px]" style={{ fontFamily: 'Poppins, sans-serif' }}>{integration.name}</h3>
          {getStatusBadge()}
        </div>
      </div>

      <div className="flex flex-shrink-0 ml-1 sm:ml-0">
        {isConnected ? (
          <button
            onClick={(e) => { e.stopPropagation(); onConnect(); }}
            className="flex items-center justify-center rounded bg-[#106959] px-3 sm:px-6 py-1.5 sm:py-2 text-[12px] sm:text-[14px] font-medium text-white hover:opacity-90 transition-all font-poppins"
          >
            Manage
          </button>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); onConnect(); }}
            className="flex items-center justify-center rounded bg-[#106959] px-3 sm:px-6 py-1.5 sm:py-2 text-[12px] sm:text-[14px] font-medium text-white hover:opacity-90 transition-all font-poppins"
          >
            Connect
          </button>
        )}
      </div>
    </div>
  );
};
