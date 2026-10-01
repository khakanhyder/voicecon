'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Copy, KeyRound } from 'lucide-react'
import { PhoneDialog } from '@/components/phone-numbers/PhoneDialog'
import { copyText } from '@/lib/clipboard'
import { API_BASE } from '@/lib/constants'

export interface RevealedKey {
  /** The full secret. Held only in this page's memory, only while the dialog is open. */
  secret: string
  name: string
  /** A regenerated key replaced one that integrations may still be using. */
  regenerated: boolean
}

interface Props {
  revealed: RevealedKey | null
  /** The person has confirmed they saved the key. The parent must drop the secret. */
  onDone: () => void
}

/**
 * The one time an API key's full secret is shown: straight after it is created
 * or regenerated.
 *
 * The server keeps only a hash, so this really is the only chance — there is
 * nothing to "reveal" later, and a lost key is replaced by regenerating. The
 * dialog therefore cannot be dismissed by accident: Escape, the backdrop and
 * the corner X do nothing until the key has been copied or the person ticks
 * that they have saved it.
 */
export function ApiKeyRevealDialog({ revealed, onDone }: Props) {
  const [copied, setCopied] = useState(false)
  const [copyFailed, setCopyFailed] = useState(false)
  const [saved, setSaved] = useState(false)
  const fieldRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setCopied(false)
    setCopyFailed(false)
    setSaved(false)
  }, [revealed?.secret])

  if (!revealed) return null
  const { secret, name, regenerated } = revealed
  const canClose = copied || saved

  const copy = async () => {
    const ok = await copyText(secret)
    setCopied(ok)
    setCopyFailed(!ok)
    if (!ok) {
      // Leave it selected so Ctrl/Cmd+C or a long-press finishes the job.
      fieldRef.current?.focus()
      fieldRef.current?.select()
    }
  }

  return (
    <PhoneDialog
      open
      onClose={() => canClose && onDone()}
      busy={!canClose}
      size="lg"
      title={regenerated ? 'Your new API key' : 'Your API key'}
      description={
        regenerated
          ? `“${name}” has a new secret. The previous one has stopped working.`
          : `“${name}” is ready to use.`
      }
      icon={<KeyRound className="h-5 w-5" />}
      footer={
        <button
          type="button"
          onClick={onDone}
          disabled={!canClose}
          className="inline-flex h-11 items-center justify-center rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white hover:bg-[#0c5a4b] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Done
        </button>
      }
    >
      <div className="space-y-5">
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3 text-[13px] leading-relaxed text-amber-900"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600" aria-hidden="true" />
          <span>
            <strong>Copy this key and store it somewhere safe now.</strong> For your security it is
            shown only this once. We keep no copy that can be shown again, so if you lose it you
            will need to regenerate the key.
          </span>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="revealed-api-key" className="block font-poppins text-[14px] font-bold text-[#000000]">
            API key
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="revealed-api-key"
              ref={fieldRef}
              value={secret}
              readOnly
              spellCheck={false}
              autoComplete="off"
              onFocus={(e) => e.currentTarget.select()}
              className="h-[45px] min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 font-mono text-[13px] text-slate-900 outline-none focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15"
            />
            <button
              type="button"
              onClick={copy}
              className="inline-flex h-[45px] flex-shrink-0 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-4 text-[14px] font-semibold text-white hover:bg-[#0c5a4b]"
            >
              {copied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
              {copied ? 'Copied' : 'Copy key'}
            </button>
          </div>
          {/* Announced to screen readers; a toast would sit behind the dialog. */}
          <p aria-live="polite" className="min-h-[18px] text-[12px]">
            {copied && <span className="text-[#0F6A59]">Copied to your clipboard.</span>}
            {copyFailed && (
              <span className="text-red-600">
                Your browser blocked copying. The key is selected: press Ctrl+C (⌘C on Mac), or
                long-press and choose Copy.
              </span>
            )}
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-[13px] font-medium text-slate-700">Use it like this:</p>
          <pre className="overflow-x-auto rounded-[8px] bg-black/85 p-3 text-[12px] leading-relaxed text-white">
            {`curl ${API_BASE}/api/v1/agents \\
  -H "Authorization: Bearer ${secret}"`}
          </pre>
          <p className="text-xs text-slate-500">
            An <code>X-API-Key</code> header works too. The key acts only in this workspace.
          </p>
        </div>

        <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-slate-200 px-3 py-3 text-[14px] text-slate-800">
          <input
            type="checkbox"
            checked={saved}
            onChange={(e) => setSaved(e.target.checked)}
            className="mt-0.5 h-4 w-4 flex-shrink-0 rounded border-slate-300 text-[#0F6A59] focus:ring-[#0F6A59]"
          />
          <span>I have saved this key somewhere safe.</span>
        </label>
      </div>
    </PhoneDialog>
  )
}
