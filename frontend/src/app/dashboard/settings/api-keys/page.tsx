'use client'

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_BASE, API_ENDPOINTS } from '@/lib/constants'
import { PERMISSIONS } from '@/lib/workspace'
import { usePermission } from '@/store/workspaceStore'

interface ApiKey {
  id: string
  name: string
  key_prefix: string
  scopes: string[]
  is_active: boolean
  last_used_at: string | null
  expires_at: string | null
  created_at: string
}

/** Expiry presets, in days. `null` is "never" — the default. */
const EXPIRY_OPTIONS: [string, number | null][] = [
  ['Never', null],
  ['30 days', 30],
  ['90 days', 90],
  ['1 year', 365],
]

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

function isExpired(key: ApiKey) {
  return key.expires_at != null && new Date(key.expires_at) <= new Date()
}

/** Group scopes by their resource ("agents:read" → "agents") so the picker is scannable. */
function groupScopes(scopes: string[]) {
  const groups = new Map<string, string[]>()
  for (const scope of scopes) {
    const resource = scope.split(':')[0]
    groups.set(resource, [...(groups.get(resource) ?? []), scope])
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
}

export default function APIKeysPage() {
  const canManage = usePermission(PERMISSIONS.apiKeysManage)

  const [keyName, setKeyName] = useState('')
  const [expiryDays, setExpiryDays] = useState<number | null>(null)
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])
  const [showScopePicker, setShowScopePicker] = useState(false)

  const [creating, setCreating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [newKey, setNewKey] = useState('')
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [availableScopes, setAvailableScopes] = useState<string[]>([])
  const [busyId, setBusyId] = useState<string | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const scopeGroups = useMemo(() => groupScopes(availableScopes), [availableScopes])

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
    // The server owns the list of grantable scopes, so the picker can never
    // offer something key creation would reject.
    apiClient
      .get<string[]>(API_ENDPOINTS.API_KEY_SCOPES)
      .then(({ data }) => setAvailableScopes(data))
      .catch(() => setAvailableScopes([]))
  }, [])

  const toggleScope = (scope: string) =>
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    )

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!keyName.trim()) return
    setCreating(true)
    try {
      const expires_at =
        expiryDays == null
          ? null
          : new Date(Date.now() + expiryDays * 86_400_000).toISOString().replace('Z', '')
      const { data } = await apiClient.post<{ key: string }>(API_ENDPOINTS.API_KEYS, {
        name: keyName.trim(),
        scopes: selectedScopes,
        expires_at,
      })
      setNewKey(data.key)
      setKeyName('')
      setSelectedScopes([])
      setExpiryDays(null)
      setShowScopePicker(false)
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

  const handleToggleActive = async (key: ApiKey) => {
    setBusyId(key.id)
    try {
      await apiClient.patch(API_ENDPOINTS.API_KEY(key.id), { is_active: !key.is_active })
      toast.success(key.is_active ? 'API key disabled' : 'API key enabled')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const handleRename = async (id: string) => {
    if (!renameValue.trim()) return
    setBusyId(id)
    try {
      await apiClient.patch(API_ENDPOINTS.API_KEY(id), { name: renameValue.trim() })
      setRenamingId(null)
      toast.success('API key renamed')
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
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
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
            <Input value={newKey} readOnly className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
            <Button onClick={() => copyToClipboard(newKey)}>Copy</Button>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">Use it like this:</p>
            <pre className="overflow-x-auto rounded-[8px] bg-black/85 p-3 text-[12px] leading-relaxed text-white">
              {`curl ${API_BASE}/api/v1/agents \\
  -H "Authorization: Bearer ${newKey}"`}
            </pre>
            <p className="text-xs text-muted-foreground">
              An <code>X-API-Key</code> header works too. The key acts only in this workspace.
            </p>
          </div>
        </div>
      )}

      {/* Create API Key */}
      {canManage && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-semibold">Create New API Key</h2>
          <form onSubmit={handleCreateKey} className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-end gap-4">
              <div className="flex-1 space-y-2">
                <Label htmlFor="keyName" className="text-base font-bold text-[#000000] font-poppins block">Key Name</Label>
                <Input
                  id="keyName"
                  placeholder="Production API"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  required
                  className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
              </div>
              <div className="space-y-2 sm:w-48">
                <Label htmlFor="expiry" className="text-[14px] font-bold text-[#000000] font-poppins block">Expires</Label>
                <select
                  id="expiry"
                  value={expiryDays ?? ''}
                  onChange={(e) => setExpiryDays(e.target.value === '' ? null : Number(e.target.value))}
                  className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]"
                >
                  {EXPIRY_OPTIONS.map(([label, days]) => (
                    <option key={label} value={days ?? ''}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-end w-full sm:w-auto">
                <Button type="submit" disabled={creating} className="w-full sm:w-auto h-[45px]">
                  {creating ? 'Creating…' : 'Create Key'}
                </Button>
              </div>
            </div>

            {/* Scopes */}
            {availableScopes.length > 0 && (
              <div className="space-y-3 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={() => setShowScopePicker((v) => !v)}
                  className="text-base font-medium text-[#106959] hover:underline"
                >
                  {showScopePicker ? '▾' : '▸'} Permissions ({selectedScopes.length === 0 ? 'full access' : `${selectedScopes.length} selected`})
                </button>
                <p className="text-sm text-muted-foreground">
                  Leave empty for full access. The key can then do anything your role allows.
                  Selecting scopes limits it further. A key can never exceed your own permissions,
                  and can never manage keys, team, or billing.
                </p>
                {showScopePicker && (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {scopeGroups.map(([resource, scopes]) => (
                      <div key={resource} className="space-y-1.5">
                        <p className="text-xs font-bold uppercase tracking-wide text-black/50">{resource.replace('_', ' ')}</p>
                        {scopes.map((scope) => (
                          <label key={scope} className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                              type="checkbox"
                              checked={selectedScopes.includes(scope)}
                              onChange={() => toggleScope(scope)}
                              className="rounded border-slate-300"
                            />
                            <span className="font-mono text-[12px]">{scope.split(':')[1]}</span>
                          </label>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </form>
        </div>
      )}

      {/* API Keys List */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <h2 className="text-xl font-semibold">Your API Keys</h2>

        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : apiKeys.length === 0 ? (
          <p className="text-base text-muted-foreground">
            {canManage
              ? 'No API keys yet. Create one above to get started.'
              : 'No API keys in this workspace. Ask an admin to create one.'}
          </p>
        ) : (
          <div className="space-y-4">
            {apiKeys.map((apiKey) => (
              <div
                key={apiKey.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4 bg-white"
              >
                <div className="space-y-1 min-w-0">
                  {renamingId === apiKey.id ? (
                    <div className="flex items-center gap-2">
                      <Input
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRename(apiKey.id)
                          if (e.key === 'Escape') setRenamingId(null)
                        }}
                        autoFocus
                        className="h-9 w-56 rounded-xl border border-slate-200 px-2 text-[14px]"
                      />
                      <Button size="sm" onClick={() => handleRename(apiKey.id)} disabled={busyId === apiKey.id}>
                        Save
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setRenamingId(null)}>
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <p className="font-medium break-all">
                      {apiKey.name}
                      {isExpired(apiKey) ? (
                        <span className="ml-2 rounded bg-destructive/10 px-2 py-0.5 text-xs text-destructive">
                          expired
                        </span>
                      ) : !apiKey.is_active ? (
                        <span className="ml-2 rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          disabled
                        </span>
                      ) : null}
                    </p>
                  )}
                  <p className="font-mono text-base text-muted-foreground break-all">
                    {apiKey.key_prefix}••••••••••••
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {apiKey.scopes.length === 0
                      ? 'Full access'
                      : `${apiKey.scopes.length} scope${apiKey.scopes.length === 1 ? '' : 's'}: ${apiKey.scopes.join(', ')}`}
                  </p>
                  <div className="flex flex-col sm:flex-row sm:gap-4 text-sm text-muted-foreground mt-2 sm:mt-0">
                    <span>Created {formatDate(apiKey.created_at)}</span>
                    <span className="hidden sm:inline">·</span>
                    <span>Last used {apiKey.last_used_at ? formatDate(apiKey.last_used_at) : 'never'}</span>
                    <span className="hidden sm:inline">·</span>
                    <span>{apiKey.expires_at ? `Expires ${formatDate(apiKey.expires_at)}` : 'Never expires'}</span>
                  </div>
                </div>
                {canManage && (
                  <div className="flex flex-wrap gap-2 w-full sm:w-auto">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 sm:flex-none justify-center"
                      disabled={busyId === apiKey.id}
                      onClick={() => {
                        setRenamingId(apiKey.id)
                        setRenameValue(apiKey.name)
                      }}
                    >
                      Rename
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 sm:flex-none justify-center"
                      disabled={busyId === apiKey.id}
                      onClick={() => handleToggleActive(apiKey)}
                    >
                      {apiKey.is_active ? 'Disable' : 'Enable'}
                    </Button>
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
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Security Notice */}
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
        <h3 className="font-semibold text-destructive mb-2">Security Best Practices</h3>
        <ul className="space-y-1 text-base text-muted-foreground list-disc list-inside">
          <li>Never share your API keys publicly or commit them to version control</li>
          <li>Rotate your keys regularly for enhanced security</li>
          <li>Use different keys for development and production environments</li>
          <li>Grant only the scopes an integration actually needs</li>
          <li>Revoke keys immediately if you suspect they&apos;ve been compromised</li>
        </ul>
      </div>
    </div>
  )
}
