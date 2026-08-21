'use client'

/**
 * Settings → General.
 *
 * The only account-level preferences that are not tied to a person's identity
 * (Profile), the money (Billing), the people (Team) or the workspace record
 * (Workspace) — plus a read-only orientation strip so this page answers "who am
 * I signed in as, where, and on what plan" without sending anyone hunting.
 *
 * Deliberately not a hub of links: the sidebar already lists every settings
 * page directly below this one, so cards repeating those links earned nothing.
 */

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { Building2, CreditCard, UserRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { authService } from '@/lib/auth'
import { getErrorMessage } from '@/lib/api'
import { PERMISSIONS } from '@/lib/workspace'
import { PLAN_LABELS } from '@/lib/entitlements'
import { useAuthStore } from '@/store/authStore'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { useEntitlementStore } from '@/store/entitlementStore'

// Matches the trigger styling the agent builder's selects already use, so a
// dropdown looks the same wherever it appears.
const selectTriggerClass =
  'w-full h-[45px] rounded-xl border border-slate-200 bg-white px-3 text-[14px] font-poppins text-[#000000] outline-none transition-colors hover:border-slate-300 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 data-[state=open]:border-[#0F6A59] data-[state=open]:ring-2 data-[state=open]:ring-[#0F6A59]/15'
const labelClass = 'text-[14px] font-bold text-[#000000] font-poppins block'

const TIMEZONES: [string, string][] = [
  ['UTC', 'UTC'],
  ['America/New_York', 'Eastern Time (ET)'],
  ['America/Chicago', 'Central Time (CT)'],
  ['America/Denver', 'Mountain Time (MT)'],
  ['America/Los_Angeles', 'Pacific Time (PT)'],
  ['Europe/London', 'London (GMT)'],
  ['Europe/Paris', 'Paris (CET)'],
  ['Asia/Karachi', 'Karachi (PKT)'],
  ['Asia/Tokyo', 'Tokyo (JST)'],
]

// Codes, not display names: `users.language` is a 10-character column and the
// value is meant to be a locale the app can key off later.
const LANGUAGES: [string, string][] = [
  ['en', 'English'],
  ['es', 'Spanish'],
  ['fr', 'French'],
  ['de', 'German'],
  ['ar', 'Arabic'],
  ['hi', 'Hindi'],
  ['pt', 'Portuguese'],
]

const ROLE_LABELS: Record<string, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
}

const STATUS_LABELS: Record<string, string> = {
  trialing: 'Free trial',
  active: 'Active',
  past_due: 'Payment failed',
  grace: 'Trial ended',
  expired: 'Expired',
  canceled: 'Cancelled',
  incomplete: 'Incomplete',
}

const STATUS_STYLES: Record<string, string> = {
  trialing: 'bg-blue-100 text-blue-700',
  active: 'bg-emerald-100 text-emerald-700',
  past_due: 'bg-amber-100 text-amber-700',
  grace: 'bg-amber-100 text-amber-700',
  expired: 'bg-red-100 text-red-600',
  canceled: 'bg-slate-100 text-slate-600',
}

/** Keeps a value the server already holds selectable even if it predates the list. */
function withCurrent(options: [string, string][], value: string): [string, string][] {
  if (!value || options.some(([option]) => option === value)) return options
  return [[value, value], ...options]
}

function Tile({
  icon,
  title,
  rows,
  action,
}: {
  icon: React.ReactNode
  title: string
  rows: { label: string; value: React.ReactNode }[]
  action?: { label: string; href: string }
}) {
  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#0F6A59]/10 text-[#106959]">
          {icon}
        </span>
        <h3 className="text-[16px] font-bold font-poppins text-[#000000]">{title}</h3>
      </div>

      <dl className="flex-1">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-slate-100 py-2.5 last:border-0"
          >
            <dt className="shrink-0 text-sm text-slate-600">{row.label}</dt>
            <dd className="min-w-0 break-words text-left text-sm font-semibold text-slate-900 sm:text-right">
              {row.value}
            </dd>
          </div>
        ))}
      </dl>

      {action && (
        <Link
          href={action.href}
          className="mt-4 text-sm font-semibold text-[#106959] hover:underline"
        >
          {action.label} →
        </Link>
      )}
    </div>
  )
}

export default function SettingsGeneralPage() {
  const { user, setUser } = useAuthStore()
  const workspace = useWorkspaceStore((s) => s.current)
  const can = useWorkspaceStore((s) => s.can)
  const entitlements = useEntitlementStore((s) => s.entitlements)

  const [loading, setLoading] = useState(!user)
  const [saving, setSaving] = useState(false)
  const [prefs, setPrefs] = useState({ timezone: 'UTC', language: 'en' })

  useEffect(() => {
    let active = true
    // The store is usually warm from the dashboard layout; refetch anyway so a
    // deep link straight to Settings edits the current values, not stale ones.
    authService
      .fetchMe()
      .then((u) => {
        if (!active) return
        setUser(u)
        setPrefs({ timezone: u.timezone || 'UTC', language: u.language || 'en' })
      })
      .catch((e) => toast.error(getErrorMessage(e)))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const dirty =
    !!user && (prefs.timezone !== (user.timezone || 'UTC') || prefs.language !== (user.language || 'en'))

  const timezones = useMemo(() => withCurrent(TIMEZONES, prefs.timezone), [prefs.timezone])
  const languages = useMemo(() => withCurrent(LANGUAGES, prefs.language), [prefs.language])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await authService.updateProfile({
        timezone: prefs.timezone,
        language: prefs.language,
      })
      setUser(updated)
      toast.success('Preferences saved')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const planName =
    entitlements?.plan_name ||
    (entitlements?.plan_slug ? PLAN_LABELS[entitlements.plan_slug] ?? entitlements.plan_slug : null) ||
    (workspace?.plan_type ? PLAN_LABELS[workspace.plan_type] ?? workspace.plan_type : '—')

  const status = entitlements?.status
  const statusBadge = status ? (
    <span
      className={`rounded px-2 py-0.5 text-xs font-semibold ${
        STATUS_STYLES[status] ?? 'bg-slate-100 text-slate-600'
      }`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  ) : (
    '—'
  )

  const renewal = entitlements?.is_trial
    ? entitlements.days_remaining != null
      ? `${entitlements.days_remaining} ${entitlements.days_remaining === 1 ? 'day' : 'days'} left`
      : '—'
    : entitlements?.current_period_end
      ? new Date(entitlements.current_period_end).toLocaleDateString('en-GB', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
        })
      : '—'

  return (
    <div className="w-full space-y-6">
      {/* Preferences */}
      <form onSubmit={handleSave} className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Preferences</h2>
          <p className="mt-1 text-sm text-slate-600">
            How dates, times and copy are presented to you across the dashboard.
          </p>
        </div>

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            <div className="h-[69px] animate-pulse rounded-xl bg-slate-100" />
            <div className="h-[69px] animate-pulse rounded-xl bg-slate-100" />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            <div className="space-y-2">
              <Label htmlFor="timezone" className={labelClass}>
                Timezone
              </Label>
              <Select
                value={prefs.timezone}
                onValueChange={(value) => setPrefs({ ...prefs, timezone: value })}
              >
                <SelectTrigger id="timezone" className={selectTriggerClass}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {timezones.map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Call times, schedules and reports are shown in this zone.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="language" className={labelClass}>
                Language
              </Label>
              <Select
                value={prefs.language}
                onValueChange={(value) => setPrefs({ ...prefs, language: value })}
              >
                <SelectTrigger id="language" className={selectTriggerClass}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {languages.map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Saved to your account. The dashboard is English-only today — this
                is the preference the rest of the product will read as it lands.
              </p>
            </div>
          </div>
        )}

        <div>
          <Button type="submit" disabled={saving || !dirty} className="w-full sm:w-auto">
            {saving ? 'Saving…' : 'Save preferences'}
          </Button>
        </div>
      </form>

      {/* At a glance */}
      <div>
        <h2 className="mb-3 text-xl font-semibold">At a glance</h2>
        <div className="grid gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <Tile
            icon={<UserRound className="h-5 w-5" />}
            title="Account"
            rows={[
              { label: 'Name', value: user?.full_name || '—' },
              { label: 'Email', value: user?.email || '—' },
            ]}
            action={{ label: 'Edit profile', href: '/dashboard/settings/profile' }}
          />

          <Tile
            icon={<Building2 className="h-5 w-5" />}
            title="Workspace"
            rows={[
              { label: 'Name', value: workspace?.name || '—' },
              {
                label: 'Your role',
                value: workspace ? ROLE_LABELS[workspace.role] ?? workspace.role : '—',
              },
              {
                label: 'Members',
                value: workspace ? String(workspace.member_count) : '—',
              },
            ]}
            action={{ label: 'Manage workspace', href: '/dashboard/settings/workspace' }}
          />

          <Tile
            icon={<CreditCard className="h-5 w-5" />}
            title="Plan"
            rows={[
              { label: 'Plan', value: planName },
              { label: 'Status', value: statusBadge },
              { label: entitlements?.is_trial ? 'Trial' : 'Renews', value: renewal },
            ]}
            // Billing is admin-and-up; members see where they stand without a
            // link the API would refuse. Until the workspace lands there is no
            // permission set to judge by, so the link stays rather than flashing.
            action={
              !workspace || can(PERMISSIONS.billingRead)
                ? { label: 'Manage billing', href: '/dashboard/settings/billing' }
                : undefined
            }
          />
        </div>
      </div>
    </div>
  )
}
