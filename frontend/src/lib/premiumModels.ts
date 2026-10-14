/**
 * Which AI models are "premium": their minutes count the plan's premium
 * multiplier times (1.5× by default). Mirrors `catalog.is_premium_model` in
 * the backend, which is what billing actually uses; keep the two in step.
 */
const STANDARD_MARKERS = ['mini', 'nano', 'haiku', 'gpt-3.5']
const PRICED_PROVIDERS = ['openai', 'anthropic', 'openrouter']

export function isPremiumModel(provider: string | null | undefined, model: string | null | undefined): boolean {
  if (!model) return false
  if (!PRICED_PROVIDERS.includes((provider || 'openai').toLowerCase())) return false
  const name = model.toLowerCase().split('/').pop() ?? ''
  return !STANDARD_MARKERS.some((marker) => name.includes(marker))
}

/** "Premium · 1.5× minutes", or null for a standard model / no multiplier. */
export function premiumTag(
  provider: string | null | undefined,
  model: string | null | undefined,
  multiplier: number | null | undefined
): string | null {
  const m = multiplier ?? 1
  if (m <= 1 || !isPremiumModel(provider, model)) return null
  return `Premium · ${m.toLocaleString('en-US')}× minutes`
}
