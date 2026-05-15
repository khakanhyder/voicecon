'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function TeamSettingsPage() {
  const [email, setEmail] = useState('')
  const [teamMembers] = useState([
    {
      id: '1',
      name: 'John Doe',
      email: 'john@example.com',
      role: 'Owner',
      status: 'Active',
    },
  ])

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    // TODO: Implement API call to invite team member
    console.log('Inviting:', email)
    setEmail('')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Team Management</h1>
        <p className="text-muted-foreground">
          Invite team members and manage permissions
        </p>
      </div>

      {/* Invite Member */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Invite Team Member</h2>

        <form onSubmit={handleInvite} className="flex gap-4">
          <div className="flex-1 space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              placeholder="colleague@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="flex items-end">
            <Button type="submit">Send Invite</Button>
          </div>
        </form>
      </div>

      {/* Team Members */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Team Members</h2>

        <div className="space-y-4">
          {teamMembers.map((member) => (
            <div
              key={member.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                  {member.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div>
                  <p className="font-medium">{member.name}</p>
                  <p className="text-sm text-muted-foreground">{member.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-sm font-medium">{member.role}</p>
                  <p className="text-xs text-muted-foreground">{member.status}</p>
                </div>
                <Button variant="ghost" size="sm" disabled={member.role === 'Owner'}>
                  {member.role === 'Owner' ? 'Owner' : 'Remove'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Roles & Permissions */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Roles & Permissions</h2>

        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <div className="rounded bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
              Owner
            </div>
            <div className="flex-1">
              <p className="text-sm">Full access to all features and settings</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="rounded bg-muted px-2 py-1 text-xs font-medium">
              Admin
            </div>
            <div className="flex-1">
              <p className="text-sm">Can manage team members and most settings</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="rounded bg-muted px-2 py-1 text-xs font-medium">
              Member
            </div>
            <div className="flex-1">
              <p className="text-sm">Can create and manage agents and workflows</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="rounded bg-muted px-2 py-1 text-xs font-medium">
              Viewer
            </div>
            <div className="flex-1">
              <p className="text-sm">Read-only access to view agents and analytics</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
