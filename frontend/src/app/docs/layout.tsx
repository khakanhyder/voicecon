import type { Metadata } from 'next'
import { DocsShell } from '@/components/docs/DocsShell'

export const metadata: Metadata = {
  title: {
    default: 'Voicecon Documentation',
    template: '%s',
  },
  description:
    'Build, configure, and ship AI voice agents on Voicecon — agents, workflows, tools, integrations, phone numbers, and knowledge bases.',
}

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return <DocsShell>{children}</DocsShell>
}
