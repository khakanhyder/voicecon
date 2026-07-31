'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

interface ApiKey {
  id: string
  name: string
  key_prefix: string
  is_active: boolean
  last_used_at: string | null
  expires_at: string | null
  created_at: string
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function APIKeysPage() {
  const [keyName, setKeyName] = useState('')
  const [creating, setCreating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [newKey, setNewKey] = useState('')
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = async () => {
    try {
      const { data } = await apiClient.get<ApiKey[]>(API_ENDPOINTS.API_KEYS)
      setApiKeys(data)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!keyName.trim()) return
    setCreating(true)
    try {
      const { data } = await apiClient.post<{ key: string }>(API_ENDPOINTS.API_KEYS, {
        name: keyName.trim(),
        scopes: [],
      })
      setNewKey(data.key)
      setKeyName('')
      toast.success('API key created')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const handleRegenerate = async (id: string) => {
    if (!confirm('Regenerate this key? The current key will stop working immediately.')) return
    setBusyId(id)
    try {
      const { data } = await apiClient.post<{ key: string }>(API_ENDPOINTS.API_KEY_REGENERATE(id))
      setNewKey(data.key)
      toast.success('API key regenerated')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const handleRevoke = async (id: string) => {
    if (!confirm('Revoke this key? This cannot be undone.')) return
    setBusyId(id)
    try {
      await apiClient.delete(API_ENDPOINTS.API_KEY(id))
      toast.success('API key revoked')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  return (
    <div className="space-y-6">


      {/* New API Key Alert */}
      {newKey && (
        <div className="rounded-[10px] border border-[#000000] bg-[#0F6A590A] p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-primary">New API Key Created</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Make sure to copy your API key now. You won&apos;t be able to see it again!
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setNewKey('')}>
              ✕
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Input value={newKey} readOnly className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 text-[14px]"/>
            <Button onClick={() => copyToClipboard(newKey)}>Copy</Button>
          </div>
        </div>
      )}

      {/* Create API Key */}
      <div className="rounded-[10px] border border-[#000000] bg-white p-6 space-y-4">
        <h2 className="text-xl font-semibold">Create New API Key</h2>
        <form onSubmit={handleCreateKey} className="flex flex-col sm:flex-row sm:items-end gap-4">
          <div className="flex-1 space-y-2">
            <Label htmlFor="keyName" className="text-[14px] font-bold text-[#000000] font-poppins block">Key Name</Label>
            <Input
              id="keyName"
              placeholder="Production API"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              required
             className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 text-[14px]" />
          </div>
          <div className="flex items-end w-full sm:w-auto">
            <Button type="submit" disabled={creating} className="w-full sm:w-auto h-[45px]">
              {creating ? 'Creating…' : 'Create Key'}
            </Button>
          </div>
        </form>
      </div>

      {/* API Keys List */}
      <div className="rounded-[10px] border border-[#000000] bg-white p-6 space-y-4">
        <h2 className="text-xl font-semibold">Your API Keys</h2>

        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : apiKeys.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No API keys yet. Create one above to get started.
          </p>
        ) : (
          <div className="space-y-4">
            {apiKeys.map((apiKey) => (
              <div
                key={apiKey.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-[10px] border border-[#000000] p-4 bg-white"
              >
                <div className="space-y-1">
                  <p className="font-medium break-all">
                    {apiKey.name}
                    {!apiKey.is_active && (
                      <span className="ml-2 rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        inactive
                      </span>
                    )}
                  </p>
                  <p className="font-mono text-sm text-muted-foreground break-all">
                    {apiKey.key_prefix}••••••••••••
                  </p>
                  <div className="flex flex-col sm:flex-row sm:gap-4 text-xs text-muted-foreground mt-2 sm:mt-0">
                    <span>Created {formatDate(apiKey.created_at)}</span>
                    <span className="hidden sm:inline">·</span>
                    <span>Last used {apiKey.last_used_at ? formatDate(apiKey.last_used_at) : 'never'}</span>
                  </div>
                </div>
                <div className="flex gap-2 w-full sm:w-auto">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 sm:flex-none justify-center"
                    disabled={busyId === apiKey.id}
                    onClick={() => handleRegenerate(apiKey.id)}
                  >
                    Regenerate
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="flex-1 sm:flex-none justify-center"
                    disabled={busyId === apiKey.id}
                    onClick={() => handleRevoke(apiKey.id)}
                  >
                    Revoke
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Security Notice */}
      <div className="rounded-[10px] border border-[#000000] bg-[#0F6A590A] p-6">
        <h3 className="font-semibold text-destructive mb-2">Security Best Practices</h3>
        <ul className="space-y-1 text-sm text-muted-foreground list-disc list-inside">
          <li>Never share your API keys publicly or commit them to version control</li>
          <li>Rotate your keys regularly for enhanced security</li>
          <li>Use different keys for development and production environments</li>
          <li>Revoke keys immediately if you suspect they&apos;ve been compromised</li>
        </ul>
      </div>
    </div>
  )
}
