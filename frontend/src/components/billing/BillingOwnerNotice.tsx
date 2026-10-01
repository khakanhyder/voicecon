'use client'

import { ShieldAlert } from 'lucide-react'

import { PERMISSIONS } from '@/lib/workspace'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { cn } from '@/lib/utils'

/**
 * Whether this person may buy, change or cancel the workspace's plan.
 *
 * Billing belongs to the workspace owner; admins can read it but not change
 * it, and the API answers 403 if they try. Every buy/upgrade surface reads
 * this so it can say so up front, instead of taking a card number and then
 * failing with a role error.
 *
 * `canManage` is true until the workspace has loaded: guessing "no" would
 * flash the notice at owners on every page load, and the server enforces the
 * permission either way.
 */
export function useBillingAccess() {
  const current = useWorkspaceStore((s) => s.current)
  return {
    canManage: !current || current.permissions.includes(PERMISSIONS.billingManage),
    ownerEmail: current?.owner_email ?? null,
    workspaceName: current?.name ?? null,
  }
}

/** Says who can change the plan. Renders nothing for someone who can. */
export function BillingOwnerNotice({ className }: { className?: string }) {
  const { canManage, ownerEmail, workspaceName } = useBillingAccess()
  if (canManage) return null

  return (
    <div
      role="note"
      className={cn(
        'flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900',
        className,
      )}
    >
      <ShieldAlert className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" aria-hidden="true" />
      <div className="min-w-0">
        <p className="font-semibold">Only the workspace owner can change the plan</p>
        <p className="mt-1 break-words text-amber-800">
          You can see the plan and invoices{workspaceName ? ` for ${workspaceName}` : ''}, but buying,
          upgrading or cancelling is up to the owner
          {ownerEmail ? (
            <>
              {' '}
              (<a href={`mailto:${ownerEmail}`} className="font-medium underline">{ownerEmail}</a>)
            </>
          ) : null}
          . Ask them to choose a plan, or switch to a workspace you own.
        </p>
      </div>
    </div>
  )
}
