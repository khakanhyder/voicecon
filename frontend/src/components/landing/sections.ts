/**
 * Clean URLs for the landing page's sections: voicecon.ai/pricing instead of
 * voicecon.ai/#pricing. Middleware rewrites each path to the home page, and
 * SmoothScroll scrolls to the matching section on load and on click. Shared by
 * middleware, so keep this file free of React and browser code.
 */
export const SECTION_PATHS: Record<string, string> = {
  '/product': 'features',
  '/product-tour': 'product',
  '/how-it-works': 'how-it-works',
  '/workflows': 'workflows',
  '/integrations': 'integrations',
  '/use-cases': 'use-cases',
  '/pricing': 'pricing',
  '/faq': 'faq',
}

/** Section element id for a path, or undefined when the path is not a section. */
export function sectionForPath(pathname: string): string | undefined {
  return SECTION_PATHS[pathname]
}
