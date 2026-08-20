'use client'

import Link from 'next/link'

/**
 * Workspace switcher for the sidebar.
 *
 * A user who has been invited somewhere belongs to more than one workspace, and
 * needs to see which one they are in and move between them. When there is only
 * one workspace this still renders the name and role — that alone answers
 * "whose data am I looking at?".
 *
 * Switching reloads the page: every list on screen is workspace-scoped, and a
 * full reload is the honest way to make sure none of it is stale.
 */

import { useEffect, useRef, useState } from 'react'
import { Building2, Check, ChevronsUpDown, Plus , Settings} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/lib/api'
import { workspaceService } from '@/lib/workspace'
import { useWorkspaceStore } from '@/store/workspaceStore'

const ROLE_LABEL: Record<string, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
}

interface WorkspaceSwitcherProps {
  /** Collapsed rail has no room for the name — show just the badge. */
  collapsed?: boolean
  /** Sidebar panel colour, so the switcher matches its surroundings. */
  panelBackground?: string
}

export function WorkspaceSwitcher({ collapsed, panelBackground }: WorkspaceSwitcherProps) {
  const { current, workspaces, isLoading, isSwitching, switchTo } = useWorkspaceStore()
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Click-away close, so the panel doesn't linger over the nav.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const handleSwitch = async (id: string) => {
    if (id === current?.id) {
      setOpen(false)
      return
    }
    const next = await switchTo(id)
    if (!next) {
      toast.error('Could not switch workspace')
      return
    }
    toast.success(`Switched to ${next.name}`)
    setOpen(false)
    // Everything on screen belongs to the old workspace — start clean.
    window.location.reload()
  }

  const handleCreate = async () => {
    const name = window.prompt('Name your new workspace')?.trim()
    if (!name) return
    setCreating(true)
    try {
      const created = await workspaceService.create(name)
      toast.success(`Created ${created.name}`)
      window.location.reload()
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setCreating(false)
    }
  }

  if (isLoading && !current) {
    return (
      <div className={cn('px-3', collapsed && 'px-2')}>
        <div className="h-[46px] animate-pulse rounded-xl bg-white/10" />
      </div>
    )
  }

  if (!current) return null

  const initial = current.name.trim()[0]?.toUpperCase() ?? 'W'

  return (
    <div ref={containerRef} className={cn('relative', collapsed ? 'px-2' : 'px-3')}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={collapsed ? `${current.name} · ${ROLE_LABEL[current.role] ?? current.role}` : undefined}
        disabled={isSwitching}
        className={cn(
          'flex w-full items-center gap-3 rounded-xl py-2.5 text-left transition-colors disabled:opacity-60',
          collapsed ? 'justify-center px-2' : 'px-3'
        )}
        style={{ background: panelBackground }}
      >
        <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/20 text-[13px] font-bold text-white">
          {initial}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-poppins text-[14px] font-semibold leading-tight text-white">
                {current.name}
              </span>
              <span className="mt-0.5 block font-poppins text-[11px] leading-none text-white/60">
                {ROLE_LABEL[current.role] ?? current.role}
                {workspaces.length > 1 ? ` · ${workspaces.length} workspaces` : ''}
              </span>
            </span>
            <ChevronsUpDown className="h-4 w-4 flex-shrink-0 text-white/70" />
          </>
        )}
      </button>

      {open && (
        <div
          className={cn(
            'absolute z-50 mt-1.5 overflow-hidden rounded-xl shadow-xl ring-1 ring-black/10',
            collapsed ? 'left-full ml-2 top-0 w-64' : 'left-3 right-3'
          )}
          style={{ background: '#0b5045' }}
        >
          <p className="px-3 pt-3 pb-1 font-poppins text-[10px] uppercase tracking-wider text-white/50">
            Workspaces
          </p>
          <div className="max-h-64 overflow-y-auto">
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                type="button"
                onClick={() => handleSwitch(ws.id)}
                disabled={isSwitching}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-white/10 disabled:opacity-60"
              >
                <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-white/15 text-[12px] font-bold text-white">
                  {ws.name.trim()[0]?.toUpperCase() ?? 'W'}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-poppins text-[13px] text-white">
                    {ws.name}
                  </span>
                  <span className="block font-poppins text-[11px] text-white/55">
                    {ROLE_LABEL[ws.role] ?? ws.role} · {ws.member_count}{' '}
                    {ws.member_count === 1 ? 'member' : 'members'}
                  </span>
                </span>
                {ws.is_current && <Check className="h-4 w-4 flex-shrink-0 text-white" />}
              </button>
            ))}
          </div>
          <Link
            href="/dashboard/settings/workspace"
            onClick={() => setOpen(false)}
            className="flex w-full items-center gap-2.5 border-t border-white/10 px-3 py-2.5 font-poppins text-[13px] text-white/85 transition-colors hover:bg-white/10"
          >
            <Settings className="h-4 w-4" />
            Workspace settings
          </Link>
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating}
            className="flex w-full items-center gap-2.5 border-t border-white/10 px-3 py-2.5 font-poppins text-[13px] text-white/85 transition-colors hover:bg-white/10 disabled:opacity-60"
          >
            <Plus className="h-4 w-4" />
            {creating ? 'Creating…' : 'New workspace'}
          </button>
        </div>
      )}
    </div>
  )
}

/** Compact read-only badge, for headers and page titles. */
export function WorkspaceBadge({ className }: { className?: string }) {
  const current = useWorkspaceStore((s) => s.current)
  if (!current) return null
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600',
        className
      )}
    >
      <Building2 className="h-3.5 w-3.5" />
      {current.name}
      <span className="text-slate-400">·</span>
      <span className="capitalize">{current.role}</span>
    </span>
  )
}
