'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';

export const OAuthCallback: React.FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');
  const [error, setError] = useState<string | null>(null);
  const [integrationName, setIntegrationName] = useState<string>('');

  useEffect(() => {
    const handleOAuthCallback = async () => {
      // Get OAuth parameters from URL
      const code = searchParams?.get('code');
      const state = searchParams?.get('state');
      const errorParam = searchParams?.get('error');
      const errorDescription = searchParams?.get('error_description');

      // Check for OAuth errors
      if (errorParam) {
        setError(errorDescription || `OAuth error: ${errorParam}`);
        setStatus('error');
        return;
      }

      // Validate state parameter (CSRF protection)
      const savedState = localStorage.getItem('oauth_state');
      const integrationSlug = localStorage.getItem('oauth_integration');

      if (!state || !savedState || state !== savedState) {
        setError('Invalid state parameter. This may be a security issue.');
        setStatus('error');
        return;
      }

      if (!code) {
        setError('Authorization code not received from OAuth provider.');
        setStatus('error');
        return;
      }

      if (!integrationSlug) {
        setError('Integration information not found.');
        setStatus('error');
        return;
      }

      setIntegrationName(integrationSlug);

      try {
        // Exchange code for access token (call backend API)
        const response = await fetch('/api/integrations/oauth/exchange', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code,
            state,
            integration: integrationSlug,
            redirectUri: `${window.location.origin}/integrations/oauth/callback`,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.message || 'Failed to exchange authorization code');
        }

        const data = await response.json();

        // Save connection information
        const connected = localStorage.getItem('connected_integrations');
        const connectedSet = connected ? new Set(JSON.parse(connected)) : new Set();
        connectedSet.add(integrationSlug);
        localStorage.setItem('connected_integrations', JSON.stringify([...connectedSet]));

        // Save status
        const statuses = JSON.parse(localStorage.getItem('integration_statuses') || '{}');
        statuses[integrationSlug] = 'connected';
        localStorage.setItem('integration_statuses', JSON.stringify(statuses));

        // Save connection data
        const connectionData = {
          integrationSlug,
          connectedAt: new Date().toISOString(),
          authType: 'oauth2',
          ...data,
        };
        localStorage.setItem(`integration_${integrationSlug}`, JSON.stringify(connectionData));

        // Clean up OAuth state
        localStorage.removeItem('oauth_state');
        localStorage.removeItem('oauth_integration');

        setStatus('success');

        // Redirect after 2 seconds
        setTimeout(() => {
          router.push('/dashboard/integrations/connected');
        }, 2000);
      } catch (err: any) {
        console.error('OAuth exchange error:', err);
        setError(err.message || 'Failed to complete OAuth flow');
        setStatus('error');

        // Clean up OAuth state
        localStorage.removeItem('oauth_state');
        localStorage.removeItem('oauth_integration');
      }
    };

    handleOAuthCallback();
  }, [searchParams, router]);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white border rounded-lg p-8">
        {status === 'processing' && (
          <div className="text-center">
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Completing Authorization...
            </h2>
            <p className="text-gray-600">
              Please wait while we finalize your integration connection.
            </p>
          </div>
        )}

        {status === 'success' && (
          <div className="text-center">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Successfully Connected!
            </h2>
            <p className="text-gray-600 mb-4">
              Your {integrationName} integration is now active.
            </p>
            <p className="text-sm text-gray-500">
              Redirecting to your connected integrations...
            </p>
          </div>
        )}

        {status === 'error' && (
          <div className="text-center">
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <XCircle className="w-8 h-8 text-red-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Connection Failed
            </h2>
            <Alert variant="destructive" className="mb-4 text-left">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
            <div className="flex flex-col gap-2">
              <Button
                onClick={() => router.push('/dashboard/integrations')}
                className="w-full"
              >
                Back to Integrations
              </Button>
              <Button
                onClick={() => window.location.reload()}
                variant="outline"
                className="w-full"
              >
                Try Again
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
