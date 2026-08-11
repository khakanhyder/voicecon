import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { DOCS_NAV } from '@/lib/docs/navigation'

/**
 * The full section index, for the documentation home.
 *
 * Deliberately typographic — no coloured icon tiles. On a reference site those
 * read as an app dashboard rather than a table of contents, and the page count
 * is the more useful signal anyway: it tells a newcomer how much of a section
 * they are committing to before they open it.
 */
export function SectionGrid() {
  return (
    <div className="grid gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-2">
      {DOCS_NAV.map((group) => (
        <Link
          key={group.title}
          href={group.pages[0].href}
          className="group flex flex-col bg-white px-5 py-4 transition-colors hover:bg-brand-50/40"
        >
          <span className="flex items-center gap-1.5 font-poppins text-[14.5px] font-bold tracking-[-0.01em] text-slate-900 transition-colors group-hover:text-brand-700">
            {group.title}
            <ArrowRight className="h-3.5 w-3.5 flex-shrink-0 text-slate-300 transition-all group-hover:translate-x-0.5 group-hover:text-brand-500" />
          </span>
          <span className="mt-1 text-[13.5px] leading-[1.6] text-slate-500">{group.blurb}</span>
          <span className="mt-2.5 font-poppins text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-400">
            {group.pages.length} {group.pages.length === 1 ? 'page' : 'pages'}
          </span>
        </Link>
      ))}
    </div>
  )
}

/** Three entry points, for readers who do not yet know what they need. */
export function StartHere() {
  const paths = [
    {
      href: '/docs/quickstart',
      title: 'Ship your first agent',
      body: 'Ten minutes from an empty workspace to a live phone call you can dial.',
    },
    {
      href: '/docs/concepts',
      title: 'Learn the vocabulary',
      body: 'Agents, tools, workflows, and how each one hands off to the next.',
    },
    {
      href: '/docs/tools',
      title: 'Make it act',
      body: 'Give the agent tools so it can book, look up, text, and escalate.',
    },
  ]

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {paths.map((path, index) => (
        <Link
          key={path.href}
          href={path.href}
          className="group rounded-xl border border-slate-200 px-4 py-4 transition-colors hover:border-brand-300 hover:bg-brand-50/40"
        >
          <span className="font-mono text-[11.5px] font-semibold text-brand-500">
            {String(index + 1).padStart(2, '0')}
          </span>
          <span className="mt-2 block font-poppins text-[14.5px] font-bold leading-snug tracking-[-0.01em] text-slate-900 transition-colors group-hover:text-brand-700">
            {path.title}
          </span>
          <span className="mt-1.5 block text-[13.5px] leading-[1.6] text-slate-500">
            {path.body}
          </span>
        </Link>
      ))}
    </div>
  )
}
