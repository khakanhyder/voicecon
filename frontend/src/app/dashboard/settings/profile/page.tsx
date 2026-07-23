'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAuthStore } from '@/store/authStore'
import { authService } from '@/lib/auth'
import { getErrorMessage } from '@/lib/api'

const TIMEZONES = [
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

export default function ProfileSettingsPage() {
  const router = useRouter()
  const { user, setUser } = useAuthStore()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone_number: '',
    company_name: '',
    avatar_url: '',
    timezone: 'UTC',
    bio: '',
  })

  // Password change
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' })
  const [changingPw, setChangingPw] = useState(false)

  // Delete account
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const hydrate = (u: NonNullable<typeof user>) =>
    setFormData({
      full_name: u.full_name || '',
      email: u.email || '',
      phone_number: u.phone_number || '',
      company_name: u.company_name || '',
      avatar_url: u.avatar_url || '',
      timezone: u.timezone || 'UTC',
      bio: u.bio || '',
    })

  useEffect(() => {
    let active = true
    authService
      .fetchMe()
      .then((u) => {
        if (!active) return
        setUser(u)
        hydrate(u)
      })
      .catch((e) => toast.error(getErrorMessage(e)))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await authService.updateProfile({
        full_name: formData.full_name,
        phone_number: formData.phone_number || null,
        company_name: formData.company_name || null,
        avatar_url: formData.avatar_url || null,
        timezone: formData.timezone,
        bio: formData.bio || null,
      })
      setUser(updated)
      toast.success('Profile updated')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pw.new_password.length < 8) {
      toast.error('New password must be at least 8 characters')
      return
    }
    if (pw.new_password !== pw.confirm) {
      toast.error('New passwords do not match')
      return
    }
    setChangingPw(true)
    try {
      await authService.changePassword({
        current_password: pw.current_password || undefined,
        new_password: pw.new_password,
      })
      toast.success('Password changed')
      setPw({ current_password: '', new_password: '', confirm: '' })
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setChangingPw(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await authService.deleteAccount()
      toast.success('Account deactivated')
      setUser(null)
      router.push('/login')
    } catch (err) {
      toast.error(getErrorMessage(err))
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-lg bg-muted" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Profile Settings</h1>
        <p className="text-muted-foreground">Manage your personal information and preferences</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Personal Information */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Personal Information</h2>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="fullName">Full Name</Label>
              <Input
                id="fullName"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={formData.email} disabled />
              <p className="text-xs text-muted-foreground">
                Contact support to change your email address
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="+1 (555) 123-4567"
                value={formData.phone_number}
                onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="company">Company</Label>
              <Input
                id="company"
                placeholder="Acme Inc."
                value={formData.company_name}
                onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bio">Bio</Label>
            <Textarea
              id="bio"
              placeholder="Tell us about yourself..."
              value={formData.bio}
              onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
              rows={4}
            />
          </div>
        </div>

        {/* Preferences */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Preferences</h2>

          <div className="space-y-2">
            <Label htmlFor="timezone">Timezone</Label>
            <select
              id="timezone"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={formData.timezone}
              onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
            >
              {TIMEZONES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Avatar */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Profile Picture</h2>

          <div className="flex items-center gap-4">
            {formData.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={formData.avatar_url}
                alt="Avatar"
                className="h-20 w-20 rounded-full object-cover"
              />
            ) : (
              <div className="h-20 w-20 rounded-full bg-primary/10 flex items-center justify-center text-2xl font-semibold text-primary">
                {formData.full_name.charAt(0).toUpperCase() || 'U'}
              </div>
            )}
            <div className="flex-1 space-y-2">
              <Label htmlFor="avatarUrl">Avatar Image URL</Label>
              <Input
                id="avatarUrl"
                placeholder="https://…/avatar.png"
                value={formData.avatar_url}
                onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Paste a public image URL. Saved with your profile.
              </p>
            </div>
          </div>
        </div>

        <div>
          <Button type="submit" size="lg" disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </form>

      {/* Change Password */}
      <form onSubmit={handleChangePassword} className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Change Password</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="curPw">Current Password</Label>
            <Input
              id="curPw"
              type="password"
              value={pw.current_password}
              onChange={(e) => setPw({ ...pw, current_password: e.target.value })}
              placeholder="Leave blank if none set"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="newPw">New Password</Label>
            <Input
              id="newPw"
              type="password"
              value={pw.new_password}
              onChange={(e) => setPw({ ...pw, new_password: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirmPw">Confirm New Password</Label>
            <Input
              id="confirmPw"
              type="password"
              value={pw.confirm}
              onChange={(e) => setPw({ ...pw, confirm: e.target.value })}
            />
          </div>
        </div>
        <Button type="submit" variant="outline" disabled={changingPw}>
          {changingPw ? 'Updating…' : 'Update Password'}
        </Button>
      </form>

      {/* Danger Zone */}
      <div className="rounded-lg border-2 border-destructive/20 bg-destructive/5 p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-destructive">Danger Zone</h2>
          <p className="text-sm text-muted-foreground">
            Deactivating your account signs you out and disables access. Contact support to restore
            it.
          </p>
        </div>
        {confirmDelete ? (
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">Are you sure?</span>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? 'Deactivating…' : 'Yes, deactivate my account'}
            </Button>
            <Button variant="outline" onClick={() => setConfirmDelete(false)} disabled={deleting}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="destructive"
            onClick={() => setConfirmDelete(true)}
          >
            Delete Account
          </Button>
        )}
      </div>
    </div>
  )
}
