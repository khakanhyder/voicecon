'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, Building2, Loader2 } from 'lucide-react'
import { PhoneDialog } from '@/components/phone-numbers/PhoneDialog'
import { getErrorMessage } from '@/lib/api'
import { workspaceService, type WorkspaceDetail } from '@/lib/workspace'

const FIELD_CLASS =
  'h-[45px] w-full rounded-xl border border-slate-200 bg-white px-3 font-poppins text-[14px] text-[#000000] outline-none transition-colors placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15'
const PRIMARY =
  'inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white hover:bg-[#0c5a4b] disabled:opacity-50'
const SECONDARY =
  'inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50'

/** Same ceiling as the API's NonBlankName. */
const MAX_NAME = 255

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (workspace: WorkspaceDetail) => void
}

/** Names and creates a workspace. The caller decides what happens next. */
export function NewWorkspaceDialog({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setName('')
    setBusy(false)
    setError('')
  }, [open])

  const trimmed = name.trim()

  const create = async () => {
    if (!trimmed || busy) return
    setBusy(true)
    setError('')
    try {
      onCreated(await workspaceService.create(trimmed))
    } catch (e) {
      setError(getErrorMessage(e))
      setBusy(false)
    }
  }

  return (
    <PhoneDialog
      open={open}
      onClose={onClose}
      busy={busy}
      size="md"
      title="Create a new workspace"
      description="A separate space with its own agents, numbers, integrations and team. You'll be its owner."
      icon={<Building2 className="h-5 w-5" />}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={busy} className={SECONDARY}>
            Cancel
          </button>
          <button type="submit" form="new-workspace-form" disabled={busy || !trimmed} className={PRIMARY}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {busy ? 'Creating…' : 'Create workspace'}
          </button>
        </>
      }
    >
      <form
        id="new-workspace-form"
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          create()
        }}
      >
        <div className="space-y-1.5">
          <label htmlFor="new-workspace-name" className="block font-poppins text-[14px] font-bold text-[#000000]">
            Workspace name <span className="text-red-500">*</span>
          </label>
          <input
            id="new-workspace-name"
            value={name}
            onChange={(e) => {
              setName(e.target.value)
              setError('')
            }}
            placeholder="e.g. Acme Dental"
            maxLength={MAX_NAME}
            autoComplete="organization"
            autoFocus
            className={FIELD_CLASS}
          />
          <p className="text-xs text-slate-500">You can rename it later in Workspace settings.</p>
        </div>

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </form>
    </PhoneDialog>
  )
}
