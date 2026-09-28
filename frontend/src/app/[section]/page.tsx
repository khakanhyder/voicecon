import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { HomePage, homeMetadata } from '@/components/landing/HomePage'
import { SECTION_PATHS } from '@/components/landing/sections'

/**
 * The landing page's section URLs (/pricing, /faq, ...). Each renders the home
 * page under its own title, description and canonical; SmoothScroll then lands
 * on the section. Only the paths in SECTION_PATHS exist: anything else at the
 * root that is not another route is a 404.
 */

// Same cadence as the home page (see app/page.tsx).
export const revalidate = 60
export const dynamicParams = false

export function generateStaticParams() {
  return Object.keys(SECTION_PATHS).map((path) => ({ section: path.slice(1) }))
}

interface Props {
  params: { section: string }
}

export function generateMetadata({ params }: Props): Promise<Metadata> {
  return homeMetadata(`/${params.section}`)
}

export default function SectionPage({ params }: Props) {
  if (!SECTION_PATHS[`/${params.section}`]) notFound()
  return <HomePage />
}
