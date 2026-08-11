'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * A fenced code sample with a copy button.
 *
 * Code arrives as a plain string rather than children so the copy button has
 * something to put on the clipboard — copying `textContent` off a ref breaks
 * the moment a sample contains a highlighted span.
 */
export function CodeBlock({
  code,
  language,
  filename,
  /** Renders without the dark chrome, for short single-line samples. */
  compact = false,
}: {
  code: string
  language?: string
  filename?: string
  compact?: boolean
}) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      // Clipboard is unavailable over plain HTTP and in some embedded
      // browsers. The sample is still selectable, so failing quietly beats
      // throwing an error at someone who is only trying to read.
    }
  }

  return (
    <figure
      className={cn(
        'group relative overflow-hidden rounded-xl border',
        compact ? 'border-slate-200 bg-slate-50' : 'border-slate-800 bg-slate-900'
      )}
    >
      {(filename || language) && (
        <figcaption
          className={cn(
            'flex items-center justify-between border-b px-4 py-2 font-mono text-[12px]',
            compact
              ? 'border-slate-200 bg-white text-slate-500'
              : 'border-slate-800 bg-slate-950 text-slate-400'
          )}
        >
          <span>{filename ?? language}</span>
        </figcaption>
      )}

      <button
        type="button"
        onClick={copy}
        aria-label={copied ? 'Copied' : 'Copy code'}
        className={cn(
          'absolute right-2.5 flex h-7 w-7 items-center justify-center rounded-md border opacity-0 transition-opacity focus:opacity-100 group-hover:opacity-100',
          filename || language ? 'top-11' : 'top-2.5',
          compact
            ? 'border-slate-200 bg-white text-slate-500 hover:text-slate-900'
            : 'border-slate-700 bg-slate-800 text-slate-400 hover:text-white'
        )}
      >
        {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
      </button>

      <pre
        className={cn(
          'overflow-x-auto p-4 font-mono text-[13px] leading-[1.65]',
          compact ? 'text-slate-800' : 'text-slate-100'
        )}
      >
        <code>{code}</code>
      </pre>
    </figure>
  )
}
