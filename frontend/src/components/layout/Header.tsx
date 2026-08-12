'use client'

import { usePathname } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Menu, Plus } from 'lucide-react'
import Link from 'next/link'
import { NotificationBell } from '@/components/layout/NotificationBell'
import { WorkspaceBadge } from '@/components/layout/WorkspaceSwitcher'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { PERMISSIONS } from '@/lib/workspace'

/**
 * `action.permission` names the write capability the button would exercise, so
 * a viewer isn't offered a "New Agent" button the API would reject. The API
 * enforces the same permission regardless of what is rendered here.
 */
const pageTitles: Record<
  string,
  {
    title: string
    description: string
    action?: { label: string; href: string; permission?: string }
  }
> = {
  '/dashboard': { title: 'Dashboard', description: 'Overview of your voice AI platform' },
  '/dashboard/agents': { title: 'Agents', description: 'Manage your AI voice agents', action: { label: 'New Agent', href: '/dashboard/agents/new', permission: PERMISSIONS.agentsWrite } },
  '/dashboard/calls': { title: 'Call History', description: 'View and manage all calls' },
  '/dashboard/phone-numbers': { title: 'Phone Numbers', description: 'Manage your phone numbers', action: { label: 'Purchase Number', href: '/dashboard/phone-numbers?tab=search', permission: PERMISSIONS.phoneNumbersWrite } },
  '/dashboard/tools': { title: 'Tools', description: 'Manage integration tools' },
  '/dashboard/knowledge': { title: 'Knowledge Base', description: 'Documents your agents answer from', action: { label: 'New Knowledge Base', href: '/dashboard/knowledge/new', permission: PERMISSIONS.knowledgeWrite } },
  '/dashboard/workflows': { title: 'Workflows', description: 'Automate with visual workflows', action: { label: 'New Workflow', href: '/dashboard/workflows/new', permission: PERMISSIONS.workflowsWrite } },
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
  const workspace = useWorkspaceStore((s) => s.current)
  const can = useWorkspaceStore((s) => s.can)

  const getPageInfo = (path: string) => {
    // Exact match first
    if (pageTitles[path]) return { ...pageTitles[path] }

    // Find longest matching prefix
    const matches = Object.keys(pageTitles)
      .filter((p) => path.startsWith(p + '/'))
      .sort((a, b) => b.length - a.length)

    if (matches.length > 0) {
      const parentInfo = pageTitles[matches[0]]
      return {
        ...parentInfo,
        action: undefined // Don't show parent actions (like "New Agent") on sub-pages
      }
    }

    return { title: 'Voicecon', description: '' }
  }

  const pageInfo = getPageInfo(pathname)

  return (
    // The header floats as its own rounded panel, matching the sidebar and the
    // cards below instead of sitting on a flat full-bleed bar.
    <div className="flex-shrink-0 px-4 pt-4 md:px-5 md:pt-5">
      <header className="flex h-[68px] items-center gap-4 rounded-2xl border border-slate-200 bg-white px-3 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] md:px-4">
        {/* Mobile menu trigger */}
        <button
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition-colors hover:border-[#0F6A59]/30 hover:bg-[#0F6A59]/5 hover:text-[#0F6A59] lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Page info — a green rule ties the title back to the brand */}
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="hidden h-9 w-1 flex-shrink-0 rounded-full bg-gradient-to-b from-[#0F6A59] to-[#1fa183] sm:block" />
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold leading-tight text-slate-900">{pageInfo.title}</h1>
            {pageInfo.description && (
              <p className="hidden truncate text-xs text-slate-500 sm:block">{pageInfo.description}</p>
            )}
          </div>
        </div>

        {/* Right cluster — every control is a 40px pill so they read as one set */}
        <div className="flex flex-shrink-0 items-center gap-2">
          {/* Workspace badge — shows current workspace name and role */}
          {workspace && (
            <div className="hidden h-10 items-center gap-2.5 rounded-full border border-[#0F6A59]/15 bg-gradient-to-r from-[#0F6A59]/[0.06] to-[#1fa183]/[0.06] px-4 md:flex">
              <span
                className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-[11px] font-bold text-white"
                style={{ background: 'linear-gradient(135deg, #0F6A59 0%, #1fa183 100%)' }}
              >
                {workspace.name?.trim()[0]?.toUpperCase() ?? 'W'}
              </span>
              <span className="text-sm font-semibold text-slate-800">{workspace.name}</span>
              <span className="text-slate-300">·</span>
              <span className="rounded-full bg-[#0F6A59]/10 px-2 py-0.5 text-[11px] font-semibold capitalize text-[#0F6A59]">
                {workspace.role}
              </span>
            </div>
          )}

          {/* Primary action */}
          {pageInfo.action &&
            // Until the workspace loads we don't know the role — showing the
            // action and letting the API decide beats flashing it away.
            (!pageInfo.action.permission || !workspace || can(pageInfo.action.permission)) && (
              <Link href={pageInfo.action.href}>
                <Button
                  size="sm"
                  className="hidden h-10 gap-1.5 rounded-full border-0 bg-[#0F6A59] px-5 text-white shadow-sm transition-all hover:bg-[#0d5a4c] hover:shadow-md sm:flex"
                >
                  <Plus className="h-4 w-4" />
                  {pageInfo.action.label}
                </Button>
              </Link>
            )}

          {/* Notifications */}
          <NotificationBell />

          {/* User */}
          <div className="flex h-10 items-center gap-2.5 rounded-full border border-slate-200 bg-slate-50 py-1 pl-1 pr-1 transition-colors hover:bg-white xl:pr-4">
            <div
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
              style={{ background: 'linear-gradient(135deg, #0F6A59 0%, #1fa183 100%)' }}
            >
              {user?.full_name ? user.full_name[0].toUpperCase() : 'U'}
            </div>
            <div className="hidden xl:block">
              <p className="text-sm font-medium leading-none text-slate-900">{user?.full_name || 'User'}</p>
              <p className="mt-1 max-w-32 truncate text-xs leading-none text-slate-500">{user?.email}</p>
            </div>
          </div>
        </div>
      </header>
    </div>
  )
}
