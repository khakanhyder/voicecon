'use client'

import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and preferences
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Link href="/dashboard/settings/profile">
          <div className="rounded-lg border bg-card p-6 hover:bg-accent transition-colors cursor-pointer">
            <h3 className="text-xl font-semibold mb-2">Profile</h3>
            <p className="text-muted-foreground">
              Update your profile information and preferences
            </p>
          </div>
        </Link>

        <Link href="/dashboard/settings/billing">
          <div className="rounded-lg border bg-card p-6 hover:bg-accent transition-colors cursor-pointer">
            <h3 className="text-xl font-semibold mb-2">Billing</h3>
            <p className="text-muted-foreground">
              Manage your subscription and payment methods
            </p>
          </div>
        </Link>

        <Link href="/dashboard/settings/team">
          <div className="rounded-lg border bg-card p-6 hover:bg-accent transition-colors cursor-pointer">
            <h3 className="text-xl font-semibold mb-2">Team</h3>
            <p className="text-muted-foreground">
              Invite team members and manage permissions
            </p>
          </div>
        </Link>

        <Link href="/dashboard/settings/api-keys">
          <div className="rounded-lg border bg-card p-6 hover:bg-accent transition-colors cursor-pointer">
            <h3 className="text-xl font-semibold mb-2">API Keys</h3>
            <p className="text-muted-foreground">
              Generate and manage API keys for integrations
            </p>
          </div>
        </Link>
      </div>
    </div>
  )
}
