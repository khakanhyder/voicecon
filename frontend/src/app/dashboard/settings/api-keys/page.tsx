'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function APIKeysPage() {
  const [keyName, setKeyName] = useState('')
  const [showNewKey, setShowNewKey] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [apiKeys] = useState([
    {
      id: '1',
      name: 'Production API',
      key: 'vcon_live_••••••••••••••••',
      created: '2024-01-15',
      lastUsed: '2 hours ago',
    },
    {
      id: '2',
      name: 'Development',
      key: 'vcon_test_••••••••••••••••',
      created: '2024-01-10',
      lastUsed: '1 day ago',
    },
  ])

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    // TODO: Implement API call to create API key
    const mockKey = `vcon_live_${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`
    setNewKey(mockKey)
    setShowNewKey(true)
    setKeyName('')
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
        <p className="text-muted-foreground">
          Manage your API keys for integrations
        </p>
      </div>

      {/* New API Key Alert */}
      {showNewKey && (
        <div className="rounded-lg border border-primary bg-primary/5 p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-primary">New API Key Created</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Make sure to copy your API key now. You won't be able to see it again!
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowNewKey(false)}
            >
              ✕
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Input
              value={newKey}
              readOnly
              className="font-mono text-sm"
            />
            <Button onClick={() => copyToClipboard(newKey)}>
              Copy
            </Button>
          </div>
        </div>
      )}

      {/* Create API Key */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Create New API Key</h2>

        <form onSubmit={handleCreateKey} className="flex gap-4">
          <div className="flex-1 space-y-2">
            <Label htmlFor="keyName">Key Name</Label>
            <Input
              id="keyName"
              placeholder="Production API"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              required
            />
          </div>
          <div className="flex items-end">
            <Button type="submit">Create Key</Button>
          </div>
        </form>
      </div>

      {/* API Keys List */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Your API Keys</h2>

        <div className="space-y-4">
          {apiKeys.map((apiKey) => (
            <div
              key={apiKey.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div className="space-y-1">
                <p className="font-medium">{apiKey.name}</p>
                <p className="font-mono text-sm text-muted-foreground">{apiKey.key}</p>
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>Created {apiKey.created}</span>
                  <span>Last used {apiKey.lastUsed}</span>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  Regenerate
                </Button>
                <Button variant="destructive" size="sm">
                  Revoke
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* API Documentation */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">API Documentation</h2>

        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Use your API keys to authenticate requests to the Voicecon API.
          </p>

          <div className="rounded-lg bg-muted p-4 font-mono text-sm">
            <p className="text-muted-foreground mb-2"># Example request</p>
            <p>curl https://api.voicecon.com/v1/agents \</p>
            <p className="ml-4">-H "Authorization: Bearer YOUR_API_KEY"</p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" size="sm">
              View Full Documentation
            </Button>
            <Button variant="outline" size="sm">
              API Reference
            </Button>
          </div>
        </div>
      </div>

      {/* Security Notice */}
      <div className="rounded-lg border-2 border-destructive/20 bg-destructive/5 p-6">
        <h3 className="font-semibold text-destructive mb-2">Security Best Practices</h3>
        <ul className="space-y-1 text-sm text-muted-foreground list-disc list-inside">
          <li>Never share your API keys publicly or commit them to version control</li>
          <li>Rotate your keys regularly for enhanced security</li>
          <li>Use different keys for development and production environments</li>
          <li>Revoke keys immediately if you suspect they've been compromised</li>
        </ul>
      </div>
    </div>
  )
}
