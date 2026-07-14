'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Lock, Check, AlertCircle, Loader2, Key, ExternalLink,
  Shield, CheckCircle, XCircle, RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

interface IntegrationSetupProps {
  integration: {
    id: string
    slug: string
    name: string
    authType: 'oauth2' | 'api_key' | 'basic'
    permissions: string[]
    scopes?: string[]
    oauthUrl?: string
    setupSteps: string[]
    apiKeyFields?: Array<{ name: string; label: string; type: string; required: boolean }>
  }
  connectorId?: string        // backend UUID of the IntegrationConnector row
  existingConnectionId?: string
  onDisconnected?: () => void
  onConnected?: (connectionId: string) => void
}

type ConnectionStatus = 'idle' | 'connecting' | 'testing' | 'success' | 'error'

export const IntegrationSetup: React.FC<IntegrationSetupProps> = ({
  integration,
  connectorId,
  existingConnectionId,
  onDisconnected,
  onConnected,
}) => {
  const router = useRouter()
  const [status, setStatus] = useState<ConnectionStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [apiKeyValues, setApiKeyValues] = useState<Record<string, string>>({})
  const [testResults, setTestResults] = useState<{
    passed: boolean
    message: string
    details?: string[]
  } | null>(null)

  const isConnected = !!existingConnectionId && existingConnectionId !== 'simulated'

  // ── OAuth flow ───────────────────────────────────────────────────────────
  const handleOAuthConnect = async () => {
    setStatus('connecting')
    setError(null)

    if (!connectorId) {
      // No backend connector ID — show helpful message
      setError(
        `${integration.name} isn't available to connect yet. Your administrator needs to ` +
        `register an OAuth app with ${integration.name} and add its client credentials to the ` +
        `server environment. See the integration setup guide.`
      )
      setStatus('error')
      return
    }

    try {
      const redirectUri = `${window.location.origin}/api/integrations/oauth/callback`
      const res = await apiClient.post<{ authorization_url: string; state: string }>(
        API_ENDPOINTS.INTEGRATION_CONNECTORS + '/oauth/authorize',
        {
          connector_id: connectorId,
          redirect_uri: redirectUri,
          scopes: integration.scopes || [],
        }
      )
      // Store context for the callback page
      sessionStorage.setItem('oauth_state', res.data.state)
      sessionStorage.setItem('oauth_slug', integration.slug)
      sessionStorage.setItem('oauth_return', window.location.pathname)
      // Redirect to provider
      window.location.href = res.data.authorization_url
    } catch (err) {
      setError(getErrorMessage(err))
      setStatus('error')
    }
  }

  // ── API key flow ─────────────────────────────────────────────────────────
  const handleApiKeyConnect = async () => {
    setStatus('connecting')
    setError(null)

    const missingFields = integration.apiKeyFields
      ?.filter((f) => f.required && !apiKeyValues[f.name])
      .map((f) => f.label)

    if (missingFields && missingFields.length > 0) {
      setError(`Please fill in required fields: ${missingFields.join(', ')}`)
      setStatus('error')
      return
    }

    if (!connectorId) {
      setError('Integration connector not found. Please refresh and try again.')
      setStatus('error')
      return
    }

    try {
      const res = await apiClient.post<{ id: string }>(
        API_ENDPOINTS.INTEGRATION_CONNECTIONS,
        {
          connector_id: connectorId,
          name: `${integration.name} Connection`,
          auth_data: apiKeyValues,
        }
      )
      setStatus('success')
      setTestResults({
        passed: true,
        message: 'Connection successful!',
        details: ['API key validated', 'Connection stored securely', 'Ready to use'],
      })
      onConnected?.(res.data.id)
      toast.success(`${integration.name} connected successfully`)
    } catch (err) {
      setError(getErrorMessage(err))
      setStatus('error')
    }
  }

  // ── Test connection ──────────────────────────────────────────────────────
  const handleTestConnection = async () => {
    if (!existingConnectionId || existingConnectionId === 'simulated') {
      toast.error('No active connection to test')
      return
    }
    setStatus('testing')
    try {
      const res = await apiClient.post<{ success: boolean; message: string }>(
        API_ENDPOINTS.INTEGRATION_CONNECTION_TEST(existingConnectionId)
      )
      setTestResults({
        passed: res.data.success,
        message: res.data.message || (res.data.success ? 'Connection verified' : 'Test failed'),
        details: res.data.success ? ['Authentication confirmed', 'API access active'] : undefined,
      })
      if (res.data.success) toast.success('Connection verified')
      else toast.error('Connection test failed')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setStatus('idle')
    }
  }

  // ── Disconnect ───────────────────────────────────────────────────────────
  const handleDisconnect = async () => {
    if (!existingConnectionId || existingConnectionId === 'simulated') {
      onDisconnected?.()
      setStatus('idle')
      setTestResults(null)
      setApiKeyValues({})
      return
    }
    try {
      await apiClient.delete(API_ENDPOINTS.INTEGRATION_CONNECTION(existingConnectionId))
      toast.success(`${integration.name} disconnected`)
      onDisconnected?.()
      setStatus('idle')
      setTestResults(null)
      setApiKeyValues({})
    } catch {
      toast.error('Failed to disconnect')
    }
  }

  const handleRetry = () => {
    setStatus('idle')
    setError(null)
    setTestResults(null)
  }

  // ── Render helpers ───────────────────────────────────────────────────────
  const renderOAuthSetup = () => (
    <div className="space-y-6">
      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">Required Permissions</h3>
        </div>
        <p className="text-sm text-gray-600 mb-4">Voicecon will request the following permissions:</p>
        <ul className="space-y-2">
          {integration.permissions.map((perm, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
              <Check className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
              <span>{perm}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Setup Instructions</h3>
        <ol className="space-y-3">
          {integration.setupSteps.map((step, idx) => (
            <li key={idx} className="flex items-start gap-3 text-sm text-gray-700">
              <div className="flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-700 rounded-full text-xs font-medium flex-shrink-0">
                {idx + 1}
              </div>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {!connectorId && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            OAuth for {integration.name} requires provider credentials configured on the server.
            API key integrations (Twilio, Stripe, Airtable, SendGrid) work without extra setup.
          </AlertDescription>
        </Alert>
      )}

      <Alert>
        <Lock className="h-4 w-4" />
        <AlertDescription>
          Your credentials are encrypted and stored securely. Voicecon uses OAuth 2.0 for authentication.
        </AlertDescription>
      </Alert>
    </div>
  )

  const renderApiKeySetup = () => (
    <div className="space-y-6">
      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Key className="w-5 h-5 text-blue-600" />
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
                onChange={(e) => setApiKeyValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
                placeholder={`Enter your ${field.label.toLowerCase()}`}
                required={field.required}
                className="font-mono text-sm mt-1"
              />
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">How to Get Your Credentials</h3>
        <ol className="space-y-3">
          {integration.setupSteps.map((step, idx) => (
            <li key={idx} className="flex items-start gap-3 text-sm text-gray-700">
              <div className="flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-700 rounded-full text-xs font-medium flex-shrink-0">
                {idx + 1}
              </div>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">What Voicecon Can Do</h3>
        </div>
        <ul className="space-y-2">
          {integration.permissions.map((perm, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
              <Check className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
              <span>{perm}</span>
            </li>
          ))}
        </ul>
      </div>

      <Alert>
        <Lock className="h-4 w-4" />
        <AlertDescription>
          Your API keys are encrypted using AES-256 and stored securely.
        </AlertDescription>
      </Alert>
    </div>
  )

  const renderTestResults = () => {
    if (!testResults) return null
    return (
      <div className={`bg-white border-2 rounded-lg p-6 ${testResults.passed ? 'border-green-200 bg-green-50/30' : 'border-red-200 bg-red-50/30'}`}>
        <div className="flex items-start gap-3 mb-4">
          {testResults.passed
            ? <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0" />
            : <XCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
          }
          <div className="flex-1">
            <h3 className={`text-lg font-semibold mb-2 ${testResults.passed ? 'text-green-900' : 'text-red-900'}`}>
              {testResults.message}
            </h3>
            {testResults.details && (
              <ul className="space-y-1">
                {testResults.details.map((detail, idx) => (
                  <li key={idx} className={`flex items-center gap-2 text-sm ${testResults.passed ? 'text-green-700' : 'text-red-700'}`}>
                    <div className={`w-1.5 h-1.5 rounded-full ${testResults.passed ? 'bg-green-600' : 'bg-red-600'}`} />
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
              Browse More
            </Button>
          </div>
        )}
        {!testResults.passed && (
          <Button onClick={handleRetry} variant="outline" className="gap-2">
            <RefreshCw className="w-4 h-4" /> Try Again
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {isConnected && status !== 'success' && (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            This integration is already connected. You can test or disconnect it below.
          </AlertDescription>
        </Alert>
      )}

      {error && status === 'error' && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {testResults && renderTestResults()}

      {status !== 'success' && (
        <>
          {integration.authType === 'oauth2' && renderOAuthSetup()}
          {integration.authType === 'api_key' && renderApiKeySetup()}

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
                      <><Loader2 className="w-4 h-4 animate-spin" /> Connecting…</>
                    ) : (
                      <><ExternalLink className="w-4 h-4" /> Connect with {integration.name}</>
                    )}
                  </Button>
                )}

                {integration.authType === 'api_key' && (
                  <Button
                    onClick={handleApiKeyConnect}
                    disabled={status === 'connecting'}
                    className="gap-2"
                    size="lg"
                  >
                    {status === 'connecting' ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Connecting…</>
                    ) : (
                      <><Key className="w-4 h-4" /> Connect Integration</>
                    )}
                  </Button>
                )}

                <Button variant="outline" onClick={() => router.push('/dashboard/integrations')} size="lg">
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <Button onClick={handleTestConnection} variant="outline" className="gap-2" disabled={status === 'testing'}>
                  {status === 'testing' ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  Test Connection
                </Button>
                <Button onClick={handleDisconnect} variant="destructive" className="gap-2">
                  <XCircle className="w-4 h-4" /> Disconnect
                </Button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
