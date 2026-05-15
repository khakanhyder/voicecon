'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/store/authStore'

export default function HomePage() {
  const router = useRouter()
  const { isAuthenticated, isLoading } = useAuthStore()

  // Redirect authenticated users to analytics dashboard
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push('/dashboard/analytics')
    }
  }, [isAuthenticated, isLoading, router])

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    )
  }

  // Show landing page for non-authenticated users
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="text-2xl font-bold text-primary">Voicecon</div>
          </div>
          <nav className="flex items-center gap-4">
            <Link href="/login">
              <Button variant="ghost">Login</Button>
            </Link>
            <Link href="/register">
              <Button>Get Started</Button>
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="container mx-auto px-4 py-24 text-center">
          <h1 className="mb-6 text-5xl font-bold tracking-tight">
            Voice AI meets <span className="text-primary">Unlimited Integrations</span>
          </h1>
          <p className="mx-auto mb-8 max-w-2xl text-xl text-muted-foreground">
            Create, deploy, and manage AI voice agents with seamless integrations to 500+ apps.
            Build powerful workflows without code.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link href="/register">
              <Button size="lg">Start Building Free</Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="outline">
                View Demo
              </Button>
            </Link>
          </div>
        </section>

        {/* Features Section */}
        <section className="border-t bg-muted/50 py-24">
          <div className="container mx-auto px-4">
            <h2 className="mb-12 text-center text-3xl font-bold">Platform Features</h2>
            <div className="grid gap-8 md:grid-cols-3">
              <div className="rounded-lg border bg-card p-6">
                <div className="mb-4 text-4xl">🎙️</div>
                <h3 className="mb-2 text-xl font-semibold">Voice AI Agents</h3>
                <p className="text-muted-foreground">
                  Create intelligent voice agents with multiple LLM, TTS, and STT providers.
                  Customize conversations and add function calling.
                </p>
              </div>
              <div className="rounded-lg border bg-card p-6">
                <div className="mb-4 text-4xl">🔗</div>
                <h3 className="mb-2 text-xl font-semibold">500+ Integrations</h3>
                <p className="text-muted-foreground">
                  Connect with CRM, marketing tools, calendars, and more. Pre-built connectors
                  for Salesforce, HubSpot, Google, and hundreds more.
                </p>
              </div>
              <div className="rounded-lg border bg-card p-6">
                <div className="mb-4 text-4xl">⚡</div>
                <h3 className="mb-2 text-xl font-semibold">No-Code Workflows</h3>
                <p className="text-muted-foreground">
                  Visual workflow builder with triggers, actions, and conditions. Automate
                  complex processes without writing code.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          © 2024 Voicecon. All rights reserved.
        </div>
      </footer>
    </div>
  )
}
