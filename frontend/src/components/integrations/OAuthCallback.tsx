'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { apiClient, getErrorMessage } from '@/lib/api';
import { API_ENDPOINTS } from '@/lib/constants';

export const OAuthCallback: React.FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');
  const [error, setError] = useState<string | null>(null);
  const [integrationName, setIntegrationName] = useState<string>('');

  useEffect(() => {
    const cleanup = () => {
      sessionStorage.removeItem('oauth_state');
      sessionStorage.removeItem('oauth_connector_id');
      sessionStorage.removeItem('oauth_redirect_uri');
      sessionStorage.removeItem('oauth_slug');
      sessionStorage.removeItem('oauth_return');
    };

    const handleOAuthCallback = async () => {
      // Params from the provider redirect
      const code = searchParams?.get('code');
      const state = searchParams?.get('state');
      const errorParam = searchParams?.get('error');
      const errorDescription = searchParams?.get('error_description');

      if (errorParam) {
        setError(errorDescription || `OAuth error: ${errorParam}`);
        setStatus('error');
        return;
      }

      // Context stored when the flow was started (IntegrationSetup)
      const savedState = sessionStorage.getItem('oauth_state');
      const connectorId = sessionStorage.getItem('oauth_connector_id');
      const redirectUri = sessionStorage.getItem('oauth_redirect_uri');
      const slug = sessionStorage.getItem('oauth_slug') || '';
      const returnPath = sessionStorage.getItem('oauth_return') || '/dashboard/integrations';
      setIntegrationName(slug);

      if (!state || !savedState || state !== savedState) {
        setError('Invalid state parameter. Please start the connection again.');
        setStatus('error');
        return;
      }
      if (!code) {
        setError('Authorization code not received from the provider.');
        setStatus('error');
        return;
      }
      if (!connectorId || !redirectUri) {
        setError('Connection context was lost. Please start the connection again.');
        setStatus('error');
        return;
      }

      try {
        // Exchange the code via the backend (same redirect_uri as authorize).
        await apiClient.post(
          API_ENDPOINTS.INTEGRATIONS +
            `/oauth/callback?redirect_uri=${encodeURIComponent(redirectUri)}`,
          { connector_id: connectorId, code, state }
        );
        cleanup();
        setStatus('success');
        setTimeout(() => router.push(returnPath), 1500);
      } catch (err: any) {
        setError(getErrorMessage(err));
        setStatus('error');
        cleanup();
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
