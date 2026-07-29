import { DM_Sans } from 'next/font/google'
import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { Toaster } from 'sonner'

const dmSans = DM_Sans({ 
  subsets: ['latin'],
  variable: '--font-dm-sans',
  display: 'swap',
})
// Poppins (the sidebar/nav face in the brand spec) is resolved through a plain
// CSS stack in globals.css rather than next/font — fetching it from Google
// Fonts stalls every cold compile on machines without network access to them,
// and falls back to the same face anyway.

export const metadata: Metadata = {
  title: 'Voicecon - Voice AI Platform with Integration Management',
  description: 'Create, deploy, and manage AI voice agents with unlimited integrations',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${dmSans.variable} font-sans`}>
        <Providers>
          {children}
          <Toaster position="top-right" richColors />
        </Providers>
      </body>
    </html>
  )
}
