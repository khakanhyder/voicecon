'use client'

import { usePathname } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Menu, Search, Plus } from 'lucide-react'
import Link from 'next/link'
import { NotificationBell } from '@/components/layout/NotificationBell'

const pageTitles: Record<string, { title: string; description: string; action?: { label: string; href: string } }> = {
  '/dashboard': { title: 'Dashboard', description: 'Overview of your voice AI platform' },
  '/dashboard/agents': { title: 'Agents', description: 'Manage your AI voice agents', action: { label: 'New Agent', href: '/dashboard/agents/new' } },
  '/dashboard/calls': { title: 'Call History', description: 'View and manage all calls' },
  '/dashboard/phone-numbers': { title: 'Phone Numbers', description: 'Manage your phone numbers' },
  '/dashboard/knowledge': { title: 'Knowledge Base', description: 'Documents your agents answer from', action: { label: 'New Knowledge Base', href: '/dashboard/knowledge/new' } },
  '/dashboard/workflows': { title: 'Workflows', description: 'Automate with visual workflows', action: { label: 'New Workflow', href: '/dashboard/workflows/new' } },
  '/dashboard/integrations': { title: 'Integrations', description: 'Connect your apps and services' },
  '/dashboard/analytics': { title: 'Analytics', description: 'Insights and performance metrics' },
  '/dashboard/marketplace': { title: 'Marketplace', description: 'Templates and pre-built agents' },
  '/dashboard/settings': { title: 'Settings', description: 'Manage your account and preferences' },
  '/dashboard/settings/profile': { title: 'Profile', description: 'Update your personal information' },
  '/dashboard/settings/billing': { title: 'Billing', description: 'Manage your subscription and payments' },
  '/dashboard/settings/team': { title: 'Team', description: 'Manage team members and roles' },
  '/dashboard/settings/api-keys': { title: 'API Keys', description: 'Manage API access credentials' },
}

interface HeaderProps {
  onMenuClick: () => void
}

export function Header({ onMenuClick }: HeaderProps) {
  const { user } = useAuth()
  const pathname = usePathname()

  const pageInfo = pageTitles[pathname] || { title: 'Voicecon', description: '' }

  return (
    <header className="flex-shrink-0 h-16 bg-white border-b border-slate-200 flex items-center px-4 md:px-6 gap-4">
      {/* Mobile menu trigger */}
      <button
        onClick={onMenuClick}
        className="flex lg:hidden items-center justify-center h-9 w-9 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Page info */}
      <div className="flex-1 min-w-0">
        <h1 className="text-lg font-semibold text-slate-900 leading-tight truncate">{pageInfo.title}</h1>
        <p className="text-xs text-slate-500 hidden sm:block truncate">{pageInfo.description}</p>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* Search — hidden on mobile */}
        <button className="hidden md:flex items-center gap-2 h-9 px-3 rounded-lg border border-slate-200 text-sm text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors w-48 lg:w-56">
          <Search className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1 text-left truncate">Search...</span>
          <kbd className="hidden lg:inline-flex text-xs bg-slate-100 text-slate-400 rounded px-1.5 py-0.5 font-mono">⌘K</kbd>
        </button>

        {/* Primary action */}
        {pageInfo.action && (
          <Link href={pageInfo.action.href}>
            <Button size="sm" className="hidden sm:flex gap-1.5 gradient-primary border-0 text-white hover:opacity-90">
              <Plus className="h-4 w-4" />
              {pageInfo.action.label}
            </Button>
          </Link>
        )}

        {/* Notifications */}
        <NotificationBell />

        {/* User avatar */}
        <div className="flex items-center gap-2 pl-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-full text-white text-sm font-semibold ring-2 ring-blue-100 flex-shrink-0" style={{ background: 'linear-gradient(135deg, #1168d4 0%, #1a85ff 100%)' }}>
            {user?.full_name ? user.full_name[0].toUpperCase() : 'U'}
          </div>
          <div className="hidden xl:block">
            <p className="text-sm font-medium text-slate-900 leading-none">{user?.full_name || 'User'}</p>
            <p className="text-xs text-slate-500 mt-0.5 truncate max-w-32">{user?.email}</p>
          </div>
        </div>
      </div>
    </header>
  )
}
