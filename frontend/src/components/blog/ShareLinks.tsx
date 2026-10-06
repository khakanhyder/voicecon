'use client'

import { useState } from 'react'
import { Check, Link2 } from 'lucide-react'

/**
 * Share an article: LinkedIn, X, Facebook and copy-link. Plain share URLs, no
 * third-party scripts, so nothing extra loads and the CSP needs no changes.
 */
export function ShareLinks({ url, title }: { url: string; title: string }) {
  const [copied, setCopied] = useState(false)
  const u = encodeURIComponent(url)
  const t = encodeURIComponent(title)
  const targets = [
    {
      label: 'LinkedIn',
      href: `https://www.linkedin.com/sharing/share-offsite/?url=${u}`,
      icon: (
        <path d="M4.98 3.5C4.98 4.88 3.87 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1 4.98 2.12 4.98 3.5zM.24 8h4.52v13.5H.24V8zm7.5 0h4.33v1.85h.06c.6-1.14 2.08-2.35 4.28-2.35 4.58 0 5.42 3.01 5.42 6.93v8.07h-4.52v-7.15c0-1.71-.03-3.9-2.38-3.9-2.38 0-2.75 1.86-2.75 3.78v7.27H7.74V8z" />
      ),
    },
    {
      label: 'X',
      href: `https://twitter.com/intent/tweet?url=${u}&text=${t}`,
      icon: <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />,
    },
    {
      label: 'Facebook',
      href: `https://www.facebook.com/sharer/sharer.php?u=${u}`,
      icon: (
        <path d="M24 12.07C24 5.41 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.04V9.41c0-3.02 1.8-4.7 4.54-4.7 1.31 0 2.68.24 2.68.24v2.97h-1.5c-1.5 0-1.96.93-1.96 1.89v2.26h3.32l-.53 3.5h-2.8V24C19.62 23.1 24 18.1 24 12.07" />
      ),
    },
  ]

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard blocked (insecure origin, denied permission): nothing to undo.
    }
  }

  const button =
    'inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/[0.04] text-white/75 transition-colors hover:border-brand-300/50 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200'

  return (
    <div className="flex items-center gap-2">
      <span className="mr-1 text-sm text-white/55">Share</span>
      {targets.map((target) => (
        <a
          key={target.label}
          href={target.href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Share on ${target.label} (opens in a new tab)`}
          className={button}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
            {target.icon}
          </svg>
        </a>
      ))}
      <button type="button" onClick={copy} aria-label={copied ? 'Link copied' : 'Copy link'} className={button}>
        {copied ? <Check className="h-4 w-4 text-brand-200" /> : <Link2 className="h-4 w-4" />}
      </button>
    </div>
  )
}
