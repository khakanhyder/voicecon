'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/components/ui/password-input'
import { AvatarUploader } from '@/components/ui/avatar-uploader'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAuthStore } from '@/store/authStore'
import { authService } from '@/lib/auth'
import { QUERY_KEYS } from '@/lib/constants'
import { getErrorMessage } from '@/lib/api'
import { ChangeEmailDialog } from '@/components/settings/ChangeEmailDialog'
import { DeactivateAccountDialog } from '@/components/settings/DeactivateAccountDialog'
import { PhoneInput } from '@/components/ui/phone-input'
import { FieldError, errorInputClass, fieldErrorProps } from '@/components/ui/field-error'
import { personNameError, validatePersonName } from '@/lib/validation'
import {
  DEFAULT_PHONE_COUNTRY,
  phoneError,
  phoneFromStored,
  phoneToE164,
  type PhoneValue,
} from '@/lib/phone'

export default function ProfileSettingsPage() {
  const router = useRouter()
  const { user, setUser: setStoreUser } = useAuthStore()
  const queryClient = useQueryClient()

  // Every place that shows the signed-in user reads one of two copies: the
  // store (sidebar) or the cached /users/me query (useAuth, so the top bar).
  // Writing only the store left the query's copy — fresh for five minutes —
  // serving the old picture and name until a reload. Write both.
  const setUser = (u: NonNullable<typeof user>) => {
    setStoreUser(u)
    queryClient.setQueryData([QUERY_KEYS.ME], u)
  }

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    company_name: '',
    avatar_url: '',
    bio: '',
  })

  // The user's own number — not the company's, which lives in the company profile.
  const [phone, setPhone] = useState<PhoneValue>({ country: DEFAULT_PHONE_COUNTRY, national: '' })
  const [phoneProblem, setPhoneProblem] = useState<string | undefined>()
  const [nameProblem, setNameProblem] = useState<string | undefined>()

  // Password change
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' })
  const [changingPw, setChangingPw] = useState(false)

  // Change email
  const [changingEmail, setChangingEmail] = useState(false)

  // Deactivate account
  const [deactivating, setDeactivating] = useState(false)

  const hydrate = (u: NonNullable<typeof user>) =>
    setFormData({
      full_name: u.full_name || '',
      email: u.email || '',
      company_name: u.company_name || '',
      avatar_url: u.avatar_url || '',
      bio: u.bio || '',
    })

  const hydratePhone = (u: NonNullable<typeof user>) => setPhone(phoneFromStored(u.phone_number))

  useEffect(() => {
    let active = true
    authService
      .fetchMe()
      .then((u) => {
        if (!active) return
        setUser(u)
        hydrate(u)
        hydratePhone(u)
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
    // Both are checked and reported together, so fixing one never reveals the
    // other only on the next click.
    const nameIssue = personNameError(formData.full_name)
    const problem = phoneError(phone)
    setNameProblem(nameIssue)
    setPhoneProblem(problem)
    if (nameIssue) {
      document.getElementById('fullName')?.focus()
      return
    }
    if (problem) {
      document.getElementById('phone')?.focus()
      return
    }
    setSaving(true)
    try {
      const updated = await authService.updateProfile({
        full_name: validatePersonName(formData.full_name),
        phone_number: phoneToE164(phone),
        company_name: formData.company_name || null,
        avatar_url: formData.avatar_url || null,
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

  // Uploading is its own request, not part of the form save: the file goes to
  // storage and the row is updated server-side, so the URL it returns is
  // authoritative and gets folded straight back into the form state.
  const handleAvatarUpload = async (file: File) => {
    try {
      const updated = await authService.uploadAvatar(file)
      setUser(updated)
      setFormData((f) => ({ ...f, avatar_url: updated.avatar_url || '' }))
      toast.success('Profile picture updated')
    } catch (err) {
      toast.error(getErrorMessage(err))
      throw err
    }
  }

  const handleAvatarRemove = async () => {
    try {
      const updated = await authService.removeAvatar()
      setUser(updated)
      setFormData((f) => ({ ...f, avatar_url: '' }))
      toast.success('Profile picture removed')
    } catch (err) {
      toast.error(getErrorMessage(err))
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

  // The dialog has already deactivated the account and cleared this browser's
  // session by the time this runs; all that is left is to leave.
  const handleDeactivated = () => {
    setDeactivating(false)
    toast.success('Your account has been deactivated')
    setStoreUser(null)
    queryClient.clear()
    router.push('/login')
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
      <form onSubmit={handleSubmit} className="space-y-8">
     {/* Avatar */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-semibold">Profile Picture</h2>

          <AvatarUploader
            src={formData.avatar_url || null}
            name={formData.full_name}
            onUpload={handleAvatarUpload}
            onRemove={handleAvatarRemove}
            disabled={saving}
          />

          <details className="pt-1">
            <summary className="cursor-pointer text-xs text-muted-foreground hover:text-slate-700">
              Or paste an image URL
            </summary>
            <div className="mt-3 space-y-2">
              <Label htmlFor="avatarUrl" className="text-[14px] font-bold text-[#000000] font-poppins block">Avatar Image URL</Label>
              <Input
                id="avatarUrl"
                placeholder="https://…/avatar.png"
                value={formData.avatar_url}
                onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
                className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
              <p className="text-xs text-muted-foreground">
                Kept for pictures already hosted elsewhere — a Google account
                photo, for instance. Saved with the rest of the form.
              </p>
            </div>
          </details>
        </div>

        {/* Personal Information */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-semibold">Personal Information</h2>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="fullName" className="text-[14px] font-bold text-[#000000] font-poppins block">Full Name</Label>
              <Input
                id="fullName"
                value={formData.full_name}
                onChange={(e) => {
                  setFormData({ ...formData, full_name: e.target.value })
                  if (nameProblem) setNameProblem(undefined)
                }}
                onBlur={() => setNameProblem(personNameError(formData.full_name))}
                maxLength={100}
                autoComplete="name"
                {...fieldErrorProps('fullName', nameProblem)}
                className={`w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px] ${nameProblem ? errorInputClass : ''}`} />
              <FieldError id="fullName-error" message={nameProblem} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-[14px] font-bold text-[#000000] font-poppins block">Email</Label>
              <div className="flex gap-2">
                <Input id="email" type="email" value={formData.email} readOnly aria-describedby="email-help" className="w-full h-[45px] min-w-0 rounded-xl border border-slate-200 outline-none bg-slate-50 text-slate-600 font-poppins px-3 text-[14px]" />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setChangingEmail(true)}
                  className="h-[45px] flex-shrink-0 rounded-xl"
                >
                  Change
                </Button>
              </div>
              <p id="email-help" className="text-xs text-muted-foreground">
                We&apos;ll confirm the new address with a code before anything changes.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone" className="text-[14px] font-bold text-[#000000] font-poppins block">Phone Number</Label>
              <PhoneInput
                id="phone"
                value={phone}
                onChange={(v) => {
                  setPhone(v)
                  setPhoneProblem(undefined)
                }}
                disabled={saving}
                inputClassName="h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px] disabled:opacity-50"
                error={phoneProblem}
                placeholder="(555) 123-4567"
              />
              <FieldError id="phone-error" message={phoneProblem} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="company" className="text-[14px] font-bold text-[#000000] font-poppins block">Company</Label>
              <Input
                id="company"
                placeholder="Acme Inc."
                value={formData.company_name}
                onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bio" className="text-[14px] font-bold text-[#000000] font-poppins block">Bio</Label>
            <Textarea
              id="bio"
              placeholder="Tell us about yourself..."
              value={formData.bio}
              onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
              rows={4}
              className="w-full rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 py-2 text-[14px]" />
          </div>

          <p className="text-xs text-muted-foreground">
            Timezone and language moved to{' '}
            <Link href="/dashboard/settings" className="font-semibold text-[#106959] hover:underline">
              Settings → General
            </Link>
            .
          </p>
        </div>

        <div>
          <Button type="submit" size="lg" disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </form>

      {/* Change Password */}
      <form onSubmit={handleChangePassword} className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <h2 className="text-xl font-semibold">Change Password</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="curPw" className="text-[14px] font-bold text-[#000000] font-poppins block">Current Password</Label>
            <PasswordInput
              id="curPw"
              value={pw.current_password}
              onChange={(e) => setPw({ ...pw, current_password: e.target.value })}
              placeholder="Leave blank if none set"
              className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="newPw" className="text-[14px] font-bold text-[#000000] font-poppins block">New Password</Label>
            <PasswordInput
              id="newPw"
              value={pw.new_password}
              onChange={(e) => setPw({ ...pw, new_password: e.target.value })}
              className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirmPw" className="text-[14px] font-bold text-[#000000] font-poppins block">Confirm New Password</Label>
            <PasswordInput
              id="confirmPw"
              value={pw.confirm}
              onChange={(e) => setPw({ ...pw, confirm: e.target.value })}
              className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
          </div>
        </div>
        <Button type="submit" variant="outline" disabled={changingPw}>
          {changingPw ? 'Updating…' : 'Update Password'}
        </Button>
      </form>

      {/* Danger Zone */}
      <div className="rounded-2xl border border-red-200 bg-red-50/40 p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-destructive">Danger Zone</h2>
          <p className="text-sm text-muted-foreground">
            Deactivating your account signs you out and switches off the workspaces you own. The
            account is kept for a recovery period, during which our support team can reactivate
            it, and is then permanently deleted.
          </p>
        </div>
        <Button type="button" variant="destructive" onClick={() => setDeactivating(true)}>
          Deactivate account
        </Button>
      </div>
      <DeactivateAccountDialog
        open={deactivating}
        onClose={() => setDeactivating(false)}
        email={formData.email}
        hasPassword={user?.has_password ?? true}
        onDeactivated={handleDeactivated}
      />
      <ChangeEmailDialog
        open={changingEmail}
        onClose={() => setChangingEmail(false)}
        currentEmail={formData.email}
        hasPassword={user?.has_password ?? true}
        onChanged={(updated) => {
          setUser(updated)
          // Only the address: anything else typed into the form stays unsaved.
          setFormData((f) => ({ ...f, email: updated.email }))
          setChangingEmail(false)
          toast.success(`Your email address is now ${updated.email}`)
        }}
      />
    </div>
  )
}
