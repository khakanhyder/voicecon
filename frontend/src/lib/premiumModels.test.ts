import { describe, expect, it } from 'vitest'
import { isPremiumModel, premiumTag } from './premiumModels'

describe('isPremiumModel (mirrors catalog.is_premium_model)', () => {
  it.each([
    ['openai', 'gpt-5.5', true],
    ['openai', 'gpt-4o', true],
    ['openai', 'gpt-5.4-nano', false],
    ['openai', 'gpt-4o-mini', false],
    ['openai', 'o4-mini', false],
    ['anthropic', 'claude-opus-5-5', true],
    ['anthropic', 'claude-sonnet-5', true],
    ['anthropic', 'claude-haiku-4-5-20251001', false],
    ['openrouter', 'openai/gpt-5.5', true],
    ['custom', 'llama', false],
  ])('%s %s -> %s', (provider, model, premium) => {
    expect(isPremiumModel(provider, model)).toBe(premium)
  })

  it('tags only premium models, and only when the plan multiplies', () => {
    expect(premiumTag('openai', 'gpt-5.5', 1.5)).toBe('Premium · 1.5× minutes')
    expect(premiumTag('openai', 'gpt-5.5', 1)).toBeNull()
    expect(premiumTag('openai', 'gpt-5.4-nano', 1.5)).toBeNull()
  })
})
