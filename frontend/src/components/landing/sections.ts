/**
 * Clean URLs for the landing page's sections: voicecon.ai/pricing instead of
 * voicecon.ai/#pricing. Each path is its own route (app/[section]) that renders
 * the home page, and SmoothScroll scrolls to the matching section on load and
 * on click. Shared by middleware, so keep this file free of React and browser
 * code.
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

/**
 * Search and link-preview copy for each section URL. Without it every section
 * shared the home page's title, description and canonical, so search results
 * and browser tabs could not tell /pricing from /faq. Keep the claims to what
 * the product does today.
 */
export const SECTION_META: Record<string, { title: string; description: string }> = {
  '/product': {
    title: 'Platform features | Voicecon',
    description:
      'Build, deploy and improve AI voice agents in one dashboard: prompts, voices, knowledge bases, tools, call history and analytics.',
  },
  '/product-tour': {
    title: 'Product tour | Voicecon',
    description:
      'Take a look at the Voicecon workspace: the agent editor, the workflow canvas, call history and analytics.',
  },
  '/how-it-works': {
    title: 'How it works | Voicecon',
    description:
      'Go from sign-up to your first test call with guided onboarding. No code or telephony setup required.',
  },
  '/workflows': {
    title: 'No-code workflows | Voicecon',
    description:
      'Build automations on a visual canvas: branch on what the caller said, let AI write the follow-up and push the result into your apps.',
  },
  '/integrations': {
    title: 'Integrations | Voicecon',
    description:
      'Connect your CRM, calendar and team chat once, then use them as tools during calls or as steps in a workflow.',
  },
  '/use-cases': {
    title: 'Use cases | Voicecon',
    description:
      'Ready-made AI voice agent templates for common jobs, so you start from a working setup instead of a blank page.',
  },
  '/pricing': {
    title: 'Pricing | Voicecon',
    description: 'Voicecon plans and pricing. Start with a free trial and choose a plan when you are ready to go live.',
  },
  '/faq': {
    title: 'FAQ | Voicecon',
    description: 'Answers to common questions about Voicecon: setup, the free trial, integrations, billing and data.',
  },
}
