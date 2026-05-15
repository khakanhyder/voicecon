import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Lock,
  Check,
  AlertCircle,
  Loader2,
  Key,
  ExternalLink,
  Shield,
  CheckCircle,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface IntegrationSetupProps {
  integration: {
    id: string;
    slug: string;
    name: string;
    authType: 'oauth2' | 'api_key' | 'basic';
    permissions: string[];
    scopes?: string[];
    oauthUrl?: string;
    setupSteps: string[];
    apiKeyFields?: Array<{
      name: string;
      label: string;
      type: string;
      required: boolean;
    }>;
  };
}

type ConnectionStatus = 'idle' | 'connecting' | 'testing' | 'success' | 'error';

export const IntegrationSetup: React.FC<IntegrationSetupProps> = ({ integration }) => {
  const router = useRouter();
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [apiKeyValues, setApiKeyValues] = useState<Record<string, string>>({});
  const [testResults, setTestResults] = useState<{
    passed: boolean;
    message: string;
    details?: string[];
  } | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Check if already connected
  useEffect(() => {
    const connected = localStorage.getItem('connected_integrations');
    if (connected) {
      try {
        const connectedSet = new Set(JSON.parse(connected));
        setIsConnected(connectedSet.has(integration.slug));
      } catch (error) {
        console.error('Error checking connection status:', error);
      }
    }
  }, [integration.slug]);

  const handleOAuthConnect = () => {
    setStatus('connecting');
    setError(null);

    // Generate state parameter for OAuth security
    const state = Math.random().toString(36).substring(2, 15);
    localStorage.setItem('oauth_state', state);
    localStorage.setItem('oauth_integration', integration.slug);

    // In production, construct actual OAuth URL with proper parameters
    const clientId = process.env.NEXT_PUBLIC_OAUTH_CLIENT_ID || 'demo_client_id';
    const redirectUri = `${window.location.origin}/integrations/oauth/callback`;

    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      state: state,
      response_type: 'code',
      scope: integration.scopes?.join(' ') || '',
    });

    // Simulate OAuth flow (in production, this would redirect to actual OAuth provider)
    console.log('OAuth URL:', `${integration.oauthUrl}?${params.toString()}`);

    // For demo purposes, simulate successful OAuth
    setTimeout(() => {
      handleTestConnection();
    }, 2000);
  };

  const handleApiKeyConnect = async () => {
    setStatus('connecting');
    setError(null);

    // Validate required fields
    const missingFields = integration.apiKeyFields
      ?.filter((field) => field.required && !apiKeyValues[field.name])
      .map((field) => field.label);

    if (missingFields && missingFields.length > 0) {
      setError(`Please fill in required fields: ${missingFields.join(', ')}`);
      setStatus('error');
      return;
    }

    // Simulate API call to validate credentials
    setTimeout(() => {
      handleTestConnection();
    }, 1500);
  };

  const handleTestConnection = async () => {
    setStatus('testing');
    setError(null);

    // Simulate connection test
    setTimeout(() => {
      // 90% success rate for demo
      const success = Math.random() > 0.1;

      if (success) {
        setTestResults({
          passed: true,
          message: 'Connection successful!',
          details: [
            'Authentication verified',
            'API access confirmed',
            'Permissions validated',
            'Ready to use',
          ],
        });
        setStatus('success');

        // Save connection
        saveConnection();
      } else {
        setTestResults({
          passed: false,
          message: 'Connection failed',
          details: [
            'Invalid credentials',
            'Please check your API keys and try again',
          ],
        });
        setStatus('error');
        setError('Failed to connect. Please verify your credentials.');
      }
    }, 2000);
  };

  const saveConnection = () => {
    // Save to localStorage (in production, save to backend)
    const connected = localStorage.getItem('connected_integrations');
    const connectedSet = connected ? new Set(JSON.parse(connected)) : new Set();
    connectedSet.add(integration.slug);
    localStorage.setItem('connected_integrations', JSON.stringify([...connectedSet]));

    // Save status
    const statuses = JSON.parse(localStorage.getItem('integration_statuses') || '{}');
    statuses[integration.slug] = 'connected';
    localStorage.setItem('integration_statuses', JSON.stringify(statuses));

    // Save connection data
    const connectionData = {
      integrationId: integration.id,
      slug: integration.slug,
      connectedAt: new Date().toISOString(),
      authType: integration.authType,
      ...(integration.authType === 'api_key' && { credentials: apiKeyValues }),
    };
    localStorage.setItem(`integration_${integration.slug}`, JSON.stringify(connectionData));

    setIsConnected(true);
  };

  const handleDisconnect = () => {
    // Remove from connected integrations
    const connected = localStorage.getItem('connected_integrations');
    if (connected) {
      const connectedSet = new Set(JSON.parse(connected));
      connectedSet.delete(integration.slug);
      localStorage.setItem('connected_integrations', JSON.stringify([...connectedSet]));
    }

    // Remove status
    const statuses = JSON.parse(localStorage.getItem('integration_statuses') || '{}');
    delete statuses[integration.slug];
    localStorage.setItem('integration_statuses', JSON.stringify(statuses));

    // Remove connection data
    localStorage.removeItem(`integration_${integration.slug}`);

    setIsConnected(false);
    setStatus('idle');
    setTestResults(null);
    setApiKeyValues({});
  };

  const handleRetry = () => {
    setStatus('idle');
    setError(null);
    setTestResults(null);
  };

  const renderOAuthSetup = () => (
    <div className="space-y-6">
      {/* Permissions */}
      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-indigo-600" />
          <h3 className="text-lg font-semibold text-gray-900">Required Permissions</h3>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          Voicecon will request the following permissions:
        </p>
        <ul className="space-y-2">
          {integration.permissions.map((permission, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
              <Check className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
              <span>{permission}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Setup Steps */}
      <div className="bg-white border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Setup Instructions</h3>
        <ol className="space-y-3">
          {integration.setupSteps.map((step, idx) => (
            <li key={idx} className="flex items-start gap-3 text-sm text-gray-700">
              <div className="flex items-center justify-center w-6 h-6 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium flex-shrink-0">
                {idx + 1}
              </div>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Security Note */}
      <Alert>
        <Lock className="h-4 w-4" />
        <AlertDescription>
          Your credentials are encrypted and stored securely. Voicecon uses industry-standard OAuth
          2.0 for authentication.
        </AlertDescription>
      </Alert>
    </div>
  );

  const renderApiKeySetup = () => (
    <div className="space-y-6">
      {/* API Key Form */}
      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Key className="w-5 h-5 text-indigo-600" />
          <h3 className="text-lg font-semibold text-gray-900">Enter Your Credentials</h3>
        </div>
        <div className="space-y-4">
          {integration.apiKeyFields?.map((field) => (
            <div key={field.name}>
              <Label htmlFor={field.name}>
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </Label>
              <Input
                id={field.name}
                type={field.type}
                value={apiKeyValues[field.name] || ''}
                onChange={(e) =>
                  setApiKeyValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                }
                placeholder={`Enter your ${field.label.toLowerCase()}`}
                required={field.required}
                className="font-mono text-sm"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Setup Steps */}
      <div className="bg-white border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">How to Get Your Credentials</h3>
        <ol className="space-y-3">
          {integration.setupSteps.map((step, idx) => (
            <li key={idx} className="flex items-start gap-3 text-sm text-gray-700">
              <div className="flex items-center justify-center w-6 h-6 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium flex-shrink-0">
                {idx + 1}
              </div>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Permissions Info */}
      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-indigo-600" />
          <h3 className="text-lg font-semibold text-gray-900">What Voicecon Can Do</h3>
        </div>
        <ul className="space-y-2">
          {integration.permissions.map((permission, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
              <Check className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
              <span>{permission}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Security Note */}
      <Alert>
        <Lock className="h-4 w-4" />
        <AlertDescription>
          Your API keys are encrypted using AES-256 encryption and stored securely in our
          database.
        </AlertDescription>
      </Alert>
    </div>
  );

  const renderTestResults = () => {
    if (!testResults) return null;

    return (
      <div
        className={`bg-white border-2 rounded-lg p-6 ${
          testResults.passed ? 'border-green-200 bg-green-50/30' : 'border-red-200 bg-red-50/30'
        }`}
      >
        <div className="flex items-start gap-3 mb-4">
          {testResults.passed ? (
            <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0" />
          ) : (
            <XCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
          )}
          <div className="flex-1">
            <h3
              className={`text-lg font-semibold mb-2 ${
                testResults.passed ? 'text-green-900' : 'text-red-900'
              }`}
            >
              {testResults.message}
            </h3>
            {testResults.details && (
              <ul className="space-y-1">
                {testResults.details.map((detail, idx) => (
                  <li
                    key={idx}
                    className={`flex items-center gap-2 text-sm ${
                      testResults.passed ? 'text-green-700' : 'text-red-700'
                    }`}
                  >
                    <div
                      className={`w-1.5 h-1.5 rounded-full ${
                        testResults.passed ? 'bg-green-600' : 'bg-red-600'
                      }`}
                    />
                    {detail}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {testResults.passed && (
          <div className="flex gap-3">
            <Button onClick={() => router.push('/dashboard/integrations/connected')} className="gap-2">
              <CheckCircle className="w-4 h-4" />
              View Connected Integrations
            </Button>
            <Button variant="outline" onClick={() => router.push('/dashboard/integrations')}>
              Browse More Integrations
            </Button>
          </div>
        )}

        {!testResults.passed && (
          <Button onClick={handleRetry} variant="outline" className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Try Again
          </Button>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Current Status */}
      {isConnected && status !== 'success' && (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            This integration is already connected. You can disconnect and reconnect if needed.
          </AlertDescription>
        </Alert>
      )}

      {/* Error Message */}
      {error && status === 'error' && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Test Results */}
      {testResults && renderTestResults()}

      {/* Setup Content */}
      {status !== 'success' && (
        <>
          {integration.authType === 'oauth2' && renderOAuthSetup()}
          {integration.authType === 'api_key' && renderApiKeySetup()}

          {/* Action Buttons */}
          <div className="flex gap-3">
            {!isConnected ? (
              <>
                {integration.authType === 'oauth2' && (
                  <Button
                    onClick={handleOAuthConnect}
                    disabled={status === 'connecting' || status === 'testing'}
                    className="gap-2"
                    size="lg"
                  >
                    {status === 'connecting' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Connecting...
                      </>
                    ) : status === 'testing' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Testing Connection...
                      </>
                    ) : (
                      <>
                        <ExternalLink className="w-4 h-4" />
                        Connect with {integration.name}
                      </>
                    )}
                  </Button>
                )}

                {integration.authType === 'api_key' && (
                  <Button
                    onClick={handleApiKeyConnect}
                    disabled={status === 'connecting' || status === 'testing'}
                    className="gap-2"
                    size="lg"
                  >
                    {status === 'connecting' || status === 'testing' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        {status === 'testing' ? 'Testing Connection...' : 'Connecting...'}
                      </>
                    ) : (
                      <>
                        <Key className="w-4 h-4" />
                        Connect Integration
                      </>
                    )}
                  </Button>
                )}

                <Button variant="outline" onClick={() => router.push('/dashboard/integrations')} size="lg">
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <Button onClick={handleTestConnection} variant="outline" className="gap-2">
                  <RefreshCw className="w-4 h-4" />
                  Test Connection
                </Button>
                <Button onClick={handleDisconnect} variant="destructive" className="gap-2">
                  <XCircle className="w-4 h-4" />
                  Disconnect
                </Button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
};
