'use client'

import { useAuth } from '@/hooks/useAuth'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { Mic, Phone, Plug, Workflow } from 'lucide-react'

export default function DashboardPage() {
  const { user } = useAuth()

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div>
        <h1 className="text-3xl font-bold">Welcome back, {user?.full_name || 'there'}!</h1>
        <p className="text-muted-foreground">
          Here&apos;s what&apos;s happening with your voice AI platform today.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Agents</CardTitle>
            <Mic className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">No agents created yet</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Calls</CardTitle>
            <Phone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">No calls made yet</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Integrations</CardTitle>
            <Plug className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">Connect your first app</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Workflows</CardTitle>
            <Workflow className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">Create your first workflow</p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Get started with these common tasks</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Link href="/dashboard/agents/new">
            <Button variant="outline" className="h-auto w-full justify-start p-4">
              <div className="flex items-start gap-3">
                <Mic className="mt-1 h-5 w-5" />
                <div className="text-left">
                  <div className="font-medium">Create Your First Agent</div>
                  <div className="text-sm text-muted-foreground">
                    Build an AI voice agent in minutes
                  </div>
                </div>
              </div>
            </Button>
          </Link>

          <Link href="/dashboard/integrations">
            <Button variant="outline" className="h-auto w-full justify-start p-4">
              <div className="flex items-start gap-3">
                <Plug className="mt-1 h-5 w-5" />
                <div className="text-left">
                  <div className="font-medium">Connect an Integration</div>
                  <div className="text-sm text-muted-foreground">
                    Link your favorite apps and tools
                  </div>
                </div>
              </div>
            </Button>
          </Link>

          <Link href="/dashboard/workflows/new">
            <Button variant="outline" className="h-auto w-full justify-start p-4">
              <div className="flex items-start gap-3">
                <Workflow className="mt-1 h-5 w-5" />
                <div className="text-left">
                  <div className="font-medium">Build a Workflow</div>
                  <div className="text-sm text-muted-foreground">
                    Automate tasks with visual workflows
                  </div>
                </div>
              </div>
            </Button>
          </Link>

          <Link href="/dashboard/marketplace">
            <Button variant="outline" className="h-auto w-full justify-start p-4">
              <div className="flex items-start gap-3">
                <div className="mt-1 text-lg">🛍️</div>
                <div className="text-left">
                  <div className="font-medium">Browse Marketplace</div>
                  <div className="text-sm text-muted-foreground">
                    Explore templates and pre-built agents
                  </div>
                </div>
              </div>
            </Button>
          </Link>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Your latest actions and events</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            No recent activity
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
